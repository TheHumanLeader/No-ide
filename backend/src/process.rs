use crate::core::*;
use process_wrap::tokio::*;
use tokio::{process::Command,io::{AsyncRead,AsyncReadExt},time::{timeout,Duration}};
use std::{path::Path,process::Stdio};

pub struct Managed(pub Box<dyn ChildWrapper>);
impl Drop for Managed {fn drop(&mut self){let _=self.0.start_kill();}}
pub fn spawn(mut c:Command)->Result<Managed>{
 c.stdin(Stdio::null()).stdout(Stdio::piped()).stderr(Stdio::piped());
 let mut c=CommandWrap::from(c);c.wrap(KillOnDrop);
 #[cfg(unix)]{c.wrap(ProcessGroup::leader());}
 #[cfg(windows)]{c.wrap(CreationFlags(windows::Win32::System::Threading::CREATE_NO_WINDOW));c.wrap(JobObject);}
 Ok(Managed(c.spawn()?))
}
#[derive(serde::Serialize)]
pub struct Output {pub code:i32,pub stdout:String,pub stderr:String}
async fn limited<R:AsyncRead+Unpin>(mut r:R,max:usize)->Result<Vec<u8>>{
 let mut out=Vec::new();let mut b=[0u8;4096];loop{let n=r.read(&mut b).await?;if n==0{break}if out.len()+n>max{return fail("输出超过上限；操作结果需刷新确认，未自动重试")};out.extend_from_slice(&b[..n]);}Ok(out)
}
pub async fn capture(c:Command,seconds:u64,max:usize)->Result<Output>{
 let mut child=spawn(c)?;
 let out=child.0.stdout().take().ok_or_else(||Error("标准输出未连接".into()))?;
 let err=child.0.stderr().take().ok_or_else(||Error("错误输出未连接".into()))?;
 let result=timeout(Duration::from_secs(seconds),async {
  let (status,o,e)=tokio::try_join!(async{child.0.wait().await.map_err(Error::from)},limited(out,max),limited(err,max))?;
  Ok::<_,Error>(Output{code:status.code().unwrap_or(-1),stdout:String::from_utf8(o).map_err(|_|Error("输出不是 UTF-8；未按损坏路径执行".into()))?,stderr:String::from_utf8_lossy(&e).into_owned()})
 }).await;
 let _=child.0.start_kill();let _=timeout(Duration::from_secs(3),child.0.wait()).await;
 result.map_err(|_|Error("命令超时，已请求停止受控进程；写操作结果请刷新确认".into()))?
}
pub fn checked(o:Output)->Result<String>{if o.code==0{Ok(o.stdout)}else{fail(format!("命令退出码 {}：{}",o.code,o.stderr.chars().take(4000).collect::<String>()))}}
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
 #[test]fn missing_port(){let s=CommandSpec{program:"java".into(),args:vec!["--server.port={port}".into()]};assert!(command(&s,Path::new("."),None,&[],&Default::default()).is_err());}
}
