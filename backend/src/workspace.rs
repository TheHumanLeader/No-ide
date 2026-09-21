//! v0.4 API operations: SDK registry, static discovery, safe native browsing, changelists.
use crate::{App,core::*,environments,discovery,launch};
use serde_json::{json,Value};
use std::{sync::Arc,path::Path};

pub async fn dispatch(s:&Arc<App>,action:&str,v:&Value)->Result<Option<Value>>{
 let value=match action {
  "build_tools.detect"=>{
   let store=s.store.lock().await.clone();let(a,b)=tokio::join!(launch::tools::report(&store,"maven"),launch::tools::report(&store,"gradle"));json!({"maven":a,"gradle":b})
  },
  "build_tools.save"=>{
   let kind=crate::string(v,"kind")?;if !["maven","gradle","maven_settings","maven_repository"].contains(&kind){return fail("未知构建工具设置")};let path=crate::string(v,"path")?;
   let _w=s.writes.lock().await;let snapshot=s.store.lock().await.clone();
   let value=if path.is_empty(){None}else if kind=="maven_settings"||kind=="maven_repository"{Some(launch::tools::option_path(path,kind=="maven_settings")?)}else{launch::tools::verify(&snapshot,kind,Path::new(path)).await?;Some(launch::tools::program_in(kind,Path::new(path))?.to_string_lossy().into_owned())};
   for p in &snapshot.projects{s.runtime.forget_idle(p).await?;}
   let mut store=s.store.lock().await;let mut next=store.clone();if let Some(p)=value{next.build_tools.insert(kind.into(),p);}else{next.build_tools.remove(kind);}next.save(&s.file)?;*store=next;json!({"saved":true})
  },
  "environments.detect"=>{
   let mut d=environments::discover().await;
   if let Some(pid)=v["project"].as_str(){let p=s.store.lock().await.project(pid)?;for n in [".venv","venv"]{let path=p.root.join(n);if path.join("pyvenv.cfg").is_file(){if let Ok(e)=environments::verify("python",&path).await{if !d.candidates.iter().any(|c|c.program==e.program){d.candidates.push(e);}}}}}
   json!(d)
  },
  "environments.save"=>{
   let kind=crate::string(v,"kind")?;let path=crate::string(v,"path")?;
   let mut e=environments::verify(kind,Path::new(path)).await?;
   if let Some(name)=v["name"].as_str().filter(|s|!s.trim().is_empty()){text(name,100)?;e.name=name.trim().into();}
   let _w=s.writes.lock().await;let mut store=s.store.lock().await;let mut next=store.clone();
   if v["id"].as_str().filter(|s|!s.is_empty()).is_some()||v["default"].as_bool().unwrap_or(false){for p in &next.projects{s.runtime.forget_idle(p).await?;}}
   if let Some(eid)=v["id"].as_str().filter(|x|!x.is_empty()) {
    let old=next.environments.iter_mut().find(|x|x.id==eid).ok_or_else(||Error("环境不存在".into()))?;if old.kind!=kind{return fail("不能修改环境类型，请新增一个环境")};e.id=eid.into();*old=e.clone();
   }else if let Some(old)=next.environments.iter().find(|x|x.kind==kind&&x.program==e.program){e=old.clone();}
   else {if next.environments.len()>=64{return fail("最多添加 64 个运行环境")};e.id=id();next.environments.push(e.clone());}
   if v["default"].as_bool().unwrap_or(false)||!next.environment_defaults.contains_key(kind){next.environment_defaults.insert(kind.into(),e.id.clone());}
   next.save(&s.file)?;*store=next;json!(e)
  },
  "environments.remove"=>{
   crate::confirm(v)?;let eid=crate::string(v,"id")?;let _w=s.writes.lock().await;let mut store=s.store.lock().await;let mut next=store.clone();
   if next.projects.iter().any(|p|p.configs.iter().any(|c|c.environment_id.as_deref()==Some(eid))||p.instances.iter().any(|i|i.environment_id.as_deref()==Some(eid))){return fail("此环境仍被运行配置或实例引用，请先改选其他环境")};
   for p in &next.projects{if s.runtime.project_active(p).await{return fail("删除环境前请停止运行中的实例")};s.runtime.forget_idle(p).await?;}
   next.environments.retain(|e|e.id!=eid);next.environment_defaults.retain(|_,v|v!=eid);next.save(&s.file)?;*store=next;json!({"saved":true})
  },
  "project.discover"=>{
   let p=s.store.lock().await.project(crate::string(v,"project")?)?;let sub=v["directory"].as_str().unwrap_or(".").to_string();
   json!(tokio::task::spawn_blocking(move||discovery::scan(&p.root,&sub)).await.map_err(|e|Error(e.to_string()))??)
  },
  "project.relative"=>{
   let p=s.store.lock().await.project(crate::string(v,"project")?)?;let path=Path::new(crate::string(v,"path")?).canonicalize()?;let root=p.root.canonicalize()?;
   let relative=path.strip_prefix(&root).map_err(|_|Error("所选目录/文件必须在当前项目内部；外部目录请另建项目".into()))?;
   let rel=relative.to_string_lossy().replace('\\',"/");json!({"path":if rel.is_empty(){"."}else{&rel}})
  },
  "launch.preview"=>{
   let store=s.store.lock().await.clone();let p=store.project(crate::string(v,"project")?)?;let mut c:RunConfig=crate::val(&v["config"])?;if c.id.is_empty(){c.id="preview".into();}
   let resolved=launch::resolve(&store,&p,&c,None,false)?;
   json!({"command":resolved.command,"build":resolved.build,"cwd":c.cwd,"java_home":resolved.env.get("JAVA_HOME")})
  },
  "vcs.group.save"|"vcs.group.move"|"vcs.group.delete"=>{
   // Grouping changes only local metadata. No client lookup, status or diff subprocess.
   let _write=s.writes.lock().await;let mut store=s.store.lock().await;let mut next=store.clone();let p=next.project(crate::string(v,"project")?)?;
   let rid=crate::string(v,"repo")?;let target=next.projects.iter_mut().find(|x|x.id==p.id).unwrap().repos.iter_mut().find(|x|x.id==rid).ok_or_else(||Error("仓库不存在".into()))?;
   if let Some(expected)=v["revision"].as_u64(){if expected!=target.groups.revision{return fail("分组已被其他窗口修改，请刷新后再试；此次没有移动文件")}}
   if !target.path.canonicalize()?.starts_with(p.root.canonicalize()?){return fail("仓库路径已越过项目目录")}
   let gid=v["group"].as_str().unwrap_or("");
   match action {
    "vcs.group.save"=>{target.groups.save(gid,crate::string(v,"name")?)?;},
    "vcs.group.delete"=>{crate::confirm(v)?;target.groups.remove(gid)?;},
    _=>{let paths:Vec<String>=crate::val(&v["paths"])?;if paths.is_empty()||paths.len()>2000{return fail("一次请选择 1～2000 个文件移动分组")};
     let mut unique=std::collections::BTreeSet::new();for path in paths{vcs_path(&target.path,&path)?;unique.insert(path);}
     target.groups.set(&unique.into_iter().collect::<Vec<_>>(),gid)?;
    }
   }
   let result=json!(target.groups);next.save(&s.file)?;*store=next;result
  },
  _=>return Ok(None)
 };
 Ok(Some(value))
}
