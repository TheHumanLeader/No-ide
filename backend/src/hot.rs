//! Isolated runtime outputs + a bounded authenticated Java 8 agent protocol.
//! Maven may clean/build in its own directories; the running JVM reads a private
//! snapshot. Unsupported changes are pending, never a hidden cold restart.
use crate::{core::*, incremental, launch, process, runtime::{Hub,capture_build}};
use serde::{Deserialize,Serialize};
use sha2::{Digest,Sha256};
use std::{collections::{BTreeMap,BTreeSet},path::{Path,PathBuf},sync::Arc,io::{Read,Write}};
use tokio::{io::{AsyncReadExt,AsyncWriteExt},net::TcpStream,time::{timeout,Duration}};
const CP_GOAL:&str="org.apache.maven.plugins:maven-dependency-plugin:3.8.1:build-classpath";
const MAX_TOTAL:usize=32*1024*1024;
pub fn enabled(c:&RunConfig)->bool{c.launcher.as_ref().map(|l|l.kind=="spring-maven"&&l.update_mode=="hotswap").unwrap_or(false)}
fn hash(b:&[u8])->String{format!("{:x}",Sha256::digest(b))}
fn file_hash(p:&Path)->Result<String>{let mut f=std::fs::File::open(p)?;let mut h=Sha256::new();let mut b=[0;65536];loop{let n=f.read(&mut b)?;if n==0{break}h.update(&b[..n]);}Ok(format!("{:x}",h.finalize()))}
fn agent()->Result<PathBuf>{let p=std::env::var_os("NO_IDE_AGENT").map(PathBuf::from).unwrap_or_else(||std::env::current_exe().unwrap().parent().unwrap().join("agent/no-ide-agent.jar"));if !p.is_file(){return fail("找不到内置 no-ide-agent.jar，请完整解压带 agent 文件夹的新包，或选择兼容重启模式")};Ok(native_path(p.canonicalize()?))}
#[derive(Clone,Serialize,Deserialize)]struct Layout{key:String,entries:Vec<PathBuf>,main:String}
async fn layout(p:&Project,c:&RunConfig,resolved:&RunConfig,cache:&Path,hub:Arc<Hub>)->Result<Layout>{
 let p1=p.clone();let c1=c.clone();let cache1=cache.to_path_buf();let model=tokio::task::spawn_blocking(move||incremental::hot_model(&p1,&c1,&cache1)).await.map_err(|e|Error(e.to_string()))??;
 let path=cache.join(format!("hot-layout-{}.json",hash(format!("{}:{}",p.id,c.id).as_bytes())));
 if let Ok(bytes)=std::fs::read(&path){if let Ok(old)=serde_json::from_slice::<Layout>(&bytes){if old.key==model.key && !old.entries.is_empty(){return Ok(old)}}}
 let dir=tempfile::tempdir()?;let cp=dir.path().join("runtime-cp.txt");
 let mut cmd=resolved.build.clone().ok_or_else(||Error("没有 Maven 构建配置".into()))?;
 cmd.args.retain(|a|!["clean","compile","install","-DskipTests","--also-make","-am"].contains(&a.as_str()));
 cmd.args.extend([CP_GOAL.into(),format!("-Dmdep.outputFile={}",native_path(cp.clone()).display()),"-Dmdep.pathSeparator=|".into(),"-DincludeScope=runtime".into(),"-DoutputEncoding=UTF-8".into(),"-Dmdep.regenerateFile=true".into()]);
 let command=process::command(&cmd,&inside(&p.root,&resolved.cwd)?,None,&[],&resolved.env)?;
 process::checked(capture_build(command,120,hub,c.id.clone(),c.output_encoding).await?)?;
 if cp.metadata()?.len()>2*1024*1024{return fail("运行类路径过大")}
 let text=std::fs::read_to_string(&cp)?;let mut entries=vec![model.entry.clone()];
 for s in text.trim().split('|').filter(|s|!s.is_empty()){
  let source=native_path(PathBuf::from(s));if !source.is_absolute(){return fail("运行类路径不是绝对路径")}
  let source=if let Some((_,out))=model.mappings.iter().find(|(jar,_)|jar==&source){out.clone()}else{source};
  if !entries.contains(&source){entries.push(source)}
 }
 if entries.len()>4096{return fail("运行类路径超过 4096 项")}
 let out=Layout{key:model.key,entries,main:model.main_class};std::fs::create_dir_all(cache)?;
 let mut temp=tempfile::NamedTempFile::new_in(cache)?;temp.write_all(&serde_json::to_vec(&out)?)?;temp.persist(path).map_err(|e|Error(e.to_string()))?;Ok(out)
}
#[derive(Clone)]struct Entry{source:PathBuf,target:PathBuf,root:Option<u32>}
#[derive(Clone)]struct Patch{root:u32,relative:String,before:String,bytes:Vec<u8>}
pub struct Session{_directory:tempfile::TempDir,layout:Layout,entries:Vec<Entry>,files:BTreeMap<String,String>,endpoint:PathBuf,token:String,pub java_pid:Option<u32>}
fn walk(dir:&Path,relative:&str,out:&mut BTreeMap<String,String>,copy:Option<&Path>,depth:usize,budget:&mut (usize,u64))->Result<()>{
 if depth>64||budget.0>200000{return fail("类路径快照超过支持范围")}
 let at=dir.join(relative);let meta=std::fs::symlink_metadata(&at)?;budget.0+=1;
 if meta.file_type().is_symlink(){return fail("热替换快照不跟随符号链接；请选择兼容重启模式")}
 if meta.is_dir(){if let Some(dst)=copy{std::fs::create_dir_all(dst.join(relative))?;}let mut entries=std::fs::read_dir(at)?.collect::<std::io::Result<Vec<_>>>()?;entries.sort_by_key(|e|e.file_name());for e in entries{let rel=if relative.is_empty(){e.file_name().into_string().map_err(|_|Error("类路径含非 Unicode 文件名".into()))?}else{format!("{}/{}",relative,e.file_name().into_string().map_err(|_|Error("类路径含非 Unicode 文件名".into()))?)};walk(dir,&rel,out,copy,depth+1,budget)?;}}
 else if meta.is_file(){budget.1=budget.1.saturating_add(meta.len());if budget.1>4*1024*1024*1024{return fail("私有类路径快照超过 4 GiB")};out.insert(relative.to_string(),file_hash(&at)?);if let Some(dst)=copy{std::fs::copy(at,dst.join(relative))?;}}else{return fail("类路径含非常规文件")};Ok(())
}
fn collect(entries:&[Entry],copy:bool)->Result<BTreeMap<String,String>>{
 let mut all=BTreeMap::new();let mut budget=(0usize,0u64);
 for(i,e)in entries.iter().enumerate(){
  if e.root.is_some(){let mut files=BTreeMap::new();walk(&e.source,"",&mut files,if copy{Some(&e.target)}else{None},0,&mut budget)?;for(rel,h)in files{all.insert(format!("{i}/{rel}"),h);}}
  else{let meta=e.source.metadata()?;budget.1=budget.1.saturating_add(meta.len());if !meta.is_file()||budget.1>4*1024*1024*1024{return fail("依赖快照不是文件或超过 4 GiB")};all.insert(format!("{i}/"),file_hash(&e.source)?);if copy{std::fs::copy(&e.source,&e.target)?;}}
  if all.len()>200000{return fail("快照文件数超限")}
 }
 Ok(all)
}
fn property(s:&str)->String{s.replace('\\',"\\\\").replace('\n',"\\n").replace('\r',"\\r").replace('=',"\\=").replace(':',"\\:")}
fn reject_vm_options(args:&[String])->Result<()>{for a in args{if a.starts_with("-javaagent")||a.starts_with("-agentpath")||a.starts_with("-agentlib")||a=="-cp"||a=="-classpath"||a=="--class-path"||a=="-jar"||a.starts_with("--module-path"){return fail("热替换模式不兼容另一个 Agent、调试器或自定义类路径；请使用兼容模式")}}Ok(())}
/// Return a direct Java argv, never a Maven process masquerading as Java PID.
pub async fn prepare(p:&Project,c:&RunConfig,resolved:&RunConfig,store:&Store,i:&Instance,cache:&Path,hub:Arc<Hub>)->Result<(CommandSpec,Session)>{
 let l=c.launcher.as_ref().unwrap();reject_vm_options(&l.vm_options)?;
 for key in ["JAVA_TOOL_OPTIONS","_JAVA_OPTIONS","JDK_JAVA_OPTIONS"]{if let Some(s)=resolved.env.get(key).cloned().or_else(||std::env::var(key).ok()){if s.contains("agent")||s.contains("classpath")||s.contains("class-path"){return fail(format!("{} 含额外 Agent 或类路径，当前热替换模式不兼容",key))}}}
 let java=crate::environments::select(store,"java",i.environment_id.as_deref().or(c.environment_id.as_deref()))?.program.clone();
 let layout=layout(p,c,resolved,cache,hub.clone()).await?;
 let parent=cache.join("hot-sessions");std::fs::create_dir_all(&parent)?;
 let directory=tempfile::Builder::new().prefix("instance-").tempdir_in(&parent)?;
 let base=native_path(directory.path().canonicalize()?);let mut entries=vec![];let mut roots=0;
 for (idx,source) in layout.entries.iter().enumerate(){let root=if source.is_dir(){let r=roots;roots+=1;Some(r)}else{None};let target=base.join(if root.is_some(){format!("classes-{idx}")}else{format!("dependency-{idx}.jar")});entries.push(Entry{source:source.clone(),target,root});}
 let e=entries.clone();let files=tokio::task::spawn_blocking(move||collect(&e,true)).await.map_err(|e|Error(e.to_string()))??;
 let e=entries.clone();let checked=tokio::task::spawn_blocking(move||collect(&e,false)).await.map_err(|e|Error(e.to_string()))??;
 if files!=checked{return fail("创建私有类路径期间产物变化，未启动混合版本，请重试")}
 let p1=p.clone();let c1=c.clone();let cache1=cache.to_path_buf();let model=tokio::task::spawn_blocking(move||incremental::hot_model(&p1,&c1,&cache1)).await.map_err(|e|Error(e.to_string()))??;
 if model.key!=layout.key{return fail("创建快照期间构建上下文变化，未启动")}
 let cp=base.join("classpath.txt");let cpjar=base.join("classpath.jar");std::fs::write(&cp,entries.iter().map(|e|e.target.to_string_lossy().into_owned()).collect::<Vec<_>>().join("\n"))?;
 let agent=agent()?;
 let preferred=if l.main_class.is_empty(){layout.main.clone()}else{l.main_class.clone()};
 let tool=CommandSpec{program:java.clone(),args:vec!["-cp".into(),agent.to_string_lossy().into_owned(),"noide.agent.Tool".into(),"classpath".into(),entries[0].target.to_string_lossy().into_owned(),cp.to_string_lossy().into_owned(),cpjar.to_string_lossy().into_owned(),preferred]};
 let tool=process::command(&tool,&inside(&p.root,&resolved.cwd)?,None,&[],&resolved.env)?;
 let main=process::checked(process::capture(tool,30,16384).await?)?.trim().to_string();
 if main.is_empty()||!main.chars().all(|ch|ch.is_alphanumeric()||"._$".contains(ch)){return fail("无法选择唯一主类，请在运行配置填写主类名")}
 let endpoint=base.join("endpoint");let token=id();let config=base.join("agent.properties");
 let mut props=format!("token={}\nendpoint={}\nroots={}\n",token,property(&endpoint.to_string_lossy()),roots);
 for e in &entries{if let Some(root)=e.root{props.push_str(&format!("root.{}={}\n",root,property(&e.target.to_string_lossy())));}}
 std::fs::write(&config,props)?;
 let mut args=l.vm_options.clone();for(k,v)in &l.properties{args.push(format!("-D{k}={v}"));}
 if l.trace_classes{args.push("-verbose:class".into());}
 args.extend(["-Dspring.devtools.restart.enabled=false".into(),format!("-javaagent:{}={}",agent.display(),config.display()),"-cp".into(),cpjar.to_string_lossy().into_owned(),main]);
 args.extend(l.arguments.clone());args.extend(i.args.clone());if !l.profiles.is_empty(){args.push(format!("--spring.profiles.active={}",l.profiles.join(",")));}
 hub.log(&i.id,"launch-plan","原地热替换模式：直接启动所选 Java，使用私有模块输出和依赖快照；本进程关闭 DevTools 自动重启。只有确认支持的方法体修改才原地生效；结构/资源/初始化变更等待确认重启。").await;
 Ok((CommandSpec{program:java,args},Session{_directory:directory,layout,entries,files,endpoint,token,java_pid:None}))
}
impl Session{
 pub async fn wait_ready(&mut self)->Result<()> {
  timeout(Duration::from_secs(15),async{loop{if let Ok(s)=tokio::fs::read_to_string(&self.endpoint).await{let mut lines=s.lines();let port=lines.next().and_then(|v|v.parse::<u16>().ok());let pid=lines.next().and_then(|v|v.parse::<u32>().ok());if port.is_some()&&pid.is_some(){self.java_pid=pid;return Ok(())}}tokio::time::sleep(Duration::from_millis(50)).await;}}).await.map_err(|_|Error("Java 热替换 Agent 没有就绪；请检查实际 JVM 启动日志".into()))?
 }
 pub async fn changes(&self,p:&Project,c:&RunConfig,cache:&Path)->Result<Update>{
  let p1=p.clone();let c1=c.clone();let cache1=cache.to_path_buf();let model=tokio::task::spawn_blocking(move||incremental::hot_model(&p1,&c1,&cache1)).await.map_err(|e|Error(e.to_string()))??;
  if model.key!=self.layout.key{return fail("构建配置或依赖集合变化，需要重启；旧实例继续运行")}
  let entries=self.entries.clone();let files=tokio::task::spawn_blocking(move||collect(&entries,false)).await.map_err(|e|Error(e.to_string()))??;
  if files.keys().collect::<BTreeSet<_>>()!=self.files.keys().collect::<BTreeSet<_>>(){return fail("新增或删除了类/资源，需要重启，不能用旧类冒充已应用")}
  let mut patches=vec![];let mut total=0;
  for(key,h)in &files{if self.files.get(key)==Some(h){continue}let (idx,rel)=key.split_once('/').unwrap();let entry=&self.entries[idx.parse::<usize>().map_err(|e|Error(e.to_string()))?];
   let root=entry.root.ok_or_else(||Error("第三方依赖文件变化，需要重启".into()))?;
   if !rel.ends_with(".class"){return fail(format!("资源 {} 发生变化，需要重启或专用资源刷新；未自动重启",rel))}
   let path=entry.source.join(rel);let size=path.metadata()?.len() as usize;if size>4*1024*1024{return fail("单个类超过 4 MiB，需要重启")};total+=size;
   if total>MAX_TOTAL||patches.len()>=512{return fail("本次类更新超过热替换批次上限，需要重启")}
   let bytes=std::fs::read(path)?;if hash(&bytes)!=*h{return fail("读取新类时产物变化，未应用，请重试")}
   patches.push(Patch{root,relative:rel.into(),before:self.files[key].clone(),bytes});
  }
  Ok(Update{files,patches})
 }
 pub async fn check(&self,u:&Update)->Result<String>{self.request("check",&u.patches).await}
 pub async fn apply(&mut self,u:Update)->Result<usize>{let count=u.patches.len();if count>0{self.request("apply",&u.patches).await?;}self.files=u.files;Ok(count)}
 async fn request(&self,op:&str,patches:&[Patch])->Result<String>{
  let s=tokio::fs::read_to_string(&self.endpoint).await?;let port=s.lines().next().and_then(|v|v.parse::<u16>().ok()).ok_or_else(||Error("Agent 端口无效".into()))?;
  timeout(Duration::from_secs(30),async{
   let mut socket=TcpStream::connect(("127.0.0.1",port)).await?;
   put(&mut socket,"NOIDE-HS1").await?;put(&mut socket,&self.token).await?;put(&mut socket,op).await?;socket.write_u32(patches.len() as u32).await?;
   for p in patches{socket.write_u32(p.root).await?;put(&mut socket,&p.relative).await?;put(&mut socket,&p.before).await?;socket.write_u32(p.bytes.len() as u32).await?;socket.write_all(&p.bytes).await?;}
   socket.flush().await?;let status=get(&mut socket).await?;let message=get(&mut socket).await?;
   if status!="ok"{return fail(format!("需重启，未确认热替换成功：{}",message))}Ok(message)
  }).await.map_err(|_|Error("热替换响应超时，应用状态未确认；请重启实例，不把超时当作成功".into()))?
 }
}
pub struct Update{files:BTreeMap<String,String>,patches:Vec<Patch>}
async fn put(s:&mut TcpStream,t:&str)->Result<()>{s.write_u32(t.len() as u32).await?;s.write_all(t.as_bytes()).await?;Ok(())}
async fn get(s:&mut TcpStream)->Result<String>{let n=s.read_u32().await? as usize;if n>16384{return fail("Agent 响应超限")};let mut b=vec![0;n];s.read_exact(&mut b).await?;String::from_utf8(b).map_err(|e|Error(e.to_string()))}
