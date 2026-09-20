//! Bounded static inspection: never imports Python, runs npm scripts, or evaluates build files.
use crate::{core::*, launch::Entry};
use serde::Serialize;
use std::path::{Path,PathBuf};
use regex::Regex;
#[derive(Serialize)]pub struct Report{pub entries:Vec<Entry>,pub directories:Vec<String>,pub warnings:Vec<String>,pub inspected:usize,pub truncated:bool,pub virtual_environments:Vec<String>}
fn relative(root:&Path,p:&Path)->String {p.strip_prefix(root).unwrap_or(p).to_string_lossy().replace('\\',"/")}
pub fn scan(root:&Path,sub:&str)->Result<Report>{
    let base=inside(root,sub)?;if !base.is_dir(){return fail("扫描目录不存在")};
    let mut r=Report{entries:vec![],directories:vec![".".into()],warnings:vec![],inspected:0,truncated:false,virtual_environments:vec![]};
    let ignore=[".git",".svn","node_modules","target","build","dist",".venv","venv","__pycache__",".idea",".gradle",".m2",".cache"];
    let mut stack=vec![(base.clone(),0usize)];let mut files=vec![];let mut bytes=0usize;
    while let Some((d,depth))=stack.pop(){
        if depth>7{r.truncated=true;continue;}
        let Ok(dir)=std::fs::read_dir(&d)else{r.warnings.push(format!("无法读取 {}",relative(root,&d)));continue};
        for e in dir {
            r.inspected+=1;if r.inspected>8000{r.truncated=true;break;}
            let Ok(e)=e else{continue};let Ok(t)=e.file_type()else{continue};if t.is_symlink(){continue;}
            let p=e.path();let name=e.file_name().to_string_lossy().into_owned();
            if t.is_dir(){
                if [".venv","venv"].contains(&name.as_str())&&p.join("pyvenv.cfg").is_file(){r.virtual_environments.push(p.to_string_lossy().into_owned());}
                if !ignore.contains(&name.as_str()){if r.directories.len()<300{r.directories.push(relative(root,&p));}stack.push((p,depth+1));}
            }else if t.is_file(){
                if !matches!(p.extension().and_then(|x|x.to_str()),Some("java"|"py"|"js"|"mjs"|"cjs"|"jar"))&&!matches!(name.as_str(),"package.json"|"pom.xml"|"build.gradle"|"build.gradle.kts"){continue;}
                if files.len()>=600{r.truncated=true;continue;}
                let size=e.metadata()?.len();if size>256*1024{if name.ends_with("jar"){files.push((p,String::new()));}else{r.truncated=true;}continue;}
                bytes+=size as usize;if bytes>8*1024*1024{r.truncated=true;continue;}
                if name.ends_with("jar"){files.push((p,String::new()));continue;}
                let raw=std::fs::read(&p)?;if let Ok(text)=String::from_utf8(raw){files.push((p,text));}
            }
        }
        if r.inspected>8000{break;}
    }
    files.sort_by(|a,b|a.0.cmp(&b.0));r.directories.sort();r.directories.dedup();
    let package=Regex::new(r"(?m)^\s*package\s+([\w.]+)\s*;").unwrap();
    let main=Regex::new(r"(?s)\bstatic\s+void\s+main\s*\(").unwrap();
    let class=Regex::new(r"\b(?:class|record|enum)\s+([\w$]+)").unwrap();
    let java_files:Vec<_>=files.iter().filter(|(p,_)|p.extension().and_then(|s|s.to_str())==Some("java")).map(|(p,_)|relative(root,p)).collect();
    for (p,text) in &files {
        if r.entries.len()>=150{r.truncated=true;break;}
        let parent=p.parent().unwrap();let mut cwd=relative(root,parent);if cwd.is_empty(){cwd=".".into();}
        let file=p.file_name().unwrap().to_string_lossy().into_owned();
        let mut add=|name:String,kind:&str,target:String,env:&str,port:Option<u16>,description:&str,sources:Vec<String>|{
            r.entries.push(Entry{name,kind:kind.into(),cwd:cwd.clone(),target,sources,environment_kind:env.into(),suggested_port:port,description:description.into()});
        };
        match file.as_str(){
            "package.json"=>match serde_json::from_str::<serde_json::Value>(text){Ok(j)=>{
                if let Some(scripts)=j["scripts"].as_object(){for(name,command)in scripts{if command.is_string(){
                    let cmd=command.as_str().unwrap();let port=if cmd.contains("vite")||cmd.contains("quasar dev"){Some(5173)}else{None};
                    add(format!("{} · {}",j["name"].as_str().unwrap_or("Node.js"),name),"npm-script",name.clone(),"node",port,cmd,vec![]);
                }}}
            },Err(_)=>r.warnings.push(format!("{} 不是有效 JSON",relative(root,p)))},
            "pom.xml"=>{
                if roxmltree::Document::parse(text).is_err(){r.warnings.push(format!("{} 无法解析",relative(root,p)));continue;}
                if text.contains("spring-boot")&&!text.contains("<packaging>pom</packaging>") {add(format!("{} · Spring Boot",parent.file_name().unwrap_or_default().to_string_lossy()),"spring-maven",String::new(),"java",Some(8080),"从 pom.xml 识别；使用项目 Maven Wrapper 或系统 Maven",vec![]);}
            },
            "build.gradle"|"build.gradle.kts"=>{
                let task=if text.contains("org.springframework.boot"){"bootRun"}else if text.contains("com.android.application"){"assembleDebug"}else if text.contains("application"){"run"}else{continue};
                add(format!("{} · {}",parent.file_name().unwrap_or_default().to_string_lossy(),task),"gradle-task",task.into(),"java",if task=="bootRun"{Some(8080)}else{None},"静态识别 Gradle 插件；自定义脚本任务可使用高级配置",vec![]);
            },
            _=>match p.extension().and_then(|x|x.to_str()){
                Some("py") if ["main.py","app.py","manage.py","__main__.py"].contains(&file.as_str()) || text.contains("__name__")&&text.contains("__main__") => add(file.clone(),"python-file",file.clone(),"python",None,"Python 入口候选；只读取文本，不执行 import",vec![]),
                Some("js"|"mjs"|"cjs") if ["index.js","server.js","app.js","main.js","index.mjs","server.mjs","main.mjs"].contains(&file.as_str()) => add(file.clone(),"node-file",file.clone(),"node",None,"Node.js 文件入口候选；浏览器脚本请优先选择 package.json 中的 dev",vec![]),
                Some("jar")=>add(file.clone(),"java-jar",file.clone(),"java",None,"已有 JAR 文件；是否有 Main-Class 由实际启动验证",vec![]),
                Some("java") if main.is_match(text)=>{
                    let Some(c)=class.captures(text)else{continue};
                    let target=package.captures(text).map(|p|format!("{}.{}",&p[1],&c[1])).unwrap_or_else(||c[1].to_string());
                    let mut ancestor=parent;let mut maven=None;while ancestor.starts_with(root){if ancestor.join("pom.xml").is_file(){maven=Some(ancestor);break;}let Some(up)=ancestor.parent()else{break};ancestor=up;}
                    if let Some(m)=maven {let rel=relative(root,m);r.entries.push(Entry{name:format!("{} · main",&c[1]),kind:"maven-main".into(),cwd:if rel.is_empty(){".".into()}else{rel},target,sources:vec![],environment_kind:"java".into(),suggested_port:None,description:"Maven compile + exec:java；依赖解析在你点击运行后进行".into()});}
                    else if java_files.len()<=100{r.entries.push(Entry{name:format!("{} · main",&c[1]),kind:"java-main".into(),cwd:".".into(),target,sources:java_files.clone(),environment_kind:"java".into(),suggested_port:None,description:"JDK 编译项目内普通 Java 源码；第三方依赖请用构建工具入口".into()});}
                },_=>{}
            }
        }
    }
    r.entries.sort_by_key(|e| match (e.kind.as_str(),e.target.as_str()){("npm-script","dev")|("spring-maven",_)|("gradle-task","bootRun")=>0,("npm-script","start")=>1,_=>2});
    if r.truncated{r.warnings.push("已达到扫描深度、文件数或读取量上限；可选择更小的模块目录继续找入口".into());}
    Ok(r)
}
#[cfg(test)]mod tests{
 use super::*;
 #[test]fn finds_scripts_without_execution(){let d=tempfile::tempdir().unwrap();std::fs::write(d.path().join("package.json"),r#"{"scripts":{"dev":"vite","test":"do-not-run"}}"#).unwrap();std::fs::create_dir(d.path().join("node_modules")).unwrap();std::fs::write(d.path().join("node_modules/app.py"),"print('bad')").unwrap();let r=scan(d.path(),".").unwrap();assert_eq!(r.entries.len(),2);assert_eq!(r.entries[0].target,"dev");assert!(scan(d.path(),"../").is_err());}
}
