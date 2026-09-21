//! Resolve only POM-declared workspace modules inside the user's trusted project.
//! Maven, not this module, selects the active dependency graph with -pl / -am.
use crate::core::*;
use serde::Serialize;
use std::{collections::{BTreeMap,HashSet},path::{Path,PathBuf}};
use super::Launcher;

#[derive(Clone,Serialize)]
pub struct Plan {
 pub root:String, pub module:String, pub working_directory:String,
 pub modules:Vec<String>, pub multi_module:bool, pub warnings:Vec<String>,
}
fn relative(root:&Path,p:&Path)->Result<String>{
 let p=native_path(p.canonicalize()?);let r=native_path(root.canonicalize()?);
 let s=p.strip_prefix(&r).map_err(|_|Error("Maven 模块不能越过已信任的项目目录".into()))?.to_string_lossy().replace('\\',"/");
 Ok(if s.is_empty(){".".into()}else{s})
}
fn pom(path:&Path)->Result<String>{
 if path.metadata()?.len()>512*1024{return fail("pom.xml 超过 512 KiB，请使用高级自定义构建")}
 let text=std::fs::read_to_string(path)?;
 if text.contains("<!DOCTYPE"){return fail("不解析带外部实体声明的 pom.xml")}
 Ok(text)
}
fn expand(s:&str,props:&BTreeMap<String,String>)->Option<String>{
 let mut s=s.to_string();
 for _ in 0..12 {
  let Some(a)=s.find("${") else{return Some(s)};let b=s[a+2..].find('}')?+a+2;
  let v=props.get(&s[a+2..b])?;s.replace_range(a..=b,v);
  if s.len()>4096{return None}
 }
 None
}
fn walk(project:&Path,dir:&Path,props:&BTreeMap<String,String>,seen:&mut HashSet<PathBuf>,out:&mut Vec<PathBuf>,warnings:&mut Vec<String>)->Result<()> {
 if seen.len()>=256{return fail("Maven 工作区超过 256 个声明模块，请选择更小的聚合目录")}
 let dir=native_path(dir.canonicalize()?);
 relative(project,&dir)?;
 if !seen.insert(dir.clone()){return Ok(())}
 let text=pom(&dir.join("pom.xml"))?;
 let doc=roxmltree::Document::parse(&text).map_err(|e|Error(format!("pom.xml 解析失败：{e}")))?;
 let node=doc.root_element();if !node.has_tag_name("project"){return fail("不是 Maven project 文档")}
 let mut props=props.clone();
 for p in node.children().filter(|n|n.has_tag_name("properties")){for n in p.children().filter(|n|n.is_element()){if let Some(v)=n.text(){props.insert(n.tag_name().name().into(),v.trim().into());}}}
 out.push(dir.clone());
 // Include profile module declarations for membership discovery, but never
 // activate a profile here. Maven checks actual activation when executing -pl.
 for n in node.descendants().filter(|n|n.has_tag_name("module")&&n.parent().map(|p|p.has_tag_name("modules")).unwrap_or(false)) {
  let raw=n.text().unwrap_or("").trim();if raw.is_empty(){continue}
  let Some(rel)=expand(raw,&props)else{warnings.push(format!("无法静态解析模块声明 {raw}；可显式选择聚合目录并设置 Maven Profile"));continue};
  let path=dir.join(rel.replace('\\',"/"));
  if path.join("pom.xml").is_file(){walk(project,&path,&props,seen,out,warnings)?;}
 }
 Ok(())
}
pub fn resolve(project:&Path,module:&Path,l:&Launcher)->Result<Plan>{
 let project=native_path(project.canonicalize()?);let module=native_path(module.canonicalize()?);
 relative(&project,&module)?;if !module.join("pom.xml").is_file(){return fail("所选模块目录没有 pom.xml")}
 let mut chosen=module.clone();let mut modules=vec![module.clone()];let mut notes=vec![];
 if !l.maven_root.is_empty(){
  chosen=native_path(inside(&project,&l.maven_root)?.canonicalize()?);
  if !chosen.join("pom.xml").is_file(){return fail("所选 Maven 聚合目录没有 pom.xml")}
  modules.clear();walk(&project,&chosen,&Default::default(),&mut HashSet::new(),&mut modules,&mut notes)?;
  if !modules.contains(&module){return fail("所选聚合 POM 没有声明当前入口模块；未退回单模块启动")}
 }else{
  let mut at=Some(module.as_path());let mut depth=0;
  while let Some(d)=at {
   if !d.starts_with(&project){break}depth+=1;if depth>32{return fail("聚合目录向上查找超过 32 层，请显式选择 Maven 聚合目录")}
   if d.join("pom.xml").is_file(){
    let mut found=vec![];let mut warnings=vec![];
    walk(&project,d,&Default::default(),&mut HashSet::new(),&mut found,&mut warnings)?;
    if found.contains(&module){chosen=d.to_path_buf();modules=found;notes=warnings;}
   }
   if d==project{break}at=d.parent();
  }
 }
 let working=if l.working_directory.is_empty(){chosen.clone()}else{native_path(inside(&project,&l.working_directory)?.canonicalize()?)};
 if !working.is_dir(){return fail("应用工作目录不存在")}
 let multi=chosen!=module;
 Ok(Plan{root:relative(&project,&chosen)?,module:relative(&chosen,&module)?,working_directory:relative(&project,&working)?,modules:modules.iter().map(|p|relative(&project,p)).collect::<Result<_>>()?,multi_module:multi,warnings:notes})
}
impl Plan {
 pub fn common_args(&self,project:&Path,l:&Launcher)->Result<Vec<String>>{
  let mut a=vec!["--batch-mode".into(),"--no-transfer-progress".into(),"-f".into(),inside(project,&self.root)?.join("pom.xml").to_string_lossy().into_owned()];
  if self.multi_module{a.extend(["-pl".into(),self.module.clone()]);}
  if !l.maven_profiles.is_empty(){
   if l.maven_profiles.len()>32||l.maven_profiles.iter().any(|v|v.is_empty()||v.contains([',','\n','\r','\0'])){return fail("Maven Profile 每行一个，不能包含逗号或换行")}
   a.extend(["-P".into(),l.maven_profiles.join(",")]);
  }
  for(k,v)in &l.maven_properties{
   if k.is_empty()||k.len()>256||k.contains(['=','\n','\r','\0'])||v.len()>8192||v.contains('\0'){return fail("Maven 属性格式无效")}
   // Repository and settings must stay identical in build and run.
   if ["maven.repo.local","maven.multiModuleProjectDirectory","spring-boot.run.skip"].contains(&k.as_str()){return fail("此 Maven 属性由工作台管理，请使用对应的目录设置")}
   a.push(format!("-D{k}={v}"));
  }
  Ok(a)
 }
 pub fn watch_paths(&self,project:&Path)->Result<Vec<String>>{
  let mut out=vec![];
  for m in &self.modules{let d=inside(project,m)?;for sub in ["src","pom.xml"]{let p=d.join(sub);if p.exists(){out.push(relative(project,&p)?);}}}
  Ok(out)
 }
}
#[cfg(test)]mod tests{
 use super::*;
 fn put(p:&Path,text:&str){std::fs::create_dir_all(p.parent().unwrap()).unwrap();std::fs::write(p,text).unwrap();}
 #[test]fn nested_reactor_and_workdir(){let t=tempfile::tempdir().unwrap();let r=t.path();put(&r.join("workspace/pom.xml"),"<project><properties><part>modules</part></properties><modules><module>${part}</module><module>common</module></modules></project>");put(&r.join("workspace/modules/pom.xml"),"<project><modules><module>app</module></modules></project>");for p in ["workspace/modules/app","workspace/common"]{put(&r.join(p).join("pom.xml"),"<project/>");}let l=Launcher::default();let p=resolve(r,&r.join("workspace/modules/app"),&l).unwrap();assert_eq!(p.root,"workspace");assert_eq!(p.module,"modules/app");assert_eq!(p.working_directory,"workspace");assert!(p.multi_module);let args=p.common_args(r,&l).unwrap();assert!(args.windows(2).any(|a|a==["-pl","modules/app"]));}
 #[test]fn parent_without_aggregation_is_not_reactor(){let t=tempfile::tempdir().unwrap();put(&t.path().join("pom.xml"),"<project/>");put(&t.path().join("app/pom.xml"),"<project/>");let p=resolve(t.path(),&t.path().join("app"),&Launcher::default()).unwrap();assert!(!p.multi_module);assert_eq!(p.root,"app");}
 #[test]fn explicit_directory_and_profiles(){let t=tempfile::tempdir().unwrap();put(&t.path().join("pom.xml"),"<project><profiles><profile><modules><module>app</module></modules></profile></profiles></project>");put(&t.path().join("app/pom.xml"),"<project/>");let l=Launcher{maven_root:".".into(),working_directory:"app".into(),maven_profiles:vec!["local".into()],..Default::default()};let p=resolve(t.path(),&t.path().join("app"),&l).unwrap();assert_eq!(p.working_directory,"app");assert!(p.common_args(t.path(),&l).unwrap().windows(2).any(|a|a==["-P","local"]));}
 #[test]fn traversal_and_unknown_root_rejected(){let t=tempfile::tempdir().unwrap();put(&t.path().join("pom.xml"),"<project/>");put(&t.path().join("app/pom.xml"),"<project/>");for root in [".","../"]{let l=Launcher{maven_root:root.into(),..Default::default()};assert!(resolve(t.path(),&t.path().join("app"),&l).is_err());}}
}
