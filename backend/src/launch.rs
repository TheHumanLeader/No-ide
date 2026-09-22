//! Declarative launch configuration; argv is assembled on the backend, never by a shell string.
use crate::{core::*, environments};
#[path="build_tools.rs"] pub mod tools;
#[path="maven_workspace.rs"] pub mod maven;
use serde::{Deserialize, Serialize};
use std::{collections::BTreeMap, path::{Path,PathBuf}};

#[derive(Clone,Default,Serialize,Deserialize)]
#[serde(default)]
pub struct Launcher {
    pub kind:String,
    pub target:String,
    pub build_tool_path:String,
    pub sources:Vec<String>,
    pub vm_options:Vec<String>,
    pub properties:BTreeMap<String,String>,
    pub arguments:Vec<String>,
    pub profiles:Vec<String>,
    pub maven_root:String,
    pub working_directory:String,
    pub maven_profiles:Vec<String>,
    pub maven_properties:BTreeMap<String,String>,
    pub trace_classes:bool,
    pub update_mode:String,
    pub main_class:String,
}
#[derive(Clone,Serialize,Deserialize)]
pub struct Entry {
    pub name:String,pub kind:String,pub cwd:String,pub target:String,pub sources:Vec<String>,
    pub environment_kind:String,pub suggested_port:Option<u16>,pub description:String,
}
pub fn runtime_kind(kind:&str)->&str {
    match kind {"npm-script"|"node-file"=>"node","python-file"=>"python",_=>"java"}
}
fn spec(program:impl Into<String>,args:Vec<String>)->CommandSpec{CommandSpec{program:program.into(),args}}
fn quote_arguments(args:&[String])->Result<String>{
    // Spring/Maven/Gradle parse an argument string themselves; reject line breaks.
    if args.iter().any(|a|a.contains(['\n','\r','\0'])){return fail("此启动方式的参数不能包含换行或 NUL");}
    Ok(args.iter().map(|a|format!("\"{}\"",a.replace('\\',"\\\\").replace('"',"\\\""))).collect::<Vec<_>>().join(" "))
}
fn npm_cli(env:&environments::Environment)->Result<PathBuf>{
    let bin=Path::new(&env.program).parent().unwrap();
    let mut paths=vec![bin.join("node_modules/npm/bin/npm-cli.js"),env.home.join("lib/node_modules/npm/bin/npm-cli.js"),bin.join("../lib/node_modules/npm/bin/npm-cli.js")];
    if let Ok(p)=bin.join("npm").canonicalize(){paths.insert(0,p);}
    #[cfg(unix)] paths.push(PathBuf::from("/usr/share/nodejs/npm/bin/npm-cli.js"));
    paths.into_iter().find(|p|p.is_file()).ok_or_else(||Error("所选 Node.js 环境中没有找到 npm；请添加包含 npm 的 Node 安装，或在高级配置中指定包管理器".into()))
}
pub fn resolve(store:&Store,p:&Project,c:&RunConfig,instance:Option<&Instance>,prepare:bool)->Result<RunConfig>{
    let Some(l)=&c.launcher else {return Ok(c.clone())};
    if !["","restart","hotswap"].contains(&l.update_mode.as_str()){return fail("未知更新模式")}
    if l.update_mode=="hotswap" && l.kind!="spring-maven"{return fail("当前原地热替换支持 Spring Boot / Maven 自动入口")}
    if !l.main_class.is_empty() && (l.main_class.len()>1024 || !l.main_class.chars().all(|c|c.is_alphanumeric()||"._$".contains(c))){return fail("主类名格式无效")}
    let kind=runtime_kind(&l.kind);
    let eid=instance.and_then(|i|i.environment_id.as_deref()).or(c.environment_id.as_deref());
    let env=environments::select(store,kind,eid)?;
    let cwd=inside(&p.root,&c.cwd)?;
    let target_path=||->Result<PathBuf>{inside(&cwd,&l.target)};
    let mut out=c.clone();out.build=None;
    // Instance override of JAVA_HOME/PATH must not undo a selected SDK.
    if let Some(i)=instance{out.env.extend(i.env.clone());}
    environments::inject(env,&mut out.env)?;
    let mut vm=l.vm_options.clone();
    if l.trace_classes && kind=="java" {vm.push("-verbose:class".into());}
    for(k,v)in &l.properties {text(k,256)?;if k.contains(['=','\0','\n','\r'])||v.len()>8192||v.contains('\0'){return fail("Java 系统属性格式无效")};vm.push(format!("-D{k}={v}"));}
    let mut app_args=l.arguments.clone();
    if let Some(i)=instance{app_args.extend(i.args.clone());}
    match l.kind.as_str(){
        "java-main"=>{
            if l.sources.is_empty()||l.sources.len()>100{return fail("普通 Java 自动编译支持 1～100 个源码文件；依赖项目请使用 Maven/Gradle 入口");}
            let outdir=dirs::cache_dir().unwrap_or_else(std::env::temp_dir).join("no-ide/build").join(&p.id).join(&c.id);
            if prepare{std::fs::create_dir_all(&outdir)?;}
            let javac=Path::new(&env.program).parent().unwrap().join(if cfg!(windows){"javac.exe"}else{"javac"});
            if !javac.is_file(){return fail("所选环境只有 JRE，没有 javac；请添加完整 JDK");}
            let mut build=vec!["-encoding".into(),"UTF-8".into(),"-d".into(),outdir.to_string_lossy().into_owned()];
            for file in &l.sources{let src=inside(&p.root,file)?;if src.extension().and_then(|s|s.to_str())!=Some("java")||!src.is_file(){return fail("Java 源码入口不存在")};build.push(src.to_string_lossy().into_owned());}
            out.build=Some(spec(javac.to_string_lossy(),build));
            if !l.target.chars().all(|c|c.is_alphanumeric()||"._$".contains(c)){return fail("Java 主类名无效")};
            vm.extend(["-cp".into(),outdir.to_string_lossy().into_owned(),l.target.clone()]);vm.extend(app_args);out.command=spec(&env.program,vm);
        },
        "java-jar"=>{let target=target_path()?;if !target.is_file(){return fail("所选 JAR 文件不存在")};vm.extend(["-jar".into(),target.to_string_lossy().into_owned()]);vm.extend(app_args);out.command=spec(&env.program,vm);},
        "node-file"|"python-file"=>{let target=target_path()?;if !target.is_file(){return fail("所选入口文件不存在")};let mut args=l.vm_options.clone();if kind=="python"{args.push("-u".into());}args.push(target.to_string_lossy().into_owned());args.extend(app_args);out.command=spec(&env.program,args);},
        "npm-script"=>{
            let manifest=inside(&cwd,"package.json")?;let bytes=std::fs::read(&manifest)?;if bytes.len()>256*1024{return fail("package.json 过大")};
            let j:serde_json::Value=serde_json::from_slice(&bytes)?;
            if j["scripts"][&l.target].as_str().is_none(){return fail("package.json 中已经不存在所选脚本，请重新扫描")};
            let mut args=vec![npm_cli(env)?.to_string_lossy().into_owned(),"run".into(),l.target.clone()];
            if !app_args.is_empty(){args.push("--".into());args.extend(app_args);}
            if !l.vm_options.is_empty(){out.env.insert("NODE_OPTIONS".into(),quote_arguments(&l.vm_options)?);}
            out.command=spec(&env.program,args);
        },
        "spring-maven"|"maven-main"=>{
            if !cwd.join("pom.xml").is_file(){return fail("工作目录中没有 pom.xml")};
            let mut args=if l.kind=="spring-maven"{vec!["spring-boot:run".into()]}else{vec!["compile".into(),"exec:java".into(),format!("-Dexec.mainClass={}",l.target)]};
            if l.kind=="spring-maven" {
                if !vm.is_empty(){args.push(format!("-Dspring-boot.run.jvmArguments={}",quote_arguments(&vm)?));}
                if !app_args.is_empty(){args.push(format!("-Dspring-boot.run.arguments={}",quote_arguments(&app_args)?));}
                if !l.profiles.is_empty(){args.push(format!("-Dspring-boot.run.profiles={}",l.profiles.join(",")));}
            }else{
                if !vm.is_empty(){out.env.insert("MAVEN_OPTS".into(),quote_arguments(&vm)?);}
                if !app_args.is_empty(){args.push(format!("-Dexec.args={}",quote_arguments(&app_args)?));}
            }
            let plan=maven::resolve(&p.root,&cwd,l)?;
            let tool=tools::resolve(store,&p.root,&cwd,"maven",&l.build_tool_path)?;
            let mut options=tools::maven_options(store)?;options.extend(plan.common_args(&p.root,l)?);
            if l.kind=="spring-maven"{
                // Application cwd is independent of the selected Maven module.
                // A reactor root matches IDEA's usual project working directory.
                args.push(format!("-Dspring-boot.run.workingDirectory={}",inside(&p.root,&plan.working_directory)?.display()));
            }
            out.cwd=plan.working_directory.clone();
            let mut run_args=options.clone();run_args.extend(args);
            out.command=tools::command(&tool,run_args);
            let mut build_args=options;
            if plan.multi_module{build_args.push("--also-make".into());}
            build_args.extend(["-DskipTests".into(),"clean".into(),if plan.multi_module{"install"}else{"compile"}.into()]);
            // Never run spring-boot:run on every reactor module. Only the build
            // uses --also-make; the run command selects the entry module alone.
            out.build=Some(tools::command(&tool,build_args));
        },
        "gradle-task"=>{
            if !cwd.join("build.gradle").is_file()&&!cwd.join("build.gradle.kts").is_file(){return fail("工作目录中没有 Gradle 构建文件")};
            if !["bootRun","run","assembleDebug"].contains(&l.target.as_str()){return fail("自动入口只支持已识别的 Gradle 运行任务")};
            let mut args=vec![l.target.clone(),"--no-daemon".into()];
            if !app_args.is_empty(){if l.target=="assembleDebug"{return fail("Android 构建任务不接收程序入参")};args.push(format!("--args={}",quote_arguments(&app_args)?));}
            if !vm.is_empty(){out.env.insert("JAVA_TOOL_OPTIONS".into(),quote_arguments(&vm)?);}
            let tool=tools::resolve(store,&p.root,&cwd,"gradle",&l.build_tool_path)?;out.command=tools::command(&tool,args);
        },
        _=>return fail("未知自动启动类型，请重新扫描或使用高级自定义配置"),
    }
    validate_command(&out.command)?;if let Some(b)=&out.build{validate_command(b)?;}validate_env(&out.env)?;
    Ok(out)
}
#[cfg(test)]mod tests {
    use super::*;
    #[test]fn quotes(){assert_eq!(quote_arguments(&["a b".into(),"x\"y".into()]).unwrap(),"\"a b\" \"x\\\"y\"");assert!(quote_arguments(&["\n".into()]).is_err());}
}
