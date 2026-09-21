//! Local persistent changelists, independent of .gitignore / svn:ignore.
use crate::core::*;
use serde::{Serialize,Deserialize};
use std::collections::BTreeMap;
pub const DEFAULT:&str="default";
#[derive(Clone,Serialize,Deserialize)]pub struct Group{pub id:String,pub name:String}
#[derive(Clone,Serialize,Deserialize)]#[serde(default)]
pub struct Groups{pub items:Vec<Group>,pub assignments:BTreeMap<String,String>,pub revision:u64}
impl Default for Groups{fn default()->Self{Self{items:vec![Group{id:DEFAULT.into(),name:"默认".into()}],assignments:BTreeMap::new(),revision:0}}}
impl Groups{
 pub fn of<'a>(&'a self,path:&str,original:Option<&str>)->&'a str{self.assignments.get(path).or_else(||original.and_then(|p|self.assignments.get(p))).map(String::as_str).filter(|id|self.items.iter().any(|g|g.id==*id)).unwrap_or(DEFAULT)}
 pub fn name(&self,id:&str)->Result<&str>{self.items.iter().find(|g|g.id==id).map(|g|g.name.as_str()).ok_or_else(||Error("分组已不存在，请刷新".into()))}
 pub fn save(&mut self,group_id:&str,name:&str)->Result<Group>{
  let name=name.trim();text(name,120)?;if group_id==DEFAULT{return fail("默认分组不可重命名")};
  if self.items.iter().any(|g|g.name==name&&g.id!=group_id){return fail("分组名称已存在")};
  if group_id.is_empty(){if self.items.len()>=64{return fail("每个仓库最多 64 个分组")};let g=Group{id:id(),name:name.into()};self.items.push(g.clone());self.revision+=1;Ok(g)}
  else{let g=self.items.iter_mut().find(|g|g.id==group_id).ok_or_else(||Error("分组不存在".into()))?;g.name=name.into();self.revision+=1;Ok(g.clone())}
 }
 pub fn remove(&mut self,id:&str)->Result<()>{if id==DEFAULT{return fail("默认分组不可删除")};self.name(id)?;self.items.retain(|g|g.id!=id);self.assignments.retain(|_,g|g!=id);self.revision+=1;Ok(())}
 pub fn set(&mut self,paths:&[String],id:&str)->Result<()>{self.name(id)?;if self.assignments.len()+paths.iter().filter(|p|!self.assignments.contains_key(*p)).count()>20000{return fail("已记忆的文件分组达到 20000 条上限")};for p in paths{self.assignments.insert(p.clone(),id.into());}self.revision+=1;Ok(())}
}
#[cfg(test)]mod tests{
 use super::*;
 #[test]fn remembers_clean_and_renamed_paths(){let mut g=Groups::default();let x=g.save("","忽略不提交").unwrap();g.set(&["settings.toml".into()],&x.id).unwrap();assert_eq!(g.of("settings.toml",None),x.id);assert_eq!(g.of("new.toml",Some("settings.toml")),x.id);let bytes=serde_json::to_vec(&g).unwrap();let mut g:Groups=serde_json::from_slice(&bytes).unwrap();g.save(&x.id,"仅在本机").unwrap();assert_eq!(g.of("settings.toml",None),x.id);assert_eq!(g.of("new-file",None),DEFAULT);g.remove(&x.id).unwrap();assert_eq!(g.of("settings.toml",None),DEFAULT);}
}
