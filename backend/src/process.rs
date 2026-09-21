#[path="output_text.rs"] pub mod text_output;
use crate::core::*;
use process_wrap::tokio::*;
use tokio::{process::Command,io::{AsyncRead,AsyncReadExt},time::{timeout,Duration}};
use std::{path::Path,process::Stdio};

pub struct Managed(pub Box<dyn ChildWrapper>);
impl Drop for Managed {fn drop(&mut self){let _=self.0.start_kill();}}
pub fn spawn(mut c:Command)->Result<Managed>{
 c.stdin(Stdio::null()).stdout(Stdio::piped()).stderr(Stdio::piped());
 let program=c.as_std().get_program().to_string_lossy().into_owned();
 let cwd=c.as_std().get_current_dir().map(|p|p.display().to_string()).unwrap_or_default();
 let mut c=CommandWrap::from(c);c.wrap(KillOnDrop);
 #[cfg(unix)]{c.wrap(ProcessGroup::leader());}
 #[cfg(windows)]{c.wrap(CreationFlags(windows::Win32::System::Threading::CREATE_NO_WINDOW));c.wrap(JobObject);}
 Ok(Managed(c.spawn().map_err(|e|Error(format!("无法启动程序：{program}\n工作目录：{cwd}\n系统错误：{e}\n请检查安装位置与运行配置。没有自动换用其他版本。")))?))
}
#[derive(serde::Serialize)]
pub struct Output {pub code:i32,pub stdout:String,pub stderr:String,pub warnings:Vec<String>}
struct RawOutput {code:i32,stdout:Vec<u8>,stderr:Vec<u8>}
async fn limited<R:AsyncRead+Unpin>(mut r:R,max:usize)->Result<Vec<u8>>{
 let mut out=Vec::new();let mut b=[0u8;4096];loop{let n=r.read(&mut b).await?;if n==0{break}if out.len()+n>max{return fail("输出超过上限；操作结果需刷新确认，未自动重试")};out.extend_from_slice(&b[..n]);}Ok(out)
}
async fn capture_raw(c:Command,seconds:u64,max:usize)->Result<RawOutput>{
 let mut child=spawn(c)?;
 let out=child.0.stdout().take().ok_or_else(||Error("标准输出未连接".into()))?;
 let err=child.0.stderr().take().ok_or_else(||Error("错误输出未连接".into()))?;
 let result=timeout(Duration::from_secs(seconds),async {
  let (status,o,e)=tokio::try_join!(async{child.0.wait().await.map_err(Error::from)},limited(out,max),limited(err,max))?;
  Ok::<_,Error>(RawOutput{code:status.code().unwrap_or(-1),stdout:o,stderr:e})
 }).await;
 let _=child.0.start_kill();let _=timeout(Duration::from_secs(3),child.0.wait()).await;
 result.map_err(|_|Error("命令超时，已请求停止受控进程；写操作结果请刷新确认".into()))?
}
/// Machine-readable stdout stays strict. Never turn replacement characters into paths.
fn strict_stdout(bytes:Vec<u8>,program:&str)->Result<String>{
 String::from_utf8(bytes).map_err(|e|Error(format!("程序 {program} 返回的结构化结果不是 UTF-8（第 {} 字节）；未使用替换字符解析路径或仓库数据。若命令已产生写入，请刷新确认实际结果。",e.utf8_error().valid_up_to())))
}
pub async fn capture(c:Command,seconds:u64,max:usize)->Result<Output>{
 let program=c.as_std().get_program().to_string_lossy().into_owned();
 let raw=capture_raw(c,seconds,max).await?;
 let stderr=crate::process::text_output::display(&raw.stderr,crate::process::text_output::OutputEncoding::Auto).text;
 Ok(Output{code:raw.code,stdout:strict_stdout(raw.stdout,&program)?,stderr,warnings:vec![]})
}
/// Build and version output is human-readable, not a source of executable paths.
/// A log decoding problem must not convert exit code 0 into a failed build.
pub async fn capture_text(c:Command,seconds:u64,max:usize,encoding:crate::process::text_output::OutputEncoding)->Result<Output>{
 let raw=capture_raw(c,seconds,max).await?;
 let out=crate::process::text_output::display(&raw.stdout,encoding);
 let err=crate::process::text_output::display(&raw.stderr,encoding);
 let mut warnings=vec![];
 if out.replacements{warnings.push(crate::process::text_output::warning(out.encoding));}
 if err.replacements&&(!out.replacements||out.encoding!=err.encoding){warnings.push(crate::process::text_output::warning(err.encoding));}
 Ok(Output{code:raw.code,stdout:out.text,stderr:err.text,warnings})
}
pub fn checked(o:Output)->Result<String>{if o.code==0{return Ok(o.stdout)}
 let tail=|s:&str|s.chars().rev().take(4000).collect::<String>().chars().rev().collect::<String>();
 fail(format!("命令退出码 {}：\n{}\n{}",o.code,tail(&o.stderr),tail(&o.stdout)))
}
pub fn command(spec:&CommandSpec,cwd:&Path,port:Option<u16>,extra:&[String],env:&std::collections::BTreeMap<String,String>)->Result<Command>{
 validate_command(spec)?;validate_env(env)?;
 let replace=|s:&str|->Result<String>{if s.contains("{port}")&&port.is_none(){return fail("命令包含 {port}，请设置实例端口")}Ok(s.replace("{port}",&port.map(|p|p.to_string()).unwrap_or_default()))};
 let raw=Path::new(&spec.program);
 let program=if raw.is_relative()&&(raw.components().count()>1||cwd.join(raw).is_file()){cwd.join(raw)}else{raw.to_path_buf()};
 let mut c=Command::new(program);c.current_dir(cwd);
 for a in spec.args.iter().chain(extra){c.arg(replace(a)?);}for(k,v)in env{c.env(k,replace(v)?);}
 if let Some(p)=port{c.env("PORT",p.to_string());}Ok(c)
}
#[cfg(test)]mod tests{
 use super::*;
 #[tokio::test]async fn capture_real(){let mut c=Command::new("git");c.arg("--version");let o=capture(c,10,8192).await.unwrap();assert_eq!(o.code,0);assert!(o.stdout.starts_with("git version"));}
 #[test]fn strict_machine_output_rejects_legacy_bytes(){assert!(strict_stdout(vec![0xd6,0xd0],"path-tool").is_err());assert_eq!(strict_stdout("D:\\项目".as_bytes().to_vec(),"path-tool").unwrap(),"D:\\项目");}
 #[test]fn missing_port(){let s=CommandSpec{program:"java".into(),args:vec!["--server.port={port}".into()]};assert!(command(&s,Path::new("."),None,&[],&Default::default()).is_err());}
}
