use crate::{core::*,process};
use notify::{RecommendedWatcher,Watcher,RecursiveMode,EventKind};
use serde::Serialize;
use serde_json::{json,Value};
use std::{collections::{HashMap,VecDeque},path::PathBuf,sync::{Arc,atomic::{AtomicBool,Ordering}},time::{SystemTime,UNIX_EPOCH}};
use tokio::{sync::{Mutex,broadcast,mpsc,watch,Semaphore},io::{AsyncRead,AsyncReadExt},time::{Duration,Instant,timeout}};

#[derive(Clone,Serialize,Default)]pub struct RunView{pub instance:String,pub state:String,pub pid:Option<u32>,pub error:Option<String>,pub revision:u64,pub readiness:String}
#[derive(Clone,Serialize)]pub struct Log{pub seq:u64,pub time:u64,pub instance:String,pub stream:String,pub text:String}
#[derive(Default)]struct LogBuffer{seq:u64,bytes:usize,rows:VecDeque<Log>}
pub struct Hub{pub tx:broadcast::Sender<Value>,logs:Mutex<LogBuffer>}
impl Hub{
 pub fn new()->Self{let(tx,_)=broadcast::channel(256);Self{tx,logs:Mutex::new(LogBuffer::default())}}
 pub async fn log(&self,instance:&str,stream:&str,text:&str){let text=text.chars().take(4096).collect::<String>();let mut b=self.logs.lock().await;b.seq+=1;let row=Log{seq:b.seq,time:SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_millis()as u64,instance:instance.into(),stream:stream.into(),text};b.bytes+=row.text.len();let _=self.tx.send(json!({"type":"log","data":row}));b.rows.push_back(row);while b.bytes>512*1024||b.rows.len()>2000{if let Some(r)=b.rows.pop_front(){b.bytes-=r.text.len();}}}
 pub async fn logs(&self)->Vec<Log>{self.logs.lock().await.rows.iter().cloned().collect()}
}
#[derive(Clone)]pub struct Runtime{groups:Arc<Mutex<HashMap<String,Group>>>,pub states:Arc<Mutex<HashMap<String,RunView>>>,pub hub:Arc<Hub>,builds:Arc<Semaphore>,maven_builds:Arc<Semaphore>}
#[derive(Clone)]struct Group{tx:mpsc::Sender<Control>,cancel:watch::Sender<u64>,project:String}
enum Control{Start(Instance,Store),Stop(String),Update,Shutdown}
struct Running{child:process::Managed,readers:Vec<tokio::task::JoinHandle<()>>,instance:Instance,deadline:Instant,ready:bool}
impl Runtime{
 pub fn new()->Self{Self{groups:Default::default(),states:Default::default(),hub:Arc::new(Hub::new()),builds:Arc::new(Semaphore::new(2)),maven_builds:Arc::new(Semaphore::new(1))}}
 async fn state(&self,id:&str,state:&str,pid:Option<u32>,error:Option<String>,ready:&str,bump:bool){let mut states=self.states.lock().await;let s=states.entry(id.into()).or_insert_with(||RunView{instance:id.into(),..Default::default()});s.state=state.into();s.pid=pid;s.error=error;s.readiness=ready.into();if bump{s.revision+=1;}let _=self.hub.tx.send(json!({"type":"state","data":s}));}
 pub async fn views(&self)->Vec<RunView>{self.states.lock().await.values().cloned().collect()}
 pub async fn project_active(&self,p:&Project)->bool{let s=self.states.lock().await;p.instances.iter().any(|i|s.get(&i.id).map(|v|["starting","running","building","stopping"].contains(&v.state.as_str())).unwrap_or(false))}
 pub async fn start(&self,p:Project,i:Instance,store:Store)->Result<()> {
  let cfg=p.configs.iter().find(|c|c.id==i.config_id).cloned().ok_or_else(||Error("运行配置不存在".into()))?;
  let launch_store=store.clone();let key=format!("{}/{}",p.id,cfg.id);let mut groups=self.groups.lock().await;
  if let Some(s)=self.states.lock().await.get(&i.id){if ["starting","running","building","stopping"].contains(&s.state.as_str()){return fail("实例已经运行或正在处理中")}}
  if groups.get(&key).map(|g|g.tx.is_closed()).unwrap_or(false){groups.remove(&key);}
  if !groups.contains_key(&key){let(tx,rx)=mpsc::channel(32);let(cancel,_)=watch::channel(0u64);groups.insert(key.clone(),Group{tx,cancel:cancel.clone(),project:p.id.clone()});let rt=self.clone();tokio::spawn(async move{rt.actor(p,cfg,store,rx,cancel).await;});}
  self.state(&i.id,"starting",None,None,"等待启动",false).await;
  if groups[&key].tx.try_send(Control::Start(i.clone(),launch_store)).is_err(){self.state(&i.id,"error",None,Some("操作队列已满".into()),"",false).await;return fail("操作队列已满，请稍后重试")};Ok(())
 }
 pub async fn control(&self,p:&Project,i:&Instance,op:&str)->Result<()>{let key=format!("{}/{}",p.id,i.config_id);let groups=self.groups.lock().await;let g=groups.get(&key).ok_or_else(||Error("实例尚未运行".into()))?;if op=="stop"{g.cancel.send_modify(|v|*v+=1);g.tx.try_send(Control::Stop(i.id.clone())).map_err(|_|Error("控制队列已满".into()))?;}else{g.tx.try_send(Control::Update).map_err(|_|Error("控制队列已满".into()))?;}Ok(())}
 pub async fn forget_idle(&self,p:&Project)->Result<()> {if self.project_active(p).await{return fail("修改运行配置前请先停止本项目实例")};let mut groups=self.groups.lock().await;let keys:Vec<_>=groups.iter().filter(|(_,g)|g.project==p.id).map(|(k,_)|k.clone()).collect();for k in keys{if let Some(g)=groups.remove(&k){let _=g.tx.try_send(Control::Shutdown);}}Ok(())}
 pub async fn shutdown(&self){let groups=self.groups.lock().await;for g in groups.values(){g.cancel.send_modify(|v|*v+=1);let _=g.tx.send(Control::Shutdown).await;}}
 async fn build(&self,project:&Project,cfg:&RunConfig,store:&Store,cancel:&watch::Sender<u64>,fresh:bool)->Result<()> {
  let root=&project.root;let is_maven=cfg.launcher.as_ref().map(|l|["spring-maven","maven-main"].contains(&l.kind.as_str())).unwrap_or(false);
  let mut cfg=crate::launch::resolve(store,project,cfg,None,true)?;
  if is_maven && !fresh {if let Some(b)=cfg.build.as_mut(){b.args.retain(|a|a!="clean");}}
  if let Some(b)=&cfg.build{
   let mut cancelled=cancel.subscribe();
   let run=async{
    // Two Spring entry configurations must not clean/install shared modules concurrently.
    let _maven=if is_maven{Some(self.maven_builds.acquire().await.map_err(|e|Error(e.to_string()))?)}else{None};
    let _permit=self.builds.acquire().await.map_err(|e|Error(e.to_string()))?;
    let cwd=inside(root,&cfg.cwd)?;
    if is_maven {
     let l=cfg.launcher.as_ref().unwrap();
     self.hub.log(&cfg.id,"build-plan",&format!("Maven 同工程依赖同步；{}。构建程序：{}；应用工作目录：{}；Java：{}\n构建与运行使用相同 settings.xml、本地仓库与 Maven Profile。只构建入口及其依赖，不向远程发布。",if fresh{"清理旧编译产物后构建"}else{"增量构建"},b.program,cwd.display(),cfg.env.get("JAVA_HOME").cloned().unwrap_or_default())).await;
     if l.trace_classes{self.hub.log(&cfg.id,"build-plan","已启用类加载诊断；日志量会增加，排查后请关闭。").await;}
    }
    let c=process::command(b,&cwd,None,&[],&cfg.env)?;
    let o=capture_build(c,if is_maven{900}else{120},self.hub.clone(),cfg.id.clone(),cfg.output_encoding).await?;
    process::checked(o)?;Ok::<_,Error>(())
   };
   tokio::select!{r=run=>r,_=cancelled.changed()=>fail("构建已取消")}
  }else{Ok(())}
 }
 async fn launch(&self,project:&Project,cfg:&RunConfig,store:&Store,i:Instance)->Result<Running>{
  let root=&project.root;let cfg=crate::launch::resolve(store,project,cfg,Some(&i),true)?;
  if let Some(port)=i.port{if matches!(timeout(Duration::from_millis(200),tokio::net::TcpStream::connect(("127.0.0.1",port))).await,Ok(Ok(_))){return fail(format!("端口 {port} 已有监听程序，未启动实例"));}}
  let cwd=inside(root,&cfg.cwd)?;if !cwd.is_dir(){return fail("运行目录不存在")}
  let mut env=cfg.env.clone();if cfg.launcher.is_none(){env.extend(i.env.clone());}let extra=if cfg.launcher.is_some(){&[][..]}else{i.args.as_slice()};let cmd=process::command(&cfg.command,&cwd,i.port,extra,&env)?;self.hub.log(&i.id,"launch-plan",&format!("启动程序：{}\n工作目录：{}\n所选 Java：{}",cfg.command.program,cwd.display(),env.get("JAVA_HOME").map(String::as_str).unwrap_or("非 Java / 高级命令"))).await;
  let mut child=process::spawn(cmd)?;
  let encoding=cfg.output_encoding;let mut readers=vec![];if let Some(o)=child.0.stdout().take(){let hub=self.hub.clone();let id=i.id.clone();readers.push(tokio::spawn(async move{pump(o,hub,id,"stdout",encoding).await}));}if let Some(e)=child.0.stderr().take(){let hub=self.hub.clone();let id=i.id.clone();readers.push(tokio::spawn(async move{pump(e,hub,id,"stderr",encoding).await}));}
  self.state(&i.id,if i.port.is_some(){"starting"}else{"running"},child.0.id(),None,if i.port.is_some(){"等待 TCP 端口"}else{"进程已启动；未配置应用就绪检查"},true).await;
  Ok(Running{child,readers,instance:i,deadline:Instant::now()+Duration::from_secs(if cfg.launcher.as_ref().map(|l|l.kind=="spring-maven").unwrap_or(false){120}else{30}),ready:false})
 }
 async fn stop_run(&self,mut r:Running){self.state(&r.instance.id,"stopping",r.child.0.id(),None,"",false).await;let _=r.child.0.start_kill();let _=timeout(Duration::from_secs(3),r.child.0.wait()).await;for t in r.readers{t.abort();}self.state(&r.instance.id,"stopped",None,None,"",false).await;}
 async fn actor(self,project:Project,cfg:RunConfig,mut store:Store,mut rx:mpsc::Receiver<Control>,cancel:watch::Sender<u64>){
  let root=project.root.clone();
  let deleted=Arc::new(AtomicBool::new(false));
  let mut watch_paths=cfg.watch.clone();
  if !watch_paths.is_empty(){if let Some(l)=&cfg.launcher{if ["spring-maven","maven-main"].contains(&l.kind.as_str()){
   match inside(&root,&cfg.cwd).and_then(|cwd|crate::launch::maven::resolve(&root,&cwd,l)).and_then(|plan|plan.watch_paths(&root)){
    Ok(paths)=>watch_paths.extend(paths),Err(e)=>self.hub.log(&cfg.id,"error",&format!("依赖模块监听未扩展：{}",e.0)).await,
   }
  }}}
  watch_paths.sort();watch_paths.dedup();
  let mut children:HashMap<String,Running>=HashMap::new();let(evtx,mut evrx)=mpsc::channel(1);let mut watcher:Option<RecommendedWatcher>=None;let mut watch_failed=false;
  loop{
   enum Event{Control(Option<Control>),Files,Tick}
   let event=tokio::select!{c=rx.recv()=>Event::Control(c),Some(_)=evrx.recv(),if !children.is_empty()=>Event::Files,_=tokio::time::sleep(Duration::from_millis(250)),if !children.is_empty()=>Event::Tick};
   match event{
    Event::Control(None)|Event::Control(Some(Control::Shutdown))=>break,
    Event::Control(Some(Control::Start(i,snapshot)))=>{
     store=snapshot;
     if children.contains_key(&i.id){continue}
     let result=if children.is_empty(){self.build(&project,&cfg,&store,&cancel,true).await}else{Ok(())};
     match result{Ok(())=>match self.launch(&project,&cfg,&store,i.clone()).await{Ok(r)=>{children.insert(i.id.clone(),r);},Err(e)=>self.state(&i.id,"error",None,Some(e.0),"",false).await},Err(e)=>self.state(&i.id,"error",None,Some(e.0),"",false).await}
    },
    Event::Control(Some(Control::Stop(id)))=>{if let Some(r)=children.remove(&id){self.stop_run(r).await;}else{self.state(&id,"stopped",None,None,"",false).await;}},
    e @ (Event::Files|Event::Control(Some(Control::Update)))=>{
     let manual=matches!(e,Event::Control(Some(Control::Update)));
     if children.is_empty(){continue}tokio::time::sleep(Duration::from_millis(350)).await;while evrx.try_recv().is_ok(){}
     for r in children.values(){self.state(&r.instance.id,"building",r.child.0.id(),None,"旧进程保留，正在构建",false).await;}
     let fresh=deleted.swap(false,Ordering::AcqRel)||manual;
     match self.build(&project,&cfg,&store,&cancel,fresh).await{
      Err(e)=>{for r in children.values(){self.state(&r.instance.id,"running",r.child.0.id(),Some(e.0.clone()),"构建失败；No-ide 未停止旧进程",false).await;}},
      Ok(())=>{let old=std::mem::take(&mut children);for(_,r)in old{let i=r.instance.clone();self.stop_run(r).await;match self.launch(&project,&cfg,&store,i.clone()).await{Ok(r)=>{children.insert(i.id.clone(),r);},Err(e)=>self.state(&i.id,"error",None,Some(e.0),"",false).await}}}
     }
    },
    Event::Tick=>{
     let mut remove=vec![];for(id,r)in children.iter_mut(){match r.child.0.try_wait(){Ok(Some(status))=>{self.state(id,if status.success(){"exited"}else{"error"},None,if status.success(){None}else{Some(format!("进程退出：{status}"))},"",false).await;remove.push(id.clone());},Err(e)=>{self.hub.log(id,"error",&e.to_string()).await;remove.push(id.clone());},_=>{if !r.ready{if let Some(port)=r.instance.port{if matches!(timeout(Duration::from_millis(100),tokio::net::TcpStream::connect(("127.0.0.1",port))).await,Ok(Ok(_))){r.ready=true;self.state(id,"running",r.child.0.id(),None,"TCP 端口已响应；不等于业务健康检查",false).await;}else if Instant::now()>r.deadline{self.state(id,"error",r.child.0.id(),Some("就绪检查超时，已结束该实例".into()),"",false).await;remove.push(id.clone());}}else{r.ready=true;}}}}}
     for id in remove{if let Some(mut r)=children.remove(&id){let _=r.child.0.start_kill();let _=timeout(Duration::from_secs(3),r.child.0.wait()).await;for t in r.readers{t.abort();}}}
    }
   }
   if children.is_empty(){watcher.take();watch_failed=false;}else if watcher.is_none()&&!watch_failed&&!watch_paths.is_empty(){
    let tx=evtx.clone();let watched=make_watcher(&root,&watch_paths,tx,deleted.clone());match watched{Ok(w)=>watcher=Some(w),Err(e)=>{watch_failed=true;self.hub.log(&cfg.id,"error",&format!("文件监听未启用：{}",e.0)).await;}}
   }
  }
  drop(watcher);for(_,r)in children{self.stop_run(r).await;}
 }
}
async fn log_chunks(hub:&Hub,id:&str,stream:&str,text:&str){
 // Hub rows remain bounded, but do not silently discard all output after row 1.
 let mut chunk=String::new();let mut count=0;
 for ch in text.chars(){chunk.push(ch);count+=1;if count==4096{hub.log(id,stream,&chunk).await;chunk.clear();count=0;}}
 if !chunk.is_empty(){hub.log(id,stream,&chunk).await;}
}
async fn pump<R:AsyncRead+Unpin>(mut r:R,hub:Arc<Hub>,id:String,stream:&str,encoding:crate::process::text_output::OutputEncoding){
 let mut decoder=crate::process::text_output::TextDecoder::new(encoding);let mut warned=false;let mut b=[0u8;4096];
 loop{
  let n=match r.read(&mut b).await{Ok(n)=>n,Err(e)=>{hub.log(&id,"error",&format!("读取 {stream} 日志失败：{e}")).await;break}};
  let piece=decoder.push(&b[..n],n==0);
  if piece.replacements&&!warned{warned=true;hub.log(&id,"encoding",&crate::process::text_output::warning(piece.encoding)).await;}
  if !piece.text.is_empty(){log_chunks(&hub,&id,stream,&piece.text).await;}
  if n==0{break}
 }
}

fn make_watcher(root:&std::path::Path,paths:&[String],tx:mpsc::Sender<()>,deleted:Arc<AtomicBool>)->Result<RecommendedWatcher>{
 let mut w=notify::recommended_watcher(move|e:notify::Result<notify::Event>|{if let Ok(e)=e{if matches!(e.kind,EventKind::Create(_)|EventKind::Modify(_)|EventKind::Remove(_))&&e.paths.iter().any(|p|!p.components().any(|c|[".git",".svn","target","build","dist","node_modules",".venv","__pycache__"].iter().any(|x|c.as_os_str()==*x))){if matches!(e.kind,EventKind::Remove(_)|EventKind::Modify(notify::event::ModifyKind::Name(_))){deleted.store(true,Ordering::Release);}let _=tx.try_send(());}}}).map_err(|e|Error(e.to_string()))?;
 for p in paths{if p=="."||p.is_empty(){return fail("请监听 src 等源目录，不监听整个项目")};let p=inside(root,p)?;w.watch(&p,RecursiveMode::Recursive).map_err(|e|Error(e.to_string()))?;}Ok(w)
}

async fn build_pipe<R:AsyncRead+Unpin>(mut r:R,hub:Arc<Hub>,id:String,encoding:crate::process::text_output::OutputEncoding)->Result<String>{
 let mut decoder=crate::process::text_output::TextDecoder::new(encoding);let mut tail=String::new();let mut b=[0u8;4096];let mut warned=false;
 loop{let n=r.read(&mut b).await?;let part=decoder.push(&b[..n],n==0);
  if part.replacements&&!warned{warned=true;hub.log(&id,"encoding",&crate::process::text_output::warning(part.encoding)).await;}
  log_chunks(&hub,&id,"build",&part.text).await;tail.push_str(&part.text);
  if tail.len()>32768{let mut cut=tail.len()-32768;while !tail.is_char_boundary(cut){cut+=1;}tail.drain(..cut);}
  if n==0{break}
 }Ok(tail)
}
async fn capture_build(c:tokio::process::Command,seconds:u64,hub:Arc<Hub>,id:String,encoding:crate::process::text_output::OutputEncoding)->Result<process::Output>{
 let mut child=process::spawn(c)?;
 let out=child.0.stdout().take().ok_or_else(||Error("构建标准输出未连接".into()))?;
 let err=child.0.stderr().take().ok_or_else(||Error("构建错误输出未连接".into()))?;
 let result=timeout(Duration::from_secs(seconds),async {
  let (status,stdout,stderr)=tokio::try_join!(async{child.0.wait().await.map_err(Error::from)},build_pipe(out,hub.clone(),id.clone(),encoding),build_pipe(err,hub,id,encoding))?;
  Ok::<_,Error>(process::Output{code:status.code().unwrap_or(-1),stdout,stderr,warnings:vec![]})
 }).await;
 let _=child.0.start_kill();let _=timeout(Duration::from_secs(3),child.0.wait()).await;
 result.map_err(|_|Error("构建超时，已请求停止受控构建进程；未启动新实例".into()))?
}
