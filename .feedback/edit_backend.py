from pathlib import Path
root=Path.cwd()
p=root/'backend/src/runtime.rs';s=p.read_text()
s=s.replace('pub struct Hub{pub tx:broadcast::Sender<Value>,logs:Mutex<LogBuffer>}', 'pub struct Hub{pub tx:broadcast::Sender<Value>,logs:Mutex<LogBuffer>,pub activities:crate::activity::Activities}')
s=s.replace('Self{tx,logs:Mutex::new(LogBuffer::default())}', 'Self{activities:crate::activity::Activities::new(tx.clone()),tx,logs:Mutex::new(LogBuffer::default())}')
start=s.index(' pub async fn control(');end=s.index(' pub async fn forget_idle',start)
s=s[:start]+''' pub async fn control(&self,p:&Project,i:&Instance,op:&str)->Result<()>{
  let key=format!("{}/{}",p.id,i.config_id);let groups=self.groups.lock().await;let g=groups.get(&key).ok_or_else(||Error("实例尚未运行".into()))?;
  if op=="stop"{
   if let Some(t)=self.hub.activities.get(&i.config_id).await{if t.active()&&t.cancellable{let _=self.hub.activities.cancel(&i.config_id,&t.id).await;}}
   g.cancel.send_modify(|v|*v+=1);g.tx.try_send(Control::Stop(i.id.clone())).map_err(|_|Error("控制队列已满".into()))?;
  }else{
   let states=self.states.lock().await;
   if !states.get(&i.id).map(|v|v.state=="running").unwrap_or(false){return fail("请等待实例启动或当前操作结束后再更新")}
   if p.instances.iter().any(|x|x.config_id==i.config_id&&states.get(&x.id).map(|v|matches!(v.state.as_str(),"starting"|"building"|"stopping")).unwrap_or(false)){return fail("同配置实例正在启动或处理中，请等待其结束")}
   let ids=if op=="restart"{vec![i.id.clone()]}else{p.instances.iter().filter(|x|x.config_id==i.config_id&&states.get(&x.id).map(|v|v.state=="running").unwrap_or(false)).map(|x|x.id.clone()).collect()};drop(states);
   self.hub.activities.begin(&p.id,&i.config_id,ids,if op=="repair"{"repair"}else if op=="restart"{"restart"}else{"apply"}).await?;
   let command=if op=="restart"{Control::Restart(i.id.clone())}else{Control::Update(op=="repair")};
   if g.tx.try_send(command).is_err(){self.hub.activities.finish(&i.config_id,"failed","更新请求未排入队列","操作队列已满，请稍后再试").await;return fail("控制队列已满")}
  }Ok(())
 }
 pub async fn cancel_build(&self,p:&Project,i:&Instance,task_id:&str)->Result<()>{let groups=self.groups.lock().await;let key=format!("{}/{}",p.id,i.config_id);let g=groups.get(&key).ok_or_else(||Error("配置任务已结束".into()))?;self.hub.activities.cancel(&i.config_id,task_id).await?;g.cancel.send_modify(|v|*v+=1);Ok(())}
 async fn update_failed(&self,cfg:&RunConfig,children:&HashMap<String,Running>,e:Error){
  let cancelled=self.hub.activities.cancelled(&cfg.id).await||e.0.starts_with("构建已取消");
  let message=if cancelled{"本次构建已取消；No-ide 未停止原有实例"}else{"构建失败；改动尚未生效"};
  for r in children.values(){self.state(&r.instance.id,"running",r.child.0.id(),if cancelled{None}else{Some(e.0.clone())},message,false).await;self.update_result(&r.instance.id,if cancelled{"cancelled"}else{"build-failed"},Some(e.0.clone())).await;}
  self.hub.activities.finish(&cfg.id,if cancelled{"cancelled"}else{"failed"},message,&e.0).await;
 }
 async fn settle_activity(&self,cfg:&RunConfig){
  let Some(t)=self.hub.activities.get(&cfg.id).await else{return};if !t.active()||t.phase!="waiting"{return}
  let states=self.states.lock().await;let views:Vec<_>=t.instances.iter().filter_map(|id|states.get(id)).collect();
  let result=if let Some(v)=views.iter().find(|v|v.state=="error"||v.state=="exited"){Some(("failed","构建结束，但新实例未成功就绪",v.error.clone().unwrap_or_else(||"新进程已经退出".into())))}
   else if views.iter().any(|v|v.state=="stopped"){Some(("cancelled","实例已停止；不再等待启动结果","没有将停止视为更新成功".into()))}
   else if views.len()==t.instances.len()&&views.iter().all(|v|v.state=="running"){Some(("succeeded","更新完成 · 新进程已启动",views.iter().map(|v|v.readiness.clone()).collect::<Vec<_>>().join("；")))}else{None};drop(states);
  if let Some((status,message,detail))=result{self.hub.activities.finish(&cfg.id,status,message,&detail).await;}
 }
''' + s[end:]
s=s.replace('  if let Some(s)=self.states.lock().await.get(&i.id)', '  if self.hub.activities.get(&cfg.id).await.map(|t|t.active()).unwrap_or(false){return fail("此配置正在更新，请等当前任务结束后再启动实例")}\n  if let Some(s)=self.states.lock().await.get(&i.id)',1)
s=s.replace('  let cfg=crate::launch::resolve(store,project,original,None,true)?;let mut cancelled=cancel.subscribe();', '''  let mut cancelled=cancel.subscribe();
  if self.hub.activities.cancelled(&original.id).await{return fail("构建已取消；没有启动新的构建进程")}
  let cfg=crate::launch::resolve(store,project,original,None,true)?;
  self.hub.activities.phase(&cfg.id,"queued","等待构建资源；原有实例继续运行").await;''')
s=s.replace('   if is_maven{return crate::incremental::build', '   self.hub.activities.phase(&cfg.id,"checking","正在检查源码、依赖与已有产物").await;\n   if is_maven{return crate::incremental::build')
s=s.replace('   if let Some(b)=&cfg.build{let c=process::command', '   if let Some(b)=&cfg.build{self.hub.activities.phase(&cfg.id,"building","正在执行构建；原有实例继续运行").await;let c=process::command')
s=s.replace('tokio::select!{r=run=>r,_=cancelled.changed()=>fail(', 'tokio::select!{biased;_=cancelled.changed()=>fail(').replace('"构建已取消；未把未完成产物标为最新")}', '"构建已取消；未把未完成产物标为最新"),r=run=>r}')
start=s.index('    Event::Control(Some(Control::Restart(id)))=>');end=s.index('    Event::Tick=>',start)
s=s[:start]+'''    Event::Control(Some(Control::Restart(id)))=>{
     if !children.contains_key(&id){self.hub.activities.finish(&cfg.id,"cancelled","实例已停止","没有执行重启").await;continue}
     self.state(&id,"building",children[&id].child.0.id(),None,"检查当前源码，准备重启此实例",false).await;
     match self.build(&project,&cfg,&store,&cancel,false).await{
      Err(e)=>{self.update_failed(&cfg,&children,e).await;while evrx.try_recv().is_ok(){}},
      Ok(_)=>{if !self.hub.activities.seal(&cfg.id,"restarting","构建完成，正在重启选中的实例").await{self.update_failed(&cfg,&children,Error("构建已取消，未重启实例".into())).await;continue}
       let r=children.remove(&id).unwrap();let i=r.instance.clone();self.stop_run(r).await;
       match self.launch(&project,&cfg,&store,i).await{Ok(r)=>{children.insert(id,r);self.hub.activities.phase(&cfg.id,"waiting","新进程已启动，等待就绪检查").await;},Err(e)=>{self.state(&id,"error",None,Some(e.0.clone()),"",false).await;self.hub.activities.finish(&cfg.id,"failed","构建完成，但实例启动失败",&e.0).await;}}
      }
     }
    },
    e @ (Event::Files|Event::Control(Some(Control::Update(_))))=>{
     let manual=matches!(e,Event::Control(Some(Control::Update(_))));let force=matches!(e,Event::Control(Some(Control::Update(true))));
     if children.is_empty(){if manual{self.hub.activities.finish(&cfg.id,"cancelled","实例已停止，未执行更新","").await;}continue}
     if !manual{let ids=children.keys().cloned().collect();if self.hub.activities.begin(&project.id,&cfg.id,ids,"auto").await.is_err(){continue}}
     tokio::time::sleep(Duration::from_millis(350)).await;while evrx.try_recv().is_ok(){}
     for r in children.values(){self.state(&r.instance.id,"building",r.child.0.id(),None,"旧进程保留，正在检查本次改动",false).await;self.update_result(&r.instance.id,"building",None).await;}
     deleted.store(false,Ordering::Release);
     let result=self.build(&project,&cfg,&store,&cancel,force).await;
     match result{
      Err(e)=>{self.update_failed(&cfg,&children,e).await;while evrx.try_recv().is_ok(){}},
      Ok(changed)=>{
       if !self.hub.activities.seal(&cfg.id,"applying","构建与内容复核完成，正在应用改动").await{self.update_failed(&cfg,&children,Error("构建已取消；没有应用本次改动".into())).await;while evrx.try_recv().is_ok(){};continue}
       if crate::hot::enabled(&cfg)&&!force{
        match self.apply_hot(&project,&cfg,&mut children).await{
         Ok(())=>{let states=self.states.lock().await;let any=children.keys().any(|id|states.get(id).map(|s|s.update_status=="hotswapped").unwrap_or(false));drop(states);self.hub.activities.finish(&cfg.id,"succeeded",if any{"改动已生效 · 已原地热替换"}else{"运行内容已是最新 · 未重启"},"Java 进程未重启；无需等待应用重新初始化").await;},
         Err(e)=>{for r in children.values(){self.state(&r.instance.id,"running",r.child.0.id(),None,"本次改动尚未全部生效，需要确认重启",false).await;self.update_result(&r.instance.id,"restart-required",Some(e.0.clone())).await;self.hub.log(&r.instance.id,"update-pending",&e.0).await;}self.hub.activities.finish(&cfg.id,"restart-required","构建完成 · 需要重启才能完整生效",&e.0).await;}
        }
       }else if !changed&&!force{
        for r in children.values(){self.state(&r.instance.id,"running",r.child.0.id(),None,"源码与产物一致；未构建、未重启",false).await;self.update_result(&r.instance.id,"current",None).await;}
        self.hub.activities.finish(&cfg.id,"succeeded","已是最新 · 无需构建或重启","已核对本地源码与产物；没有跳过最新性检查").await;
       }else{
        self.hub.activities.phase(&cfg.id,"restarting","构建完成，正在重启受影响实例").await;
        let old=std::mem::take(&mut children);let mut failed=None;for(_,r)in old{let i=r.instance.clone();self.stop_run(r).await;match self.launch(&project,&cfg,&store,i.clone()).await{Ok(r)=>{children.insert(i.id.clone(),r);},Err(e)=>{self.state(&i.id,"error",None,Some(e.0.clone()),"",false).await;failed=Some(e.0);}}}
        if let Some(e)=failed{self.hub.activities.finish(&cfg.id,"failed","构建完成，但部分实例启动失败",&e).await;}else{self.hub.activities.phase(&cfg.id,"waiting","新进程已启动，等待就绪检查").await;}
       }
      }
     }
    },
''' + s[end:]
s=s.replace('   if children.is_empty(){watcher.take();', '   self.settle_activity(&cfg).await;\n   if children.is_empty(){watcher.take();')
s=s.replace('  drop(watcher);for(_,r)in children', '  self.hub.activities.finish(&cfg.id,"cancelled","执行器正在退出；任务已终止","").await;\n  drop(watcher);for(_,r)in children')
p.write_text(s)
p=root/'backend/src/main.rs';s=p.read_text().replace('mod hot;', 'mod activity;mod hot;',1)
s=s.replace('"logs":s.runtime.hub.logs().await}', '"logs":s.runtime.hub.logs().await,"activities":s.runtime.hub.activities.views().await}')
s=s.replace('"runs":s.runtime.views().await}', '"runs":s.runtime.views().await,"activities":s.runtime.hub.activities.views().await}')
s=s.replace('"run.start"|"run.stop"|"run.update"', '"run.cancel"|"run.start"|"run.stop"|"run.update"')
s=s.replace('if call.action=="run.start"{s.runtime.start(p,i,store.clone()).await?}', 'if call.action=="run.cancel"{s.runtime.cancel_build(&p,&i,string(v,"task_id")?).await?}else if call.action=="run.start"{s.runtime.start(p,i,store.clone()).await?}')
p.write_text(s)
p=root/'backend/src/incremental.rs';s=p.read_text()
s=s.replace(' let started=Instant::now();let root=project.root.clone();', ' hub.activities.phase(&cfg.id,"checking","正在核对源码和产物内容；尚未开始编译").await;\n let started=Instant::now();let root=project.root.clone();',1)
s=s.replace('None=>{hub.log(&cfg.id,"build-plan",', 'None=>{hub.activities.phase(&cfg.id,"model","正在读取 Maven 模块模型；首次或配置变更时需要").await;hub.log(&cfg.id,"build-plan",',1)
s=s.replace('  let dep_changed=', '  hub.activities.phase(&cfg.id,"checking","正在比较源码、依赖和编译输出指纹").await;\n  let dep_changed=',1)
s=s.replace('  execute(cfg.build.as_ref().unwrap(),cfg,&root,hub.clone()).await?;', '  hub.activities.phase(&cfg.id,"building","模型不适用，按原构建范围执行；请展开原因").await;\n  execute(cfg.build.as_ref().unwrap(),cfg,&root,hub.clone()).await?;',1)
s=s.replace(' hub.log(&cfg.id,"build-selection",&serde_json::to_string(&report)?).await;', ' hub.activities.selection(&cfg.id,&report.selected,&report.reused,&report.mode,&report.reason).await;\n hub.log(&cfg.id,"build-selection",&serde_json::to_string(&report)?).await;',1)
s=s.replace(' execute(&command,cfg,&root,hub.clone()).await?;', ' hub.activities.phase(&cfg.id,"building",&format!("正在构建 {} 个模块，复用 {} 个",report.selected.len(),report.reused.len())).await;\n execute(&command,cfg,&root,hub.clone()).await?;\n hub.activities.phase(&cfg.id,"verifying","编译结束，正在复核输入与输出；尚未应用").await;',1)
p.write_text(s)
for name in ['backend/Cargo.toml','package.json']:
 p=root/name;p.write_text(p.read_text().replace('0.5.0','0.5.1'))
