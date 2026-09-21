mod environments;mod discovery;mod launch;mod groups;mod workspace;mod core;mod process;mod tools;mod runtime;mod scm;
use crate::core::*;
use axum::{Router,Json,extract::{State,Request,DefaultBodyLimit,ws::{WebSocketUpgrade,Message}},http::{StatusCode,header},middleware::{self,Next},response::{IntoResponse,Response},routing::{get,post}};
use serde::Deserialize;
use serde_json::{json,Value};
use std::{path::PathBuf,sync::Arc,io::Write};
use tokio::sync::{Mutex,Semaphore};
use tower_http::services::ServeDir;
struct App{store:Mutex<Store>,file:PathBuf,token:String,port:u16,runtime:runtime::Runtime,plans:Mutex<scm::Plans>,writes:Mutex<()>,vcs:Mutex<()>,dialogs:Mutex<()>,requests:Semaphore}
#[derive(Deserialize)]struct Call{action:String,#[serde(default)]params:Value}
fn val<T:serde::de::DeserializeOwned>(v:&Value)->Result<T>{Ok(serde_json::from_value(v.clone())?)}
fn string<'a>(v:&'a Value,k:&str)->Result<&'a str>{v.get(k).and_then(Value::as_str).ok_or_else(||Error(format!("缺少字段 {k}")))}
fn confirm(v:&Value)->Result<()>{if v.get("confirmed")==Some(&Value::Bool(true)){Ok(())}else{fail("请先确认项目受信任或确认此操作")}}
fn token_equal(a:&str,b:&str)->bool{if a.len()!=b.len(){return false}a.as_bytes().iter().zip(b.as_bytes()).fold(0u8,|x,(a,b)|x|(a^b))==0}
async fn boundary(State(s):State<Arc<App>>,req:Request,next:Next)->Response{
 let host=req.headers().get(header::HOST).and_then(|s|s.to_str().ok()).unwrap_or("");
 let hosts=[format!("127.0.0.1:{}",s.port),format!("localhost:{}",s.port)];
 if !hosts.iter().any(|h|h==host){return StatusCode::FORBIDDEN.into_response()}
 if let Some(origin)=req.headers().get(header::ORIGIN){if !hosts.iter().any(|h|origin==format!("http://{h}").as_str()){return StatusCode::FORBIDDEN.into_response()}}
 if req.uri().path()=="/api/call"{let token=req.headers().get(header::AUTHORIZATION).and_then(|v|v.to_str().ok()).and_then(|v|v.strip_prefix("Bearer ")).unwrap_or("");if !token_equal(token,&s.token){return StatusCode::UNAUTHORIZED.into_response()}}
 let Ok(_permit)=s.requests.try_acquire()else{return StatusCode::TOO_MANY_REQUESTS.into_response()};
 let mut response=next.run(req).await;
 let h=response.headers_mut();h.insert(header::CACHE_CONTROL,"no-store".parse().unwrap());h.insert("x-content-type-options","nosniff".parse().unwrap());h.insert("referrer-policy","no-referrer".parse().unwrap());h.insert("x-frame-options","DENY".parse().unwrap());
 h.insert("content-security-policy","default-src 'self'; script-src 'self' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self' ws://127.0.0.1:* ws://localhost:*; frame-ancestors 'none'; object-src 'none'; base-uri 'self'".parse().unwrap());response
}
async fn events(State(s):State<Arc<App>>,ws:WebSocketUpgrade)->Response{
 ws.max_message_size(4096).on_upgrade(move|mut socket|async move{
  let auth=tokio::time::timeout(std::time::Duration::from_secs(5),socket.recv()).await;
  let ok=match auth{Ok(Some(Ok(Message::Text(t))))=>token_equal(&t,&s.token),_=>false};if !ok{return}
  let mut rx=s.runtime.hub.tx.subscribe();
  let initial=json!({"type":"snapshot","states":s.runtime.views().await,"logs":s.runtime.hub.logs().await});
  if socket.send(Message::Text(initial.to_string().into())).await.is_err(){return}
  loop{tokio::select!{
   event=rx.recv()=>{match event{Ok(v)=>{if tokio::time::timeout(std::time::Duration::from_secs(3),socket.send(Message::Text(v.to_string().into()))).await.map(|r|r.is_err()).unwrap_or(true){break}},Err(_)=>{break}}},
   m=socket.recv()=>{match m{None|Some(Err(_))|Some(Ok(Message::Close(_)))=>break,_=>{}}}
  }}
 }).into_response()
}
async fn call(State(s):State<Arc<App>>,Json(call):Json<Call>)->Result<Json<Value>>{
 let v=&call.params;if let Some(result)=workspace::dispatch(&s,&call.action,v).await? {return Ok(Json(result));}
 let result=match call.action.as_str(){
  "state"=>json!({"store":s.store.lock().await.clone(),"runs":s.runtime.views().await}),
  "tools.detect"=>{
   let store=s.store.lock().await.clone();let mut effective=store.tools.clone();let mut overrides=ToolSettings::default();
   if let Some(pid)=v["project"].as_str(){overrides=store.project(pid)?.tools;effective.git=overrides.git.clone().or(effective.git);effective.svn=overrides.svn.clone().or(effective.svn);}
   let(mut git,mut svn)=tokio::join!(tools::detect("git",effective.git.as_ref()),tools::detect("svn",effective.svn.as_ref()));
   if overrides.git.is_some(){if let Some(c)=&mut git.selected{c.source="项目指定".into();}}
   if overrides.svn.is_some(){if let Some(c)=&mut svn.selected{c.source="项目指定".into();}}
   json!({"git":git,"svn":svn})
  },
  "tools.save"=>{
   let _guard=s.writes.lock().await;let mut settings:ToolSettings=val(&v["settings"])?;
   for p in [&mut settings.git,&mut settings.svn,&mut settings.svn_config_dir]{if p.as_ref().map(|s|s.trim().is_empty()).unwrap_or(false){*p=None}}
   if let Some(p)=&settings.git{tools::verify("git",p,"手动指定").await?;}if let Some(p)=&settings.svn{tools::verify("svn",p,"手动指定").await?;}if let Some(p)=&settings.svn_config_dir{existing_dir(p)?;}
   let mut store=s.store.lock().await;let mut updated=store.clone();if let Some(pid)=v["project"].as_str(){let p=updated.projects.iter_mut().find(|p|p.id==pid).ok_or_else(||Error("项目不存在".into()))?;p.tools=settings;}else{updated.tools=settings;}
   updated.save(&s.file)?;*store=updated;json!({"saved":true})
  },
  "fs.pick"=>{
   let _dialog=s.dialogs.try_lock().map_err(|_|Error("已有目录/文件选择窗口打开".into()))?;
   let kind=v["kind"].as_str().unwrap_or("folder");if !["folder","file"].contains(&kind){return fail("选择类型错误")}
   let mut c=tokio::process::Command::new(std::env::current_exe()?);c.arg(if kind=="folder"{"--pick-folder"}else{"--pick-file"});
   if let Some(dir)=v["directory"].as_str(){let dir=existing_dir(dir)?;c.arg("--picker-start").arg(dir);}
   let output=process::checked(process::capture(c,300,16384).await?)?;serde_json::from_str(&output)?
  },
  "project.add"=>{
   confirm(v)?;let root=existing_dir(string(v,"root")?)?;let name=string(v,"name")?.trim();text(name,100)?;
   let _guard=s.writes.lock().await;let mut store=s.store.lock().await;let mut updated=store.clone();if updated.projects.len()>=32{return fail("最多管理 32 个项目")};if updated.projects.iter().any(|p|p.root==root){return fail("项目目录已添加")}
   let mut repos=vec![];for(kind,meta)in[("git",".git"),("svn",".svn")]{if root.join(meta).exists(){repos.push(Repo{id:id(),kind:kind.into(),path:root.clone(),groups:Default::default()});}}
   let p=Project{id:id(),name:name.into(),root,tools:Default::default(),configs:vec![],instances:vec![],repos};updated.projects.push(p.clone());updated.save(&s.file)?;*store=updated;json!(p)
  },
  "config.save"|"instance.save"|"repo.add"=>{
   let _guard=s.writes.lock().await;let pid=string(v,"project")?;let mut store=s.store.lock().await;let mut updated=store.clone();let project=updated.project(pid)?;
   if call.action=="config.save"{s.runtime.forget_idle(&project).await?;}
   let all_ports:Vec<(String,u16)>=updated.projects.iter().flat_map(|p|p.instances.iter()).filter_map(|i|i.port.map(|p|(i.id.clone(),p))).collect();
   let p=updated.projects.iter_mut().find(|p|p.id==pid).unwrap();
   let object=match call.action.as_str(){
    "config.save"=>{let mut c:RunConfig=val(&v["config"])?;if c.id.is_empty(){c.id=id()};text(&c.name,100)?;if c.id.len()>100||!c.id.chars().all(|c|c.is_ascii_alphanumeric()||c=='-'||c=='_'){return fail("配置标识无效")};if c.launcher.is_some(){let resolved=launch::resolve(&store,&project,&c,None,false)?;c.command=resolved.command;c.build=resolved.build;}validate_command(&c.command)?;validate_env(&c.env)?;if let Some(b)=&c.build{validate_command(b)?;}let cwd=inside(&p.root,&c.cwd)?;if !cwd.is_dir(){return fail("工作目录不存在")};if c.watch.len()>8{return fail("监听目录最多 8 个")};for w in &c.watch{if w=="."||w.is_empty(){return fail("请指定 src 等源目录，不监听整个项目")};let path=inside(&p.root,w)?;if !path.exists(){return fail("监听路径不存在")}}
     if let Some(old)=p.configs.iter_mut().find(|x|x.id==c.id){*old=c.clone()}else{if p.configs.len()>=32{return fail("运行配置已达上限")};p.configs.push(c.clone())};json!(c)},
    "instance.save"=>{let mut i:Instance=val(&v["instance"])?;if i.id.is_empty(){i.id=id()};text(&i.name,100)?;validate_env(&i.env)?;if i.args.len()>128||i.args.iter().any(|a|a.contains('\0')||a.len()>8192){return fail("实例参数无效")};if !p.configs.iter().any(|c|c.id==i.config_id){return fail("运行配置不存在")};if let Some(eid)=&i.environment_id{let cfg=p.configs.iter().find(|c|c.id==i.config_id).unwrap();if let Some(l)=&cfg.launcher{let e=environments::select(&store,launch::runtime_kind(&l.kind),Some(eid))?;if l.kind=="java-main"{let build=environments::select(&store,"java",cfg.environment_id.as_deref())?;if e.major<build.major{return fail("实例 Java 版本低于配置的编译 JDK。请在运行配置中选择较低 JDK 编译，再让实例选择兼容版本")}};}else{return fail("高级原始命令配置不支持环境覆盖，请改用自动入口")}};if let Some(port)=i.port{if port==0||all_ports.iter().any(|(id,p)|*p==port&&*id!=i.id){return fail("端口为 0 或已被其他实例配置占用")}}
     if let Some(state)=s.runtime.states.lock().await.get(&i.id){if ["starting","running","building"].contains(&state.state.as_str()){return fail("请先停止此实例")}}
     if let Some(old)=p.instances.iter_mut().find(|x|x.id==i.id){*old=i.clone()}else{if p.instances.len()>=32{return fail("每个项目最多 32 个实例")};p.instances.push(i.clone())};json!(i)},
    _=>{let path=inside(&p.root,string(v,"path")?)?.canonicalize()?;let kind=if path.join(".git").exists(){"git"}else if path.join(".svn").exists(){"svn"}else{return fail("所选目录不是 Git/SVN 工作副本根目录")};if p.repos.len()>=16||p.repos.iter().any(|r|r.path==path){return fail("仓库已添加或达到上限")};let repo=Repo{id:id(),kind:kind.into(),path,groups:Default::default()};p.repos.push(repo.clone());json!(repo)}
   };
   updated.save(&s.file)?;*store=updated;object
  },
  "run.start"|"run.stop"|"run.update"=>{
   let _operation=if call.action=="run.start"{Some(s.writes.lock().await)}else{None};let store=s.store.lock().await.clone();let p=store.project(string(v,"project")?)?;let i=p.instances.iter().find(|i|Some(i.id.as_str())==v["instance"].as_str()).cloned().ok_or_else(||Error("实例不存在".into()))?;
   if call.action=="run.start"{s.runtime.start(p,i,store.clone()).await?}else{s.runtime.control(&p,&i,if call.action=="run.stop"{"stop"}else{"update"}).await?};json!({"accepted":true})
  },
  "vcs.status"|"vcs.diff"|"vcs.prepare"|"vcs.execute"=>{
   let _guard=s.vcs.lock().await;let _operation=if ["vcs.prepare","vcs.execute"].contains(&call.action.as_str()){Some(s.writes.lock().await)}else{None};let store=s.store.lock().await.clone();let p=store.project(string(v,"project")?)?;let r=p.repos.iter().find(|r|Some(r.id.as_str())==v["repo"].as_str()).ok_or_else(||Error("仓库不存在".into()))?;
   let client=scm::Client::new(&store,&p,r).await?;
   match call.action.as_str(){
    "vcs.status"=>{let status=client.status().await?;let mut output=json!(&status);let current=s.store.lock().await.project(&p.id)?;let groups=&current.repos.iter().find(|x|x.id==r.id).ok_or_else(||Error("仓库不存在".into()))?.groups;output["groups"]=json!(groups.items);output["group_meta"]=json!(groups);for (row,f) in output["files"].as_array_mut().unwrap().iter_mut().zip(status.files.iter()){row["group"]=json!(groups.of(&f.path,f.original.as_deref()));}output},
    "vcs.diff"=>json!({"diff":client.diff(string(v,"path")?,v["staged"].as_bool().unwrap_or(false)).await?}),
    "vcs.prepare"=>{let operation=string(v,"operation")?;if ["pull","update"].contains(&operation)&&s.runtime.project_active(&p).await{return fail("请先停止本项目实例再更新仓库，防止运行半更新代码")};let paths=val::<Vec<String>>(&v["paths"]).unwrap_or_default();let plan=s.plans.lock().await.prepare(&client,&p.id,operation,paths,v["message"].as_str().unwrap_or(""),v["group"].as_str(),v["whole_files"].as_bool().unwrap_or(false)).await?;json!(plan)},
    _=>{confirm(v)?;let token=string(v,"token")?;let mut plans=s.plans.lock().await;let plan=plans.items.get(token).ok_or_else(||Error("确认已过期".into()))?;if plan.project!=p.id{return fail("项目不匹配")};if ["pull","update"].contains(&plan.operation.as_str())&&s.runtime.project_active(&p).await{return fail("项目已经启动，请停止实例后再更新")};json!({"output":plans.execute(&client,token).await?})}
   }
  },
  "logs"=>json!(s.runtime.hub.logs().await),
  _=>return fail("未知操作"),
 };
 Ok(Json(result))
}
fn main(){if let Err(e)=entry(){eprintln!("No-ide：{e}");std::process::exit(1)}}
fn entry()->Result<()>{
 let args:Vec<String>=std::env::args().collect();
 if args.iter().any(|a|a=="--pick-folder"||a=="--pick-file"){
  let mut d=rfd::FileDialog::new().set_title("No-ide · 选择本机目录或程序");if let Some(dir)=args.iter().position(|a|a=="--picker-start").and_then(|i|args.get(i+1)){d=d.set_directory(dir);} let p=if args.iter().any(|a|a=="--pick-file"){d.pick_file()}else{d.pick_folder()};
  let p=p.map(|p|p.to_str().map(String::from).ok_or_else(||Error("所选路径不是 Unicode".into()))).transpose()?;
  println!("{}",json!({"path":p}));return Ok(())
 }
 if args.iter().any(|a|a=="--version"){println!("No-ide {}",env!("CARGO_PKG_VERSION"));return Ok(())}
 let option=|key:&str|args.iter().position(|a|a==key).and_then(|i|args.get(i+1)).cloned();
 let data=option("--data-dir").map(PathBuf::from).unwrap_or_else(||dirs::config_dir().unwrap_or_else(std::env::temp_dir).join("no-ide"));std::fs::create_dir_all(&data)?;
 #[cfg(unix)]{use std::os::unix::fs::PermissionsExt;std::fs::set_permissions(&data,std::fs::Permissions::from_mode(0o700))?;}
 let lock=std::fs::OpenOptions::new().create(true).truncate(false).read(true).write(true).open(data.join("executor.lock"))?;
 fs2::FileExt::try_lock_exclusive(&lock).map_err(|_|Error("此配置目录已有 No-ide 运行，请打开已有窗口".into()))?;
 let file=data.join("settings.json");let store=Store::load(&file)?;
 let web=option("--web-dir").map(PathBuf::from).unwrap_or_else(||std::env::current_exe().unwrap().parent().unwrap().join("web"));
 if !web.join("index.html").is_file(){return fail("找不到 web/index.html，请解压完整运行包，或通过 --web-dir 指定前端构建目录")}
 let port=option("--port").map(|p|p.parse::<u16>()).transpose().map_err(|_|Error("端口无效".into()))?.unwrap_or(17890);
 let rt=tokio::runtime::Builder::new_multi_thread().worker_threads(2).enable_all().build()?;
 rt.block_on(async{
  let listener=tokio::net::TcpListener::bind(("127.0.0.1",port)).await?;let port=listener.local_addr()?.port();let token=id();
  let s=Arc::new(App{store:Mutex::new(store),file,token:token.clone(),port,runtime:runtime::Runtime::new(),plans:Default::default(),writes:Default::default(),vcs:Default::default(),dialogs:Default::default(),requests:Semaphore::new(32)});
  let app=Router::new().route("/api/health",get(||async{Json(json!({"name":"no-ide","version":env!("CARGO_PKG_VERSION"),"platform":std::env::consts::OS,"arch":std::env::consts::ARCH}))})).route("/api/call",post(call)).route("/api/events",get(events)).fallback_service(ServeDir::new(web)).layer(DefaultBodyLimit::max(256*1024)).layer(middleware::from_fn_with_state(s.clone(),boundary)).with_state(s.clone());
  let url=format!("http://127.0.0.1:{port}/#token={token}");println!("NO_IDE_URL={url}");std::io::stdout().flush()?;
  if !args.iter().any(|a|a=="--no-open"){let u=url.clone();tokio::task::spawn_blocking(move||{let _=open::that(u);});}
  let shutdown=s.clone();axum::serve(listener,app).with_graceful_shutdown(async move{let _=tokio::signal::ctrl_c().await;shutdown.runtime.shutdown().await;tokio::time::sleep(std::time::Duration::from_secs(1)).await;}).await?;
  Ok::<_,Error>(())
 })?;drop(lock);Ok(())
}
