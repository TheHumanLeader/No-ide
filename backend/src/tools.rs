use crate::{core::*,process};
use serde::Serialize;
use std::{path::{Path,PathBuf},collections::HashSet};
use tokio::process::Command;
#[derive(Clone,Serialize)]pub struct Candidate {pub path:String,pub version:String,pub source:String}
#[derive(Clone,Serialize,Default)]pub struct ToolReport {pub kind:String,pub selected:Option<Candidate>,pub candidates:Vec<Candidate>,pub error:Option<String>}
pub fn candidates(kind:&str)->Vec<(PathBuf,String)> {
 let mut list=vec![];let name=if cfg!(windows){format!("{kind}.exe")}else{kind.into()};
 if let Some(path)=std::env::var_os("PATH"){for d in std::env::split_paths(&path){if d.is_absolute(){list.push((d.join(&name),"PATH".into()));}}}
 #[cfg(windows)]{
  for key in ["ProgramFiles","ProgramFiles(x86)","LOCALAPPDATA"]{if let Some(v)=std::env::var_os(key){for sub in ["Git/cmd","Git/bin","Programs/Git/cmd","TortoiseSVN/bin","SlikSvn/bin","VisualSVN/bin"]{list.push((PathBuf::from(&v).join(sub).join(&name),"常见安装目录".into()));}}}
 }
 #[cfg(unix)]{for d in ["/opt/homebrew/bin","/usr/local/bin","/usr/bin","/bin","/opt/local/bin"]{list.push((Path::new(d).join(&name),"常见安装目录".into()));}}
 let mut seen=HashSet::new();list.into_iter().filter_map(|(p,s)|p.canonicalize().ok().map(|p|(native_path(p),s))).filter(|(p,_)|p.is_file()&&seen.insert(p.clone())).take(12).collect()
}
pub async fn verify(kind:&str,path:&str,source:&str)->Result<Candidate>{
 if !["git","svn"].contains(&kind){return fail("未知客户端")}
 let p=Path::new(path);if !p.is_absolute()||!p.is_file(){return fail("客户端路径必须是存在的绝对文件路径")}
 let p=native_path(p.canonicalize()?);
 let mut c=Command::new(&p);c.arg("--version");if kind=="svn"{c.arg("--quiet");}
 c.current_dir(std::env::temp_dir());c.env("GIT_TERMINAL_PROMPT","0");
 let o=process::capture(c,4,16384).await?;let version=process::checked(o)?.trim().to_string();
 if (kind=="git"&&!version.starts_with("git version "))||(kind=="svn"&&!version.starts_with(|c:char|c.is_ascii_digit())){return fail("文件可运行，但版本输出不匹配客户端类型")}
 Ok(Candidate{path:p.to_string_lossy().into(),version,source:source.into()})
}
pub async fn detect(kind:&str,manual:Option<&String>)->ToolReport{
 let mut report=ToolReport{kind:kind.into(),..Default::default()};
 if let Some(p)=manual{match verify(kind,p,"全局指定").await{Ok(c)=>{report.selected=Some(c.clone());report.candidates.push(c)},Err(e)=>report.error=Some(e.0)}}
 for(p,source)in candidates(kind){if let Ok(c)=verify(kind,&p.to_string_lossy(),&source).await{if !report.candidates.iter().any(|x|x.path==c.path){report.candidates.push(c)}}}
 if manual.is_none(){report.selected=report.candidates.first().cloned();}
 if report.selected.is_none()&&report.error.is_none(){report.error=Some("未找到可用客户端；可手动选择，不自动安装软件".into());}report
}
pub async fn resolve(kind:&str,global:&ToolSettings,project:&ToolSettings)->Result<String>{
 let g=if kind=="git"{&global.git}else{&global.svn};let p=if kind=="git"{&project.git}else{&project.svn};
 if let Some(path)=p.as_ref().or(g.as_ref()){return Ok(verify(kind,path,if p.is_some(){"项目指定"}else{"全局指定"}).await?.path)}
 for(path,_)in candidates(kind){if let Ok(c)=verify(kind,&path.to_string_lossy(),"自动").await{return Ok(c.path)}}fail(format!("未找到 {kind} 命令行客户端，请在客户端配置中选择程序"))
}
