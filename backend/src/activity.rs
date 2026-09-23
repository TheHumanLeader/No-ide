//! A bounded, reconnectable record of the latest update per run configuration.
//! Application process state is deliberately separate from build/task state.
use crate::core::*;
use serde::Serialize;
use serde_json::{json,Value};
use std::{collections::BTreeMap,time::{SystemTime,UNIX_EPOCH}};
use tokio::sync::{broadcast,Mutex};
fn now()->u64{SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_millis() as u64}
#[derive(Clone,Serialize)]
pub struct Activity{
 pub id:String,pub project:String,pub config:String,pub instances:Vec<String>,pub kind:String,
 pub status:String,pub phase:String,pub message:String,pub detail:String,
 pub started_at:u64,pub updated_at:u64,pub finished_at:Option<u64>,pub revision:u64,
 pub cancellable:bool,pub selected:Vec<String>,pub reused:Vec<String>,pub build_mode:String,
}
impl Activity{pub fn active(&self)->bool{matches!(self.status.as_str(),"queued"|"running"|"cancelling")}}
pub struct Activities{items:Mutex<BTreeMap<String,Activity>>,tx:broadcast::Sender<Value>}
impl Activities{
 pub fn new(tx:broadcast::Sender<Value>)->Self{Self{items:Mutex::new(BTreeMap::new()),tx}}
 fn send(&self,t:&mut Activity){t.revision+=1;t.updated_at=now();let _=self.tx.send(json!({"type":"activity","data":t}));}
 pub async fn views(&self)->Vec<Activity>{self.items.lock().await.values().cloned().collect()}
 pub async fn get(&self,config:&str)->Option<Activity>{self.items.lock().await.get(config).cloned()}
 pub async fn begin(&self,project:&str,config:&str,instances:Vec<String>,kind:&str)->Result<String>{
  let mut items=self.items.lock().await;
  if items.get(config).map(Activity::active).unwrap_or(false){return fail("此配置已有更新任务，请查看进度或取消本次构建；没有重复排队")}
  if !items.contains_key(config)&&items.len()>=1024{if let Some(key)=items.iter().filter(|(_,v)|!v.active()).min_by_key(|(_,v)|v.updated_at).map(|(k,_)|k.clone()){items.remove(&key);}else{return fail("更新任务已达到上限")}}
  let mut t=Activity{id:id(),project:project.into(),config:config.into(),instances,kind:kind.into(),status:"queued".into(),phase:"queued".into(),message:"请求已接收，等待构建资源".into(),detail:String::new(),started_at:now(),updated_at:now(),finished_at:None,revision:0,cancellable:true,selected:vec![],reused:vec![],build_mode:String::new()};
  let task_id=t.id.clone();self.send(&mut t);items.insert(config.into(),t);Ok(task_id)
 }
 pub async fn phase(&self,config:&str,phase:&str,message:&str){let mut items=self.items.lock().await;if let Some(t)=items.get_mut(config){if t.active()&&t.status!="cancelling"{t.phase=phase.into();t.message=message.into();t.status="running".into();self.send(t);}}}
 pub async fn selection(&self,config:&str,selected:&[String],reused:&[String],mode:&str,reason:&str){let mut items=self.items.lock().await;if let Some(t)=items.get_mut(config){if t.active(){t.selected=selected.iter().take(256).cloned().collect();t.reused=reused.iter().take(256).cloned().collect();t.build_mode=mode.into();t.detail=reason.chars().take(1200).collect();self.send(t);}}}
 /// Expected task ID protects against a stale browser cancelling the next task.
 pub async fn cancel(&self,config:&str,expected:&str)->Result<()>{let mut items=self.items.lock().await;let t=items.get_mut(config).ok_or_else(||Error("当前没有可取消的构建".into()))?;
  if t.id!=expected||!t.active(){return fail("此任务已结束或已更换，请查看当前结果")}
  if t.status=="cancelling"{return Ok(())}
  if !t.cancellable{return fail("构建已结束，正在应用或启动，不能再取消构建；需要终止程序请用停止实例")}
  t.status="cancelling".into();t.cancellable=false;t.message="正在取消本次构建；不会因此停止原有实例".into();self.send(t);Ok(())
 }
 pub async fn cancelled(&self,config:&str)->bool{self.items.lock().await.get(config).map(|t|t.status=="cancelling").unwrap_or(false)}
 /// Serialize the cancel/apply boundary. No cancellation is advertised during a JVM mutation.
 pub async fn seal(&self,config:&str,phase:&str,message:&str)->bool{let mut items=self.items.lock().await;if let Some(t)=items.get_mut(config){if t.status=="cancelling"{return false}if t.active(){t.cancellable=false;t.status="running".into();t.phase=phase.into();t.message=message.into();self.send(t);}}true}
 pub async fn finish(&self,config:&str,status:&str,message:&str,detail:&str){let mut items=self.items.lock().await;if let Some(t)=items.get_mut(config){if !t.active(){return}t.status=status.into();t.phase="finished".into();t.message=message.into();t.detail=detail.chars().take(4000).collect();t.cancellable=false;t.finished_at=Some(now());self.send(t);}}
}
#[cfg(test)]mod tests{
 use super::*;
 #[tokio::test]async fn cancellation_is_bound_to_task_and_seals_before_apply(){let(tx,_)=broadcast::channel(32);let a=Activities::new(tx);let id=a.begin("p","c",vec!["i".into()],"apply").await.unwrap();assert!(a.begin("p","c",vec![],"apply").await.is_err());assert!(a.cancel("c","stale").await.is_err());a.cancel("c",&id).await.unwrap();assert!(!a.seal("c","applying","apply").await);a.finish("c","cancelled","cancelled","").await;let next=a.begin("p","c",vec![],"apply").await.unwrap();assert!(a.seal("c","applying","apply").await);assert!(a.cancel("c",&next).await.is_err());a.finish("c","succeeded","done","").await;assert_eq!(a.views().await.len(),1);assert!(a.get("c").await.unwrap().finished_at.is_some());}
}
