//! Local persistent changelists, independent of .gitignore / svn:ignore.
use crate::core::*;
use serde::{Serialize,Deserialize};
use std::collections::BTreeMap;
pub const DEFAULT:&str="default";
/// A label key, never a filesystem access. Metadata folders and symlinks can be
/// grouped, but traversal / absolute paths are rejected. VCS reads and writes
/// continue to use core::vcs_path, which still protects repository internals.
pub fn path_key(path:&str)->Result<String>{
 text(path,4096)?;
 let normalized=path.replace('\\',"/");
 if normalized.starts_with('/')||normalized.as_bytes().get(1)==Some(&b':'){return fail("分组路径必须是仓库内的相对路径")}
 let mut parts=Vec::new();
 for part in normalized.split('/'){
  if part==".."{return fail("分组路径不能离开仓库目录")}
  if !part.is_empty()&&part!="."{parts.push(part);}
 }
 if parts.is_empty(){return fail("请选择具体文件或目录，不能分组整个仓库根目录")}
 Ok(parts.join("/"))
}
#[derive(Clone,Serialize,Deserialize)]pub struct Group{pub id:String,pub name:String}
#[derive(Clone,Serialize,Deserialize)]#[serde(default)]
pub struct Groups{pub items:Vec<Group>,pub assignments:BTreeMap<String,String>,pub revision:u64}
impl Default for Groups{fn default()->Self{Self{items:vec![Group{id:DEFAULT.into(),name:"默认".into()}],assignments:BTreeMap::new(),revision:0}}}
impl Groups{
 fn assigned(&self,key:&str)->Option<&str>{
  self.assignments.get(key).or_else(||self.assignments.get(&key.replace('/',"\\"))).map(String::as_str).filter(|id|self.items.iter().any(|g|g.id==*id))
 }
 pub fn of<'a>(&'a self,path:&str,original:Option<&str>)->&'a str{
  let Ok(key)=path_key(path) else{return DEFAULT};
  if let Some(id)=self.assigned(&key){return id}
  if let Some(old)=original.and_then(|p|path_key(p).ok()){if let Some(id)=self.assigned(&old){return id}}
  // Nearest parent assignment wins. Explicit child "default" overrides a group.
  let mut parent=key.as_str();
  while let Some((next,_))=parent.rsplit_once('/') {if let Some(id)=self.assigned(next){return id}parent=next;}
  DEFAULT
 }
 pub fn name(&self,id:&str)->Result<&str>{self.items.iter().find(|g|g.id==id).map(|g|g.name.as_str()).ok_or_else(||Error("分组已不存在，请刷新".into()))}
 pub fn save(&mut self,group_id:&str,name:&str)->Result<Group>{
  let name=name.trim();text(name,120)?;if group_id==DEFAULT{return fail("默认分组不可重命名")};
  if self.items.iter().any(|g|g.name==name&&g.id!=group_id){return fail("分组名称已存在")};
  if group_id.is_empty(){if self.items.len()>=64{return fail("每个仓库最多 64 个分组")};let g=Group{id:id(),name:name.into()};self.items.push(g.clone());self.revision+=1;Ok(g)}
  else{let g=self.items.iter_mut().find(|g|g.id==group_id).ok_or_else(||Error("分组不存在".into()))?;g.name=name.into();self.revision+=1;Ok(g.clone())}
 }
 pub fn remove(&mut self,id:&str)->Result<()>{if id==DEFAULT{return fail("默认分组不可删除")};self.name(id)?;self.items.retain(|g|g.id!=id);self.assignments.retain(|_,g|g!=id);self.revision+=1;Ok(())}
 pub fn set(&mut self,paths:&[String],id:&str)->Result<()>{
  self.name(id)?;let keys=paths.iter().map(|p|path_key(p)).collect::<Result<std::collections::BTreeSet<_>>>()?;
  if self.assignments.len()+keys.iter().filter(|p|!self.assignments.contains_key(*p)).count()>20000{return fail("已记忆的文件分组达到 20000 条上限")};
  for key in keys{self.assignments.remove(&key.replace('/',"\\"));self.assignments.insert(key,id.into());}self.revision+=1;Ok(())
 }
}
#[cfg(test)]mod tests{
 use super::*;
 #[test]fn metadata_labels_do_not_need_access_to_metadata(){let mut g=Groups::default();let x=g.save("","忽略不提交").unwrap();g.set(&[".git".into(),"mirror\\.git".into(),"old/.svn/".into()],&x.id).unwrap();for p in [".git",".git/config","mirror/.git/objects/aa","old/.svn/wc.db"]{assert_eq!(g.of(p,None),x.id)}g.set(&[".git/specific".into()],DEFAULT).unwrap();assert_eq!(g.of(".git/specific/file",None),DEFAULT);assert_eq!(g.of(".gitignore",None),DEFAULT);let encoded=serde_json::to_vec(&g).unwrap();let again:Groups=serde_json::from_slice(&encoded).unwrap();assert_eq!(again.of("mirror\\.git\\config",None),x.id);}
 #[test]fn labels_reject_escape_and_validate_batch_before_changes(){for p in [".","../x",".git/../../x",r"..\x",r"C:\temp",r"\\server\share","/etc/passwd"]{assert!(path_key(p).is_err(),"{p}")};let mut g=Groups::default();assert!(g.set(&["valid".into(),"../escape".into()],DEFAULT).is_err());assert!(g.assignments.is_empty());}
 #[test]fn remembers_clean_and_renamed_paths(){let mut g=Groups::default();let x=g.save("","忽略不提交").unwrap();g.set(&["settings.toml".into()],&x.id).unwrap();assert_eq!(g.of("settings.toml",None),x.id);assert_eq!(g.of("new.toml",Some("settings.toml")),x.id);let bytes=serde_json::to_vec(&g).unwrap();let mut g:Groups=serde_json::from_slice(&bytes).unwrap();g.save(&x.id,"仅在本机").unwrap();assert_eq!(g.of("settings.toml",None),x.id);assert_eq!(g.of("new-file",None),DEFAULT);g.remove(&x.id).unwrap();assert_eq!(g.of("settings.toml",None),DEFAULT);}
}
