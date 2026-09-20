//! User-owned SDK registry. Discovery checks bounded, well-known locations only.
use crate::{core::*, process};
use serde::{Deserialize, Serialize};
use std::{collections::{BTreeMap, HashSet}, path::{Path, PathBuf}};
use tokio::process::Command;

#[derive(Clone, Default, Serialize, Deserialize)]
#[serde(default)]
pub struct Environment {
    pub id: String,
    pub name: String,
    pub kind: String,
    pub home: PathBuf,
    pub program: String,
    pub version: String,
    pub major: u32,
}
#[derive(Serialize)]
pub struct Discovery { pub candidates: Vec<Environment>, pub warnings: Vec<String> }
fn exe(name: &str) -> String { if cfg!(windows) { format!("{name}.exe") } else { name.into() } }
pub fn program_in(kind: &str, input: &Path) -> Result<PathBuf> {
    if !["java", "node", "python"].contains(&kind) { return fail("只支持 Java、Node.js、Python 环境"); }
    if !input.is_absolute() { return fail("请选择本机安装目录或程序文件"); }
    if input.is_file() { return Ok(input.to_path_buf()); }
    let names: Vec<String> = if kind == "python" { vec![exe("python"), exe("python3")] } else { vec![exe(kind)] };
    for sub in ["", "bin", "Scripts", "Contents/Home/bin", "jre/bin"] {
        for name in &names {
            let p = input.join(sub).join(name);
            if p.is_file() { return Ok(p); }
        }
    }
    fail("所选目录中没有找到对应运行程序；请选择 JDK / Node.js / Python 安装目录或虚拟环境")
}
pub async fn verify(kind: &str, input: &Path) -> Result<Environment> {
    let mut p = program_in(kind, input)?;
    // Do NOT canonicalize Python's executable symlink: that would lose venv identity.
    p = if kind == "python" { native_path(p.parent().ok_or_else(||Error("无效环境路径".into()))?.canonicalize()?.join(p.file_name().unwrap())) } else { native_path(p.canonicalize()?) };
    let mut c = Command::new(&p);
    c.current_dir(std::env::temp_dir()).arg(if kind == "java" { "-version" } else { "--version" });
    let o = process::capture(c, 5, 16384).await?;
    if o.code != 0 { return fail(format!("环境不能运行：{}", o.stderr.chars().take(300).collect::<String>())); }
    let raw = format!("{}\n{}", o.stdout, o.stderr);
    let line = raw.lines().find(|l| !l.trim().is_empty()).unwrap_or("").trim().to_string();
    let valid = match kind { "java" => raw.contains("version") && (raw.contains("java") || raw.contains("openjdk")), "node" => line.starts_with('v') && line.chars().nth(1).map(|c|c.is_ascii_digit()).unwrap_or(false), "python" => line.starts_with("Python "), _ => false };
    if !valid { return fail("程序的实际版本输出与所选环境类型不符"); }
    let nums:Vec<_> = line.split(|c:char| !c.is_ascii_digit()).filter(|x| !x.is_empty()).filter_map(|s|s.parse::<u32>().ok()).collect();
    let major = if kind == "java" && nums.first() == Some(&1) { *nums.get(1).unwrap_or(&0) } else { *nums.first().unwrap_or(&0) };
    let bin = p.parent().unwrap();
    let home = if ["bin", "Scripts"].iter().any(|s|bin.file_name().map(|f|f==*s).unwrap_or(false)) { bin.parent().unwrap_or(bin) } else { bin };
    Ok(Environment { name:format!("{} {}", match kind { "java"=>"Java", "node"=>"Node.js", _=>"Python" }, major), kind:kind.into(), home:home.to_path_buf(), program:p.to_string_lossy().into(), version:line, major, ..Default::default() })
}
fn children(dir: &Path, max: usize) -> Vec<PathBuf> {
    let mut out = std::fs::read_dir(dir).ok().into_iter().flatten().take(max).filter_map(|e|e.ok()).filter_map(|e|e.file_type().ok().filter(|t|t.is_dir()||t.is_symlink()).map(|_|e.path())).collect::<Vec<_>>(); out.sort(); out
}
pub async fn discover() -> Discovery {
    let mut inputs:Vec<(String,PathBuf)> = vec![];
    for kind in ["java","node","python"] {
        if let Some(path) = std::env::var_os("PATH") {
            for dir in std::env::split_paths(&path).filter(|p|p.is_absolute()).take(80) {
                for n in if kind=="python" { vec![exe("python"),exe("python3")] } else { vec![exe(kind)] } { if dir.join(&n).is_file(){ inputs.push((kind.into(),dir.join(n))); } }
            }
        }
    }
    for (k,v) in std::env::vars_os() { if k.to_string_lossy().starts_with("JAVA_HOME") { inputs.push(("java".into(),PathBuf::from(v))); } }
    if let Some(v) = std::env::var_os("VIRTUAL_ENV") { inputs.push(("python".into(),v.into())); }
    if let Some(home) = dirs::home_dir() {
        for d in [".jdks", ".sdkman/candidates/java"] { for p in children(&home.join(d),24) { inputs.push(("java".into(),p)); } }
        for p in children(&home.join(".nvm/versions/node"),24) { inputs.push(("node".into(),p)); }
        for p in children(&home.join(".pyenv/versions"),24) { inputs.push(("python".into(),p)); }
    }
    #[cfg(windows)] {
        for key in ["ProgramFiles","ProgramFiles(x86)","LOCALAPPDATA"] { if let Some(d)=std::env::var_os(key) {
            let d=PathBuf::from(d);
            for sub in ["Java","Eclipse Adoptium","Microsoft","Amazon Corretto","Zulu"] { for p in children(&d.join(sub),24){inputs.push(("java".into(),p));} }
            inputs.push(("node".into(),d.join("nodejs")));
            for p in children(&d.join("Programs/Python"),24) { inputs.push(("python".into(),p)); }
        }}
        if let Some(d)=std::env::var_os("NVM_HOME") { for p in children(&PathBuf::from(d),24) {inputs.push(("node".into(),p));} }
    }
    #[cfg(unix)] {
        for d in ["/usr/lib/jvm", "/Library/Java/JavaVirtualMachines", "/opt/homebrew/opt", "/usr/local/opt"] {
            for p in children(Path::new(d),80) { let n=p.file_name().unwrap().to_string_lossy();if d.ends_with("opt") && !n.starts_with("openjdk") {continue;} inputs.push(("java".into(),p)); }
        }
        for d in ["/usr/bin","/usr/local/bin","/opt/homebrew/bin","/opt/local/bin"] { for k in ["java","node","python3"] { if Path::new(d).join(k).is_file(){inputs.push((if k=="python3"{"python"}else{k}.into(),Path::new(d).join(k)));} } }
    }
    let mut seen=HashSet::new();let mut out=Discovery{candidates:vec![],warnings:vec![]};
    for (kind,input) in inputs {
        let Ok(p)=program_in(&kind,&input) else{continue};
        let identity = if kind=="python" { p.clone() } else { p.canonicalize().unwrap_or(p.clone()) };
        if !seen.insert((kind.clone(),identity)) {continue;}
        if seen.len()>64 {out.warnings.push("候选环境达到 64 个上限，其他安装可通过目录选择器添加".into());break;}
        match verify(&kind,&p).await { Ok(e)=>out.candidates.push(e), Err(e)=>out.warnings.push(format!("{}：{}",p.display(),e.0)) }
    }
    out
}
pub fn select<'a>(store:&'a Store,kind:&str,explicit:Option<&str>)->Result<&'a Environment> {
    let wanted=explicit.filter(|s|!s.is_empty()).or_else(||store.environment_defaults.get(kind).map(String::as_str));
    let e=if let Some(id)=wanted {store.environments.iter().find(|e|e.id==id)} else {store.environments.iter().find(|e|e.kind==kind)};
    match e {Some(e) if e.kind==kind =>Ok(e),_=>fail(format!("尚未配置可用的 {kind} 环境，请在“运行环境”中选择安装目录；不会自动安装或更换版本"))}
}
pub fn inject(e:&Environment, env:&mut BTreeMap<String,String>)->Result<()> {
    if !Path::new(&e.program).is_file() {return fail(format!("环境 {} 的程序已不存在，请重新选择",e.name));}
    let mut paths=vec![Path::new(&e.program).parent().unwrap().to_path_buf()];
    paths.extend(std::env::split_paths(&std::env::var_os("PATH").unwrap_or_default()));
    // A selected runtime wins over inherited JAVA_HOME/PATH. No global OS changes.
    let keys:Vec<_>=env.keys().filter(|k|k.eq_ignore_ascii_case("PATH")||k.eq_ignore_ascii_case("JAVA_HOME")||k.eq_ignore_ascii_case("VIRTUAL_ENV")).cloned().collect();for k in keys{env.remove(&k);}
    env.insert("PATH".into(),std::env::join_paths(paths).map_err(|e|Error(e.to_string()))?.to_string_lossy().into());
    if e.kind=="java" {env.insert("JAVA_HOME".into(),e.home.to_string_lossy().into());}
    if e.kind=="python"&&e.home.join("pyvenv.cfg").exists(){env.insert("VIRTUAL_ENV".into(),e.home.to_string_lossy().into());}
    Ok(())
}
