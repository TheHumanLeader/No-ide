use axum::{http::StatusCode, response::{IntoResponse, Response}, Json};
use serde::{Deserialize, Serialize};
use std::{collections::BTreeMap, path::{Component, Path, PathBuf}};
use std::io::Write;

pub type Result<T> = std::result::Result<T, Error>;
#[derive(Debug)]pub struct Error(pub String);
impl std::fmt::Display for Error { fn fmt(&self,f:&mut std::fmt::Formatter<'_>)->std::fmt::Result {self.0.fmt(f)} }
impl std::error::Error for Error {}
impl From<std::io::Error> for Error { fn from(e:std::io::Error)->Self {Self(e.to_string())} }
impl From<serde_json::Error> for Error { fn from(e:serde_json::Error)->Self {Self(e.to_string())} }
impl IntoResponse for Error { fn into_response(self)->Response {(StatusCode::BAD_REQUEST,Json(serde_json::json!({"error":self.0}))).into_response()} }
pub fn fail<T>(s:impl Into<String>)->Result<T> {Err(Error(s.into()))}
pub fn id()->String {uuid::Uuid::new_v4().to_string()}
pub fn text(s:&str,max:usize)->Result<()> {if s.is_empty()||s.len()>max||s.contains('\0'){fail("字段为空、过长或包含无效字符")}else{Ok(())}}

/// External Windows tools commonly expect a DOS/UNC path, not a verbatim prefix.
pub fn native_path(p:PathBuf)->PathBuf {
 #[cfg(windows)]{
  let s=p.to_string_lossy();
  if let Some(tail)=s.strip_prefix(r"\\?\UNC\"){return PathBuf::from(format!(r"\\{}",tail));}
  if let Some(tail)=s.strip_prefix(r"\\?\"){return PathBuf::from(tail);}
 }
 p
}
#[derive(Clone,Default,Serialize,Deserialize)]
#[serde(default)]pub struct ToolSettings { pub git:Option<String>, pub svn:Option<String>, pub svn_config_dir:Option<String> }
#[derive(Clone,Default,Serialize,Deserialize)]
#[serde(default)]pub struct Store { pub tools:ToolSettings, pub projects:Vec<Project>, pub environments:Vec<crate::environments::Environment>, pub environment_defaults:BTreeMap<String,String>, pub build_tools:BTreeMap<String,String> }
#[derive(Clone,Serialize,Deserialize)]pub struct Project {
 pub id:String, pub name:String, pub root:PathBuf,
 #[serde(default)] pub tools:ToolSettings,
 #[serde(default)] pub configs:Vec<RunConfig>,
 #[serde(default)] pub instances:Vec<Instance>,
 #[serde(default)] pub repos:Vec<Repo>,
}
#[derive(Clone,Serialize,Deserialize)]pub struct Repo {pub id:String,pub kind:String,pub path:PathBuf, #[serde(default)]pub groups:crate::groups::Groups}
#[derive(Clone,Default,Serialize,Deserialize)]pub struct CommandSpec {pub program:String, #[serde(default)] pub args:Vec<String>}
#[derive(Clone,Serialize,Deserialize)]pub struct RunConfig {
 pub id:String, pub name:String, #[serde(default)]pub command:CommandSpec,
 #[serde(default)]pub environment_id:Option<String>, #[serde(default)]pub launcher:Option<crate::launch::Launcher>,
 #[serde(default="dot")] pub cwd:String,
 #[serde(default)] pub build:Option<CommandSpec>,
 #[serde(default)] pub watch:Vec<String>,
 #[serde(default)] pub env:BTreeMap<String,String>,
}
fn dot()->String {".".into()}
#[derive(Clone,Serialize,Deserialize)]pub struct Instance {
 pub id:String,pub name:String,pub config_id:String,
 #[serde(default)]pub environment_id:Option<String>,
 #[serde(default)] pub port:Option<u16>,
 #[serde(default)] pub args:Vec<String>,
 #[serde(default)] pub env:BTreeMap<String,String>,
}
impl Store {
 pub fn load(file:&Path)->Result<Self> {if !file.exists(){return Ok(Self::default())} if file.metadata()?.len()>8*1024*1024{return fail("配置文件过大")} Ok(serde_json::from_slice(&std::fs::read(file)?)?)}
 pub fn save(&self,file:&Path)->Result<()> {
  let parent=file.parent().ok_or_else(||Error("无效配置目录".into()))?;
  let mut temp=tempfile::NamedTempFile::new_in(parent)?;
  let bytes=serde_json::to_vec_pretty(self)?;if bytes.len()>8*1024*1024{return fail("本地配置超过 8 MiB，未写入。请减少已记忆的文件分组")};temp.write_all(&bytes)?;temp.as_file().sync_all()?;
  temp.persist(file).map_err(|e|Error(e.to_string()))?;Ok(())
 }
 pub fn project(&self,p:&str)->Result<Project> {self.projects.iter().find(|v|v.id==p).cloned().ok_or_else(||Error("项目不存在".into()))}
}
pub fn validate_command(c:&CommandSpec)->Result<()> {text(&c.program,4096)?;if c.args.len()>128{return fail("参数过多")}for a in &c.args{if a.len()>8192||a.contains('\0'){return fail("无效参数")}}Ok(())}
pub fn validate_env(e:&BTreeMap<String,String>)->Result<()> {if e.len()>64{return fail("环境变量过多")}for(k,v)in e{if k.is_empty()||k.contains(['=','\0'])||v.contains('\0')||v.len()>8192{return fail("环境变量无效")}}Ok(())}
pub fn existing_dir(path:&str)->Result<PathBuf> {let p=Path::new(path);if !p.is_absolute(){return fail("需要系统选择器返回的绝对路径")}let p=p.canonicalize()?;if !p.is_dir(){return fail("不是文件夹")}Ok(native_path(p))}
/// Existing paths, deleted files and symlink ancestors stay in the trusted root.
pub fn inside(root:&Path,relative:&str)->Result<PathBuf> {
 let p=Path::new(relative);
 if p.is_absolute()||p.components().any(|c|matches!(c,Component::ParentDir|Component::Prefix(_)|Component::RootDir)){return fail("路径不能离开项目目录")}
 if relative.contains('\0'){return fail("无效路径")}
 let target=root.join(p);let mut ancestor=target.as_path();
 while !ancestor.exists(){ancestor=ancestor.parent().ok_or_else(||Error("无效路径".into()))?;}
 if !ancestor.canonicalize()?.starts_with(root.canonicalize()?){return fail("链接指向项目外部，已拒绝访问")}
 Ok(target)
}
pub fn vcs_path(root:&Path,path:&str)->Result<PathBuf> {
 text(path,4096)?;if path=="."||path.replace('\\',"/").split('/').any(|c|[".git",".svn"].iter().any(|name|c.trim_end_matches(['.',' ']).eq_ignore_ascii_case(name))){return fail("版本库管理数据不能纳入版本控制或提交；可以在本地移动分组，不会读写其中内容")}
 inside(root,path)
}
#[cfg(test)]mod tests{
 use super::*;
 #[test]fn traversal(){let d=tempfile::tempdir().unwrap();assert!(inside(d.path(),"../x").is_err());assert!(inside(d.path(),"deleted/file.txt").is_ok());assert!(vcs_path(d.path(),".git/config").is_err());}
 #[test]fn persistence(){let d=tempfile::tempdir().unwrap();let p=d.path().join("s.json");let s=Store::default();s.save(&p).unwrap();s.save(&p).unwrap();assert!(Store::load(&p).unwrap().projects.is_empty());}
 #[cfg(windows)]#[test]fn windows_external_paths(){assert_eq!(native_path(PathBuf::from(r"\\?\C:\Tools\git.exe")),PathBuf::from(r"C:\Tools\git.exe"));assert_eq!(native_path(PathBuf::from(r"\\?\UNC\server\share")),PathBuf::from(r"\\server\share"));}
}
