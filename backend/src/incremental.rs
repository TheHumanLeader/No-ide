//! Persistent content-addressed module-level Maven builds.
//! Recompile changed modules and downstream consumers; reuse unchanged upstream
//! artifacts. No Java ABI guessing, no timestamp-only freshness decisions.
use crate::{core::*, launch::maven, process, runtime::{capture_build, Hub}};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{collections::{BTreeMap, BTreeSet}, io::{Read, Write}, path::{Path, PathBuf}, sync::Arc};
use tokio::time::Instant;
const SCHEMA: u32 = 1;
const MAX_FILES: usize = 200_000;
const MAX_BYTES: u64 = 4 * 1024 * 1024 * 1024;
const HELP: &str = "org.apache.maven.plugins:maven-help-plugin:3.5.1";
const DEPS: &str = "org.apache.maven.plugins:maven-dependency-plugin:3.8.1:build-classpath";
const CP_FILE: &str = "target/no-ide-incremental-classpath.txt";
#[derive(Clone, Serialize, Deserialize)]
struct Module { path:String, selector:String, gav:String, artifact:String, packaging:String, inputs:Vec<PathBuf>, output:PathBuf, artifact_dir:PathBuf, deps:Vec<usize> }
#[derive(Clone, Serialize, Deserialize, Default, PartialEq)]
struct Stamp { input:String, output:String }
#[derive(Clone, Serialize, Deserialize)]
struct Record { schema:u32, context:String, modules:Vec<Module>, stamps:Vec<Stamp>, dirty:BTreeSet<usize>, external:Vec<PathBuf>, external_hash:String, opaque:Vec<String> }
#[derive(Clone, Serialize, Deserialize)]
pub struct Report { pub mode:String, pub selected:Vec<String>, pub reused:Vec<String>, pub reason:String, pub elapsed_ms:u128 }
#[derive(Default)]struct Budget {files:usize,bytes:u64}
fn hbytes(bytes:&[u8])->String{format!("{:x}",Sha256::digest(bytes))}
fn finish(h:Sha256)->String{format!("{:x}",h.finalize())}
fn part(h:&mut Sha256,bytes:&[u8]){h.update((bytes.len() as u64).to_le_bytes());h.update(bytes);}
fn read_xml(path:&Path)->Result<String>{if path.metadata()?.len()>16*1024*1024{return fail("Maven 模型超过 16 MiB，未使用不完整模型跳过构建")}let s=std::fs::read_to_string(path)?;if s.contains("<!DOCTYPE"){return fail("不解析带外部实体的 Maven 模型")}Ok(s)}
fn hash_path(path:&Path,h:&mut Sha256,budget:&mut Budget,depth:usize)->Result<()>{
 if depth>64{return fail("构建指纹目录超过 64 层，未跳过构建")}
 part(h,path.to_string_lossy().as_bytes());
 let meta=match std::fs::symlink_metadata(path){Ok(m)=>m,Err(e)if e.kind()==std::io::ErrorKind::NotFound=>{part(h,b"missing");return Ok(())},Err(e)=>return Err(e.into())};
 if meta.file_type().is_symlink(){return fail(format!("构建输入或输出含符号链接：{}；当前不缓存该布局",path.display()))}
 budget.files+=1;if budget.files>MAX_FILES{return fail("构建指纹超过 200000 项，未使用截断结果")}
 if meta.is_dir(){part(h,b"directory");let mut entries=std::fs::read_dir(path)?.collect::<std::io::Result<Vec<_>>>()?;entries.sort_by_key(|e|e.file_name());for e in entries{if [".git",".svn","node_modules","__pycache__"].iter().any(|n|e.file_name()==*n){continue}hash_path(&e.path(),h,budget,depth+1)?;}}
 else if meta.is_file(){part(h,b"file");let mut f=std::fs::File::open(path)?;let mut buf=[0u8;65536];let mut own=Sha256::new();loop{let n=f.read(&mut buf)?;if n==0{break}budget.bytes+=n as u64;if budget.bytes>MAX_BYTES{return fail("构建指纹读取超过 4 GiB，未跳过构建")}own.update(&buf[..n]);}part(h,&own.finalize());}
 else{return fail("构建指纹不读取设备或管道")}
 Ok(())
}
fn paths_hash(paths:&[PathBuf])->Result<String>{let mut paths=paths.to_vec();paths.sort();paths.dedup();let mut h=Sha256::new();let mut budget=Budget::default();for p in paths{hash_path(&p,&mut h,&mut budget,0)?;}Ok(finish(h))}
fn artifacts(dir:&Path)->Result<Vec<PathBuf>>{if !dir.exists(){return Ok(vec![dir.to_path_buf()])}let mut v=vec![];for e in std::fs::read_dir(dir)?{let p=e?.path();if matches!(p.extension().and_then(|s|s.to_str()),Some("jar"|"pom"|"war")){v.push(p);}}if v.is_empty(){v.push(dir.join(".no-ide-missing-artifact"));}v.sort();Ok(v)}
fn stamps(modules:&[Module])->Result<Vec<Stamp>>{modules.iter().map(|m|{let mut output=vec![m.output.clone()];output.extend(artifacts(&m.artifact_dir)?);Ok(Stamp{input:paths_hash(&m.inputs)?,output:paths_hash(&output)?})}).collect()}
fn xml_child<'a,'d>(n:roxmltree::Node<'a,'d>,name:&str)->Option<roxmltree::Node<'a,'d>>{n.children().find(|n|n.has_tag_name(name))}
fn text_at(n:roxmltree::Node,path:&[&str])->String{let mut at=n;for name in path{let Some(next)=xml_child(at,name)else{return String::new()};at=next;}at.text().unwrap_or("").trim().to_string()}
fn gav(n:roxmltree::Node)->String{["groupId","artifactId","version"].iter().map(|k|text_at(n,&[k])).collect::<Vec<_>>().join(":")}
fn checked_coord(s:&str)->Result<()>{if s.is_empty()||s.contains("${")||!s.chars().all(|c|c.is_alphanumeric()||".-_".contains(c)){return fail("Maven 坐标无法安全映射到本地仓库，未缓存本次构建")}Ok(())}
fn input_path(root:&Path,module:&Path,value:&str)->Result<PathBuf>{
 if value.is_empty()||value.contains("${"){return fail("Maven 有尚未解析的输入目录，未跳过构建")}
 let p=PathBuf::from(value);let p=if p.is_absolute(){p}else{module.join(p)};let p=native_path(p);
 let rel=p.strip_prefix(root).map_err(|_|Error(format!("构建输入越出已信任的项目：{}",p.display())))?;
 inside(root,&rel.to_string_lossy())
}
fn parse_model(xml:&str,root:&Path,plan:&maven::Plan,repository:&Path)->Result<(Vec<Module>,Vec<String>)>{
 let doc=roxmltree::Document::parse(xml).map_err(|e|Error(e.to_string()))?;
 let nodes:Vec<_>=if doc.root_element().has_tag_name("project"){vec![doc.root_element()]}else{doc.root_element().children().filter(|n|n.has_tag_name("project")).collect()};
 if nodes.is_empty()||nodes.len()>256{return fail("Maven 没有返回完整的有效模块模型")}
 let mut names:BTreeMap<String,Vec<String>>=BTreeMap::new();
 for p in &plan.modules{let xml=read_xml(&inside(root,p)?.join("pom.xml"))?;let d=roxmltree::Document::parse(&xml).map_err(|e|Error(e.to_string()))?;names.entry(text_at(d.root_element(),&["artifactId"])).or_default().push(p.clone());}
 let mut modules=vec![];let mut all_refs=vec![];let mut opaque=vec![];
 for n in nodes{
  let artifact=text_at(n,&["artifactId"]);let candidates=names.get(&artifact).ok_or_else(||Error("有效 POM 无法对应当前磁盘模块，未跳过构建".into()))?;
  if candidates.len()!=1{return fail("多个模块的 artifactId 相同，当前不能安全缓存")}
  let path=candidates[0].clone();let dir=inside(root,&path)?;let reactor=inside(root,&plan.root)?;
  let sel=dir.strip_prefix(&reactor).map_err(|_|Error("有效模块不在聚合目录中".into()))?.to_string_lossy().replace('\\',"/");let selector=if sel.is_empty(){".".into()}else{sel};
  let packaging={let p=text_at(n,&["packaging"]);if p.is_empty(){"jar".into()}else{p}};
  if !["jar","pom"].contains(&packaging.as_str()){opaque.push(format!("{} 的 {} 打包类型未启用模块缓存",artifact,packaging));}
  let mut inputs=vec![dir.join("pom.xml")];
  for field in ["sourceDirectory","testSourceDirectory"]{let p=text_at(n,&["build",field]);if !p.is_empty(){inputs.push(input_path(root,&dir,&p)?);}}
  if let Some(build)=xml_child(n,"build"){
   for collection in ["resources","testResources"]{if let Some(rs)=xml_child(build,collection){for r in rs.children().filter(|r|r.is_element()){let p=text_at(r,&["directory"]);if !p.is_empty(){inputs.push(input_path(root,&dir,&p)?);}}}}
   if let Some(filters)=xml_child(build,"filters"){for f in filters.children().filter(|x|x.is_element()){if let Some(p)=f.text(){inputs.push(input_path(root,&dir,p.trim())?);}}}
   if xml_child(build,"extensions").map(|e|e.children().any(|n|n.is_element())).unwrap_or(false){opaque.push("构建扩展可能有未声明输入".into());}
   if let Some(plugins)=xml_child(build,"plugins"){for plugin in plugins.children().filter(|n|n.has_tag_name("plugin")){
    let a=text_at(plugin,&["artifactId"]);let g=text_at(plugin,&["groupId"]);
    let standard=(g.is_empty()||g=="org.apache.maven.plugins")&&["maven-clean-plugin","maven-resources-plugin","maven-compiler-plugin","maven-surefire-plugin","maven-failsafe-plugin","maven-jar-plugin","maven-install-plugin","maven-deploy-plugin","maven-site-plugin"].contains(&a.as_str());
    if a=="maven-compiler-plugin"&&plugin.descendants().any(|n|n.has_tag_name("annotationProcessorPaths")){opaque.push(format!("{} 显式注解处理器路径尚未纳入复用模型",artifact));}
    let spring=g=="org.springframework.boot"&&a=="spring-boot-maven-plugin";
    let bound=xml_child(plugin,"executions").map(|x|x.children().any(|n|n.is_element())).unwrap_or(false);
    if bound&&!standard&&!spring{opaque.push(format!("{} 的插件 {} 有自定义生命周期输入，保守构建",artifact,a));}
   }}
  }
  let output=input_path(root,&dir,&text_at(n,&["build","outputDirectory"]))?;
  let g=text_at(n,&["groupId"]);let v=text_at(n,&["version"]);checked_coord(&g)?;checked_coord(&artifact)?;checked_coord(&v)?;
  let artifact_dir=repository.join(g.replace('.',"/")).join(&artifact).join(v);let mut refs=vec![];
  if let Some(ds)=xml_child(n,"dependencies"){for d in ds.children().filter(|n|n.has_tag_name("dependency")){refs.push(gav(d));}}
  if let Some(parent)=xml_child(n,"parent"){refs.push(gav(parent));}
  if let Some(build)=xml_child(n,"build"){for x in build.descendants().filter(|x|x.has_tag_name("plugin")||x.has_tag_name("extension")||x.has_tag_name("dependency")){refs.push(gav(x));}}
  all_refs.push(refs);modules.push(Module{path,selector,gav:gav(n),artifact,packaging,inputs,output,artifact_dir,deps:vec![]});
 }
 let ids:BTreeMap<_,_>=modules.iter().enumerate().map(|(i,m)|(m.gav.clone(),i)).collect();if ids.len()!=modules.len(){return fail("有效 Maven 模型存在重复坐标，未跳过构建")}
 for(i,refs)in all_refs.iter().enumerate(){modules[i].deps=refs.iter().filter_map(|g|ids.get(g).copied()).filter(|j|*j!=i).collect();modules[i].deps.sort();modules[i].deps.dedup();}
 opaque.sort();opaque.dedup();Ok((modules,opaque))
}
fn load(path:&Path)->Option<Record>{let meta=path.metadata().ok()?;if meta.len()>16*1024*1024{return None}let r:Record=serde_json::from_slice(&std::fs::read(path).ok()?).ok()?;(r.schema==SCHEMA&&r.modules.len()==r.stamps.len()&&r.modules.len()<=256).then_some(r)}
fn save(path:&Path,r:&Record)->Result<()>{let parent=path.parent().ok_or_else(||Error("无构建缓存目录".into()))?;std::fs::create_dir_all(parent)?;let mut f=tempfile::NamedTempFile::new_in(parent)?;f.write_all(&serde_json::to_vec(r)?)?;f.as_file().sync_all()?;f.persist(path).map_err(|e|Error(e.to_string()))?;Ok(())}
fn context(root:&Path,cfg:&RunConfig,plan:&maven::Plan,store:&Store)->Result<String>{
 let mut paths=vec![];for m in &plan.modules{let d=inside(root,m)?;paths.push(d.join("pom.xml"));paths.push(d.join(".mvn"));}
 if let Some(h)=dirs::home_dir(){paths.push(h.join(".m2/settings.xml"));paths.push(h.join(".m2/toolchains.xml"));}
 for key in ["maven_settings"]{if let Some(p)=store.build_tools.get(key){paths.push(PathBuf::from(p));}}
 let b=cfg.build.as_ref().unwrap();
 if Path::new(&b.program).is_file(){paths.push(PathBuf::from(&b.program));if let Some(home)=Path::new(&b.program).parent().and_then(|p|p.parent()){paths.push(home.join("conf/settings.xml"));if let Ok(lib)=std::fs::canonicalize(home.join("lib")){for e in std::fs::read_dir(lib)?{let path=e?.path();if path.is_file(){paths.push(native_path(path.canonicalize()?));}}}}}
 if let Some(home)=cfg.env.get("JAVA_HOME"){paths.push(Path::new(home).join("release"));paths.push(Path::new(home).join(if cfg!(windows){"bin/java.exe"}else{"bin/java"}));}
 let mut env:BTreeMap<String,String>=std::env::vars().collect();env.extend(cfg.env.clone());
 // Environment values contribute only to a digest, never persisted or logged.
 Ok(hbytes(&serde_json::to_vec(&(SCHEMA,root,b,paths_hash(&paths)?,env))?))
}
fn metadata_command(build:&CommandSpec,goal:&str,output:&Path)->CommandSpec{let mut c=build.clone();c.args.retain(|a|!["clean","install","compile","-DskipTests"].contains(&a.as_str()));c.args.push(format!("{HELP}:{goal}"));c.args.push(format!("-Doutput={}",output.display()));c}
async fn execute(c:&CommandSpec,cfg:&RunConfig,root:&Path,hub:Arc<Hub>)->Result<()>{let command=process::command(c,&inside(root,&cfg.cwd)?,None,&[],&cfg.env)?;process::checked(capture_build(command,900,hub,cfg.id.clone(),cfg.output_encoding).await?)?;Ok(())}
async fn model(root:&Path,cfg:&RunConfig,plan:&maven::Plan,hub:Arc<Hub>)->Result<(Vec<Module>,Vec<String>)>{
 let temp=tempfile::tempdir()?;let effective=temp.path().join("effective.xml");let settings=temp.path().join("settings.xml");
 execute(&metadata_command(cfg.build.as_ref().unwrap(),"effective-pom",&effective),cfg,root,hub.clone()).await?;
 execute(&metadata_command(cfg.build.as_ref().unwrap(),"effective-settings",&settings),cfg,root,hub).await?;
 let sx=read_xml(&settings)?;let d=roxmltree::Document::parse(&sx).map_err(|e|Error(e.to_string()))?;
 let override_repo=cfg.build.as_ref().unwrap().args.iter().rev().find_map(|a|a.strip_prefix("-Dmaven.repo.local="));
 let repo=PathBuf::from(override_repo.map(str::to_owned).unwrap_or_else(||text_at(d.root_element(),&["localRepository"])));
 if !repo.is_absolute(){return fail("Maven 没有返回绝对本地仓库目录，未缓存本次构建")}
 parse_model(&read_xml(&effective)?,root,plan,&native_path(repo))
}
fn downstream(modules:&[Module],mut changed:BTreeSet<usize>)->BTreeSet<usize>{loop{let before=changed.len();for(i,m)in modules.iter().enumerate(){if m.deps.iter().any(|d|changed.contains(d)){changed.insert(i);}}if before==changed.len(){return changed}}}
fn subset(build:&CommandSpec,modules:&[Module],selected:&BTreeSet<usize>)->CommandSpec{let mut c=build.clone();let mut args=vec![];let mut skip=false;for a in &c.args{if skip{skip=false;continue}if a=="-pl"||a=="--projects"{skip=true;continue}if a=="--also-make"||a=="-am"{continue}args.push(a.clone());}args.extend(["-pl".into(),selected.iter().map(|i|modules[*i].selector.clone()).collect::<Vec<_>>().join(",")]);c.args=args;c}
async fn dependency_paths(root:&Path,cfg:&RunConfig,modules:&[Module],hub:Arc<Hub>)->Result<Vec<PathBuf>>{
 let mut c=cfg.build.clone().unwrap();c.args.retain(|a|!["clean","install","compile","-DskipTests"].contains(&a.as_str()));
 c.args.extend([DEPS.into(),format!("-Dmdep.outputFile={CP_FILE}"),"-Dmdep.pathSeparator=|".into(),"-DincludeScope=test".into(),"-DoutputEncoding=UTF-8".into(),"-Dmdep.regenerateFile=true".into()]);execute(&c,cfg,root,hub).await?;
 let mut paths=BTreeSet::new();for m in modules{let file=inside(root,&m.path)?.join(CP_FILE);if !file.exists(){if m.packaging=="pom"{continue}else{return fail("Maven 未返回模块依赖清单，未记录成功缓存")}}let raw=std::fs::read_to_string(file)?;if raw.len()>2*1024*1024{return fail("模块依赖清单过大")}
 for path in raw.trim().split('|').filter(|s|!s.is_empty()){let p=native_path(PathBuf::from(path));if !p.is_absolute(){return fail("Maven 依赖清单含相对路径")}if modules.iter().any(|m|p.starts_with(&m.artifact_dir)){continue}if let Some(parent)=p.parent(){paths.extend(artifacts(parent)?);}else{paths.insert(p);}}}
 if paths.len()>20000{return fail("依赖清单过大，未记录截断的构建缓存")}Ok(paths.into_iter().collect())
}
/// Caller owns both the Maven semaphore and the cancellation scope.
pub async fn build(project:&Project,original:&RunConfig,cfg:&RunConfig,store:&Store,cache:&Path,force:bool,hub:Arc<Hub>)->Result<bool>{
 let started=Instant::now();let root=project.root.clone();let original_cwd=inside(&root,&original.cwd)?;
 let plan=maven::resolve(&root,&original_cwd,original.launcher.as_ref().unwrap())?;
 let path=cache.join(format!("{}.json",hbytes(format!("{}\0{}\0{}",root.display(),project.id,original.id).as_bytes())));
 if force&&path.exists(){std::fs::remove_file(&path)?;}
 let prepared=async{
  let ctx={let r=root.clone();let c=cfg.clone();let p=plan.clone();let s=store.clone();tokio::task::spawn_blocking(move||context(&r,&c,&p,&s)).await.map_err(|e|Error(e.to_string()))??};
  let old=load(&path).filter(|r|r.context==ctx);
  let mut reason=if force{"手动清理重建"}else if old.is_none(){"首次建立可信构建基线，或 POM / JDK / Maven / 构建环境已改变"}else{"比较本地源码及产物内容"}.to_string();let mut full=force||old.is_none();
  let mut record=match old{Some(r)=>r,None=>{hub.log(&cfg.id,"build-plan","正在读取 Maven 有效模块模型；仅在首次或构建配置变化时执行，不修改项目 POM。").await;let(modules,opaque)=model(&root,cfg,&plan,hub.clone()).await?;Record{schema:SCHEMA,context:ctx.clone(),stamps:vec![Stamp::default();modules.len()],modules,dirty:BTreeSet::new(),external:vec![],external_hash:String::new(),opaque}}};
  let dep_changed=if !full{let paths=record.external.clone();let hash=tokio::task::spawn_blocking(move||paths_hash(&paths)).await.map_err(|e|Error(e.to_string()))??;hash!=record.external_hash}else{false};
  if dep_changed{let(modules,opaque)=model(&root,cfg,&plan,hub.clone()).await?;record.modules=modules;record.opaque=opaque;record.stamps=vec![Stamp::default();record.modules.len()];full=true;reason="已解析的本地依赖文件发生变化，重新确认模型和构建范围".into();}
  if !record.opaque.is_empty(){full=true;reason=record.opaque.join("；");}
  let modules=record.modules.clone();let before=tokio::task::spawn_blocking(move||stamps(&modules)).await.map_err(|e|Error(e.to_string()))??;
  let dirty:BTreeSet<_>=if full{(0..record.modules.len()).collect()}else{before.iter().enumerate().filter_map(|(i,s)|(record.dirty.contains(&i)||s!=&record.stamps[i]).then_some(i)).collect()};
  let selected=downstream(&record.modules,dirty);Ok::<_,Error>((ctx,record,before,selected,full,reason))
 }.await;
 let(ctx,mut record,before,selected,full,reason)=match prepared{Ok(p)=>p,Err(e)=>{
  // No compiler has run yet. A failed metadata probe is not a cache hit.
  if path.exists(){std::fs::remove_file(&path)?;}
  hub.log(&cfg.id,"build-plan",&format!("增量模型暂不可用：{}。保守执行原构建范围；未把未知状态当作最新。",e.0)).await;
  execute(cfg.build.as_ref().unwrap(),cfg,&root,hub.clone()).await?;
  hub.log(&cfg.id,"build-selection",&serde_json::to_string(&Report{mode:"fallback".into(),selected:plan.modules.clone(),reused:vec![],reason:e.0,elapsed_ms:started.elapsed().as_millis()})?).await;return Ok(true)
 }};
 let report=Report{mode:if selected.is_empty(){"reuse"}else if full{"baseline"}else{"incremental"}.into(),selected:selected.iter().map(|i|record.modules[*i].path.clone()).collect(),reused:record.modules.iter().enumerate().filter(|(i,_)|!selected.contains(i)).map(|(_,m)|m.path.clone()).collect(),reason:reason.clone(),elapsed_ms:started.elapsed().as_millis()};
 hub.log(&cfg.id,"build-selection",&serde_json::to_string(&report)?).await;
 if selected.is_empty(){hub.log(&cfg.id,"build-plan",&format!("本地源码与产物指纹一致：复用 {} 个模块，跳过构建阶段。检查耗时 {} ms。应用仍按既定启动方式运行。",record.modules.len(),started.elapsed().as_millis())).await;return Ok(false)}
 hub.log(&cfg.id,"build-plan",&format!("{}：本次重编 {} / {} 个模块 [{}]；复用 {} 个模块。仅清理所选模块，确保已删除类、内部类和资源不残留。",reason,selected.len(),record.modules.len(),report.selected.join(", "),report.reused.len())).await;
 // Durable dirty record precedes the compiler; failed/cancelled writes never
 // become a successful cache just because output files happen to be present.
 record.dirty.extend(selected.iter().copied());save(&path,&record)?;
 let command=if full{cfg.build.clone().unwrap()}else{subset(cfg.build.as_ref().unwrap(),&record.modules,&selected)};
 execute(&command,cfg,&root,hub.clone()).await?;
 if full{record.external=dependency_paths(&root,cfg,&record.modules,hub.clone()).await?;}
 let modules=record.modules.clone();let after=tokio::task::spawn_blocking(move||stamps(&modules)).await.map_err(|e|Error(e.to_string()))??;
 if before.iter().zip(&after).any(|(a,b)|a.input!=b.input){return fail("构建期间源码又发生变化，未标记为最新，也未启动新版本；修改稳定后请再次应用改动")}
 let r=root.clone();let c=cfg.clone();let p=plan.clone();let s=store.clone();let after_ctx=tokio::task::spawn_blocking(move||context(&r,&c,&p,&s)).await.map_err(|e|Error(e.to_string()))??;
 if after_ctx!=ctx{return fail("构建期间 POM 或环境发生变化，未启动可能混合的新版本")}
 let external=record.external.clone();record.external_hash=tokio::task::spawn_blocking(move||paths_hash(&external)).await.map_err(|e|Error(e.to_string()))??;
 record.stamps=after;record.dirty.clear();save(&path,&record)?;
 hub.log(&cfg.id,"build-plan",&format!("构建及内容复核完成：重编 {} 个、复用 {} 个，总耗时 {} ms；成功指纹已保存在本机，停止或退出后继续复用。",selected.len(),report.reused.len(),started.elapsed().as_millis())).await;Ok(true)
}
#[cfg(test)]mod tests{
 use super::*;
 fn module(name:&str,deps:Vec<usize>)->Module{Module{path:name.into(),selector:name.into(),gav:name.into(),artifact:name.into(),packaging:"jar".into(),inputs:vec![],output:PathBuf::new(),artifact_dir:PathBuf::new(),deps}}
 #[test]fn impact_is_downstream_not_upstream(){let m=vec![module("base",vec![]),module("business",vec![0]),module("app",vec![1]),module("unrelated",vec![])];assert_eq!(downstream(&m,[1].into()),[1,2].into());assert_eq!(downstream(&m,[2].into()),[2].into());}
 #[test]fn hash_is_content_and_names_not_timestamp(){let t=tempfile::tempdir().unwrap();std::fs::write(t.path().join("a"),"old").unwrap();let a=paths_hash(&[t.path().into()]).unwrap();std::fs::write(t.path().join("a"),"new").unwrap();assert_ne!(a,paths_hash(&[t.path().into()]).unwrap());std::fs::remove_file(t.path().join("a")).unwrap();assert_ne!(a,paths_hash(&[t.path().into()]).unwrap());}
 #[test]fn targeted_command_does_not_reintroduce_upstream(){let c=CommandSpec{program:"mvn".into(),args:vec!["-f".into(),"pom.xml".into(),"-pl".into(),"app".into(),"--also-make".into(),"clean".into(),"install".into()]};let out=subset(&c,&[module("a",vec![]),module("app",vec![0])],&[1].into());assert!(!out.args.contains(&"--also-make".into()));assert!(out.args.ends_with(&["-pl".into(),"app".into()]));}
}
