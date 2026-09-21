//! Bounded discovery of installed Maven / Gradle. Does not download or install tools.
use crate::{core::*,environments,process};
use serde::Serialize;
use std::{collections::HashSet,path::{Path,PathBuf}};
use tokio::process::Command;
#[derive(Clone,Serialize)]pub struct Found{pub path:String,pub source:String}
#[derive(Serialize,Default)]pub struct Report{pub selected:Option<Found>,pub candidates:Vec<Found>,pub version:Option<String>,pub error:Option<String>}
fn names(kind:&str)->Result<Vec<&'static str>>{match(kind,cfg!(windows)){("maven",true)=>Ok(vec!["mvn.cmd","mvn.bat"]),("maven",false)=>Ok(vec!["mvn"]),("gradle",true)=>Ok(vec!["gradle.bat","gradle.cmd"]),("gradle",false)=>Ok(vec!["gradle"]),_=>fail("未知构建工具")}}
pub fn program_in(kind:&str,input:&Path)->Result<PathBuf>{
 let ns=names(kind)?;text(&input.to_string_lossy(),4096)?;if !input.is_absolute(){return fail("请选择构建工具的安装目录或程序文件")}
 if input.is_file(){if !ns.iter().any(|n|input.file_name().map(|f|f.to_string_lossy().eq_ignore_ascii_case(n)).unwrap_or(false)){return fail(format!("请选择 {}，不是 java.exe 或 IDEA 主程序",ns.join(" / ")))}return Ok(native_path(input.canonicalize()?))}
 for sub in ["bin","","libexec/bin","plugins/maven/lib/maven3/bin","Contents/plugins/maven/lib/maven3/bin"]{for n in &ns{let p=input.join(sub).join(n);if p.is_file(){return Ok(native_path(p.canonicalize()?))}}}
 fail(format!("所选位置没有找到 {kind}（{}）。请选择安装目录；Maven 也可选择已有 IDEA 安装目录。",ns.join(" / ")))
}
fn children(p:&Path,limit:usize)->Vec<PathBuf>{let mut v:Vec<_>=std::fs::read_dir(p).ok().into_iter().flatten().take(limit).filter_map(|e|e.ok()).filter_map(|e|e.file_type().ok().filter(|t|t.is_dir()||t.is_symlink()).map(|_|e.path())).collect();v.sort();v}
pub fn candidates(kind:&str)->Vec<Found>{
 let mut inputs=vec![];for key in if kind=="maven"{vec!["MAVEN_HOME","M2_HOME"]}else{vec!["GRADLE_HOME"]}{if let Some(p)=std::env::var_os(key){inputs.push((PathBuf::from(p),key.to_string()))}}
 if let Some(p)=std::env::var_os("PATH"){for d in std::env::split_paths(&p).filter(|d|d.is_absolute()).take(80){inputs.push((d,"PATH".into()))}}
 #[cfg(windows)]{
  for key in ["ProgramFiles","ProgramFiles(x86)","LOCALAPPDATA"]{if let Some(p)=std::env::var_os(key){let p=PathBuf::from(p);
   for sub in ["Maven","Apache/Maven","Gradle"]{inputs.push((p.join(sub),"常见安装目录".into()))}
   for d in children(&p,96){let n=d.file_name().unwrap_or_default().to_string_lossy().to_lowercase();if n.contains(kind)||n.contains("intellij"){inputs.push((d,"常见安装目录".into()))}}
   if kind=="maven"{for parent in [p.join("JetBrains"),p.join("Programs")]{for d in children(&parent,64){inputs.push((d,"已有 IDE 安装目录".into()))}}
    let mut level=vec![p.join("JetBrains/Toolbox/apps")];let mut remaining=128;
    for _ in 0..4{let mut next=vec![];for d in level{for d in children(&d,24).into_iter().take(remaining){remaining-=1;inputs.push((d.clone(),"已有 Toolbox 安装目录".into()));next.push(d)}}level=next;if remaining==0{break}}
   }
  }}if let Some(h)=dirs::home_dir(){inputs.push((h.join(format!("scoop/apps/{kind}/current")),"Scoop".into()))}
 }
 #[cfg(unix)]{
  for d in ["/opt/homebrew/bin","/usr/local/bin","/usr/bin","/opt/local/bin"]{inputs.push((PathBuf::from(d),"常见安装目录".into()))}
  for d in [format!("/opt/{kind}"),format!("/usr/share/{kind}"),format!("/opt/homebrew/opt/{kind}/libexec"),format!("/usr/local/opt/{kind}/libexec")]{inputs.push((PathBuf::from(d),"常见安装目录".into()))}
  if let Some(h)=dirs::home_dir(){inputs.push((h.join(format!(".sdkman/candidates/{kind}/current")),"SDKMAN".into()))}
  if kind=="maven"{for d in children(Path::new("/Applications"),80){if d.file_name().unwrap_or_default().to_string_lossy().starts_with("IntelliJ"){inputs.push((d,"已有 IDEA 安装目录".into()))}}}
 }
 let mut seen=HashSet::new();inputs.into_iter().filter_map(|(p,source)|program_in(kind,&p).ok().map(|p|Found{path:p.to_string_lossy().into(),source})).filter(|c|seen.insert(if cfg!(windows){c.path.to_lowercase()}else{c.path.clone()})).take(12).collect()
}
pub fn resolve(store:&Store,root:&Path,cwd:&Path,kind:&str,manual:&str)->Result<Found>{
 names(kind)?;if !manual.is_empty(){return Ok(Found{path:program_in(kind,Path::new(manual))?.to_string_lossy().into(),source:"运行配置指定".into()})}
 let root=native_path(root.canonicalize()?);let mut dir=native_path(cwd.canonicalize()?);
 let wrapper=match(kind,cfg!(windows)){("maven",true)=>"mvnw.cmd",("maven",false)=>"mvnw",(_,true)=>"gradlew.bat",(_,false)=>"gradlew"};
 while dir.starts_with(&root){let path=dir.join(wrapper);if path.is_file(){let path=native_path(path.canonicalize()?);if !path.starts_with(&root){return fail("包装器链接到项目外部，请在运行配置中明确选择构建工具")};return Ok(Found{path:path.to_string_lossy().into(),source:"项目包装器".into()})}if dir==root||!dir.pop(){break}}
 if let Some(p)=store.build_tools.get(kind).filter(|s|!s.is_empty()){return Ok(Found{path:program_in(kind,Path::new(p)).map_err(|e|Error(format!("{kind} 全局配置无效：{}；没有自动更换版本",e.0)))?.to_string_lossy().into(),source:"全局指定".into()})}
 if let Some(c)=candidates(kind).into_iter().next(){return Ok(c)}
 fail(format!("未找到 {kind} 构建工具（{}）。已检查项目包装器 {wrapper}、PATH 与常见安装目录。\n选择 Java 并不包含 Maven / Gradle。请打开“运行环境 → 构建工具”选择安装目录，或在本运行配置中选择。",names(kind)?.join(" / ")))
}
pub fn command(found:&Found,args:Vec<String>)->CommandSpec{
 #[cfg(unix)]if found.source=="项目包装器"{let mut v=vec![found.path.clone()];v.extend(args);return CommandSpec{program:"/bin/sh".into(),args:v}}
 // Arguments stay separate; do not concatenate cmd.exe /c strings.
 CommandSpec{program:found.path.clone(),args}
}
pub fn option_path(p:&str,file:bool)->Result<String>{text(p,4096)?;let p=Path::new(p);if !p.is_absolute()||(file&&!p.is_file())||(!file&&!p.is_dir()){return fail("请选择存在的 Maven 配置文件或本地仓库目录")};Ok(native_path(p.canonicalize()?).to_string_lossy().into())}
pub fn maven_options(store:&Store)->Result<Vec<String>>{let mut a=vec![];if let Some(p)=store.build_tools.get("maven_settings").filter(|p|!p.is_empty()){a.extend(["--settings".into(),option_path(p,true)?])}if let Some(p)=store.build_tools.get("maven_repository").filter(|p|!p.is_empty()){a.push(format!("-Dmaven.repo.local={}",option_path(p,false)?))}Ok(a)}
pub async fn verify(store:&Store,kind:&str,path:&Path)->Result<String>{
 let p=program_in(kind,path)?;let mut c=Command::new(p);c.current_dir(std::env::temp_dir()).arg("--version");if kind=="gradle"{c.arg("--no-daemon");}
 if let Ok(e)=environments::select(store,"java",None){let mut vars=Default::default();environments::inject(e,&mut vars)?;c.envs(vars);}
 let o=process::capture(c,12,32768).await?;if o.code!=0{return fail(format!("{kind} 版本检查失败，请检查所选 JDK：{}",o.stderr.chars().take(500).collect::<String>()))}
 let text=format!("{}\n{}",o.stdout,o.stderr);let marker=if kind=="maven"{"Apache Maven "}else{"Gradle "};text.lines().find_map(|l|l.find(marker).map(|i|l[i..].into())).ok_or_else(||Error(format!("程序输出与 {kind} 类型不符")))
}
pub async fn report(store:&Store,kind:&str)->Report{
 let mut r=Report{candidates:candidates(kind),..Default::default()};
 if let Some(p)=store.build_tools.get(kind){match program_in(kind,Path::new(p)){Ok(p)=>{r.selected=Some(Found{path:p.to_string_lossy().into(),source:"全局指定".into()});},Err(e)=>{r.error=Some(e.0);return r}}}else{r.selected=r.candidates.first().cloned()}
 if let Some(c)=&r.selected{match verify(store,kind,Path::new(&c.path)).await{Ok(v)=>r.version=Some(v),Err(e)=>r.error=Some(e.0)}}else{r.error=Some(format!("未检测到 {kind}，请选择安装目录。项目包装器仍可独立使用。"))}r
}
#[cfg(test)]mod tests{use super::*;
 #[test]fn wrapper_and_manual_priority(){let t=tempfile::tempdir().unwrap();let root=native_path(t.path().canonicalize().unwrap());let cwd=root.join("module");std::fs::create_dir(&cwd).unwrap();let home=root.join("Maven tools");std::fs::create_dir_all(home.join("bin")).unwrap();let file=home.join("bin").join(names("maven").unwrap()[0]);std::fs::write(&file,"").unwrap();assert_eq!(program_in("maven",&home).unwrap(),file);let wrapper=root.join(if cfg!(windows){"mvnw.cmd"}else{"mvnw"});std::fs::write(&wrapper,"").unwrap();let mut store=Store::default();store.build_tools.insert("maven".into(),home.to_string_lossy().into());assert_eq!(resolve(&store,&root,&cwd,"maven","").unwrap().source,"项目包装器");assert_eq!(resolve(&store,&root,&cwd,"maven",home.to_str().unwrap()).unwrap().source,"运行配置指定");std::fs::remove_file(wrapper).unwrap();assert_eq!(resolve(&store,&root,&cwd,"maven","").unwrap().source,"全局指定");store.build_tools.insert("maven".into(),root.join("missing").to_string_lossy().into());assert!(resolve(&store,&root,&cwd,"maven","").is_err());}
}
