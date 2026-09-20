use crate::{core::*,process,tools};
use serde::{Serialize,Deserialize};
use std::{collections::{HashMap,HashSet},path::Path,time::{Instant,Duration},io::{Read,Write}};
use tokio::process::Command;
use sha2::{Sha256,Digest};
const LIMIT:usize=1024*1024;
#[derive(Clone,Serialize,Deserialize)]pub struct Change{pub path:String,pub status:String,pub staged:bool,pub worktree:bool,pub conflict:bool,pub original:Option<String>}
#[derive(Clone,Serialize)]pub struct Status{pub kind:String,pub branch:String,pub remote:String,pub push_remote:String,pub files:Vec<Change>,pub snapshot:String}
#[derive(Clone)]pub struct Client{pub kind:String,pub executable:String,pub repo:Repo,pub svn_config:Option<String>}
impl Client{
 pub async fn new(s:&Store,p:&Project,r:&Repo)->Result<Self>{
  if !r.path.canonicalize()?.starts_with(p.root.canonicalize()?){return fail("仓库已移动或链接越过项目目录")}
  let mut repo=r.clone();repo.path=native_path(repo.path.canonicalize()?);
  Ok(Self{kind:r.kind.clone(),executable:tools::resolve(&r.kind,&s.tools,&p.tools).await?,repo,svn_config:p.tools.svn_config_dir.clone().or(s.tools.svn_config_dir.clone())})
 }
 fn command(&self,args:&[String])->Command{
  let mut c=Command::new(&self.executable);c.current_dir(&self.repo.path);
  c.env("GIT_TERMINAL_PROMPT","0").env("GCM_INTERACTIVE","Never");
  if self.kind=="git"{c.args(["--no-pager","--literal-pathspecs","-c","color.ui=false","-c","core.quotePath=false"]);}else{c.args(["--non-interactive","--no-auth-cache"]);if let Some(d)=&self.svn_config{c.args(["--config-dir",d]);}}
  c.args(args);c
 }
 async fn run(&self,args:&[&str])->Result<process::Output>{self.run_vec(args.iter().map(|s|s.to_string()).collect()).await}
 async fn run_vec(&self,args:Vec<String>)->Result<process::Output>{let mut o=process::capture(self.command(&args),120,LIMIT).await?;o.stderr=redact(&o.stderr);Ok(o)}
 async fn read(&self,args:&[&str])->Result<String>{process::checked(self.run(args).await?)}
 pub async fn status(&self)->Result<Status>{
  if self.kind=="git"{
   let top=self.read(&["rev-parse","--show-toplevel"]).await?;if Path::new(top.trim()).canonicalize()?!=self.repo.path.canonicalize()?{return fail("请选择实际 Git 仓库根目录，不能把父仓库误当成本项目")}
   let raw=self.read(&["status","--porcelain=v1","-z","--untracked-files=all"]).await?;let files=parse_git(&raw)?;
   let b=self.run(&["symbolic-ref","--quiet","--short","HEAD"]).await?;let branch=if b.code==0{b.stdout.trim().to_string()}else{"(detached HEAD)".into()};
   let h=self.run(&["rev-parse","--verify","HEAD"]).await?;
   let index=self.read(&["diff","--cached","--raw","--no-abbrev","--no-renames"]).await?;
   let remote=self.run(&["remote","get-url","origin"]).await?;let remote=if remote.code==0{remote.stdout.trim().to_string()}else{String::new()};
   let push=self.run(&["remote","get-url","--push","--all","origin"]).await?;let push_remote=if push.code==0{push.stdout.trim().to_string()}else{String::new()};
   let snapshot=digest(&[&raw,&index,&h.stdout,&branch,&remote,&push_remote]);Ok(Status{kind:"git".into(),branch,remote:redact(&remote),push_remote:redact(&push_remote),files,snapshot})
  }else{
   let raw=self.read(&["status","--xml","--ignore-externals"]).await?;
   let files=parse_svn(&raw)?;let info=self.read(&["info","--xml","--depth","empty","."]).await?;
   let doc=roxmltree::Document::parse(&info).map_err(|e|Error(e.to_string()))?;
   let entry=doc.descendants().find(|n|n.has_tag_name("entry")).ok_or_else(||Error("无法读取 SVN 元数据".into()))?;
   let branch=format!("r{}",entry.attribute("revision").unwrap_or("?"));
   let remote=doc.descendants().find(|n|n.has_tag_name("url")).and_then(|n|n.text()).unwrap_or("").to_string();
   Ok(Status{kind:"svn".into(),branch,push_remote:redact(&remote),remote:redact(&remote),files,snapshot:digest(&[&canonical_xml(&raw)?,&canonical_xml(&info)?])})
  }
 }
 pub async fn diff(&self,path:&str,staged:bool)->Result<String>{
  if self.kind=="svn"&&path.contains('@'){return fail("本版暂不处理包含 @ 的 SVN 文件路径，请使用本机 SVN 客户端处理该文件")}
  let target=vcs_path(&self.repo.path,path)?;let status=self.status().await?;
  let f=status.files.iter().find(|f|f.path==path).ok_or_else(||Error("此文件不在当前变更列表中，请刷新".into()))?;
  if f.status=="??"||f.status=="unversioned"{
   if !target.is_file(){return fail("未跟踪目录请逐个添加文件；不递归展开")}
   if target.metadata()?.len()>512*1024{return fail("文件超过 512 KiB，未加载")}
   let mut b=Vec::new();std::fs::File::open(target)?.take(512*1024+1).read_to_end(&mut b)?;if b.len()>512*1024{return fail("文件超过 512 KiB，未加载")};if b.contains(&0){return fail("二进制文件暂不显示文本差异")}
   let s=String::from_utf8(b).map_err(|_|Error("文件不是 UTF-8，暂不显示文本差异".into()))?;
   return Ok(format!("--- /dev/null\n+++ {path}\n{}",s.lines().map(|l|format!("+{l}\n")).collect::<String>()));
  }
  if self.kind=="git"{let mut args=vec!["diff","--no-ext-diff","--no-textconv"];if staged{args.push("--cached")};args.extend(["--",path]);self.read(&args).await}else{self.read(&["diff","--internal-diff","--depth","empty","--",path]).await}
 }
}
fn digest(parts:&[&str])->String{let mut h=Sha256::new();for p in parts{h.update((p.len()as u64).to_le_bytes());h.update(p.as_bytes());}format!("{:x}",h.finalize())}
// SVN's XML attribute ordering is not stable across invocations. Compare semantic
// elements, attributes, text and revision data rather than raw serializer bytes.
fn canonical_xml(raw:&str)->Result<String>{
 fn visit(n:roxmltree::Node<'_, '_>)->String{
  let mut attrs:Vec<_>=n.attributes().map(|a|(a.name(),a.value())).collect();attrs.sort_unstable();
  let mut children:Vec<_>=n.children().filter(|c|c.is_element()).map(visit).collect();children.sort_unstable();
  let text=n.children().filter(|c|c.is_text()).filter_map(|c|c.text()).map(str::trim).filter(|s|!s.is_empty()).collect::<Vec<_>>();
  let encoded=serde_json::to_string(&(n.tag_name().name(),attrs,text,children)).expect("XML strings serialize");digest(&[&encoded])
 }
 let doc=roxmltree::Document::parse(raw).map_err(|e|Error(e.to_string()))?;Ok(visit(doc.root_element()))
}
pub fn parse_git(raw:&str)->Result<Vec<Change>>{
 let mut list=vec![];let mut parts=raw.split('\0').filter(|p|!p.is_empty());
 while let Some(p)=parts.next(){if p.len()<4||!p.is_char_boundary(3){return fail("Git 状态格式无效")};let x=p.as_bytes()[0]as char;let y=p.as_bytes()[1]as char;let renamed=x=='R'||x=='C'||y=='R'||y=='C';let original=if renamed{Some(parts.next().ok_or_else(||Error("Git 重命名记录不完整".into()))?.to_string())}else{None};list.push(Change{path:p[3..].into(),status:p[..2].into(),staged:x!=' '&&x!='?',worktree:y!=' '||x=='?',conflict:x=='U'||y=='U'||(x=='A'&&y=='A')||(x=='D'&&y=='D'),original});if list.len()>2000{return fail("变更超过 2000 个，先缩小工作副本范围")}}
 Ok(list)
}
pub fn parse_svn(raw:&str)->Result<Vec<Change>>{
 let doc=roxmltree::Document::parse(raw).map_err(|e|Error(e.to_string()))?;let mut list=vec![];
 for e in doc.descendants().filter(|n|n.has_tag_name("entry")){if let Some(w)=e.children().find(|n|n.has_tag_name("wc-status")){let item=w.attribute("item").unwrap_or("");let props=w.attribute("props").unwrap_or("");if ["normal","none","ignored","external"].contains(&item)&&!["modified","conflicted"].contains(&props){continue};let path=e.attribute("path").unwrap_or("").to_string();let conflict=item=="conflicted"||props=="conflicted"||w.attribute("tree-conflicted")==Some("true");list.push(Change{path,status:if props=="modified"&&item=="normal"{"properties".into()}else{item.into()},staged:false,worktree:true,conflict,original:None});if list.len()>2000{return fail("变更超过 2000 个")}}}Ok(list)
}
pub fn redact(s:&str)->String {
 let mut out=s.to_string();let mut start=0;
 while let Some(i)=out[start..].find("://"){let a=start+i+3;let end=out[a..].find(|c:char|c=='/'||c.is_whitespace()).map(|v|v+a).unwrap_or(out.len());if let Some(at)=out[a..end].rfind('@'){out.replace_range(a..a+at,"[凭据已隐藏]");start=a+"[凭据已隐藏]".len()+1;}else{start=end;}if start>=out.len(){break}}
 out
}
#[derive(Clone,Serialize)]pub struct Plan {
 pub token:String,pub project:String,pub repo:String,pub operation:String,pub paths:Vec<String>,pub message:String,pub destination:String,pub branch:String,
 #[serde(skip)]pub fingerprint:String,#[serde(skip)]pub created:Option<Instant>,
}
#[derive(Default)]pub struct Plans{pub items:HashMap<String,Plan>}
impl Plans{
 pub async fn prepare(&mut self,client:&Client,project:&str,operation:&str,mut paths:Vec<String>,message:&str)->Result<Plan>{
  self.items.retain(|_,p|p.created.map(|t|t.elapsed()<Duration::from_secs(90)).unwrap_or(false));if self.items.len()>=16{return fail("待确认操作过多")}
  if !["stage","unstage","commit","pull","push","update","add"].contains(&operation){return fail("未支持此操作")}
  let s=client.status().await?;if s.files.iter().any(|f|f.conflict){return fail("工作副本存在冲突，请先处理冲突")}
  if client.kind=="svn"&&["stage","unstage","push","pull"].contains(&operation){return fail("SVN 没有 Git 暂存/推送语义，请使用添加、提交、更新")}
  if client.kind=="git"&&["add","update"].contains(&operation){return fail("Git 请使用暂存或拉取")}
  if ["pull","update"].contains(&operation)&&!s.files.is_empty(){return fail("为保护未提交修改，请先提交或自行保存改动后再更新；不会自动丢弃文件")}
  if operation=="commit"{text(message.trim(),16000)?;if client.kind=="git"{paths=s.files.iter().filter(|f|f.staged).map(|f|f.path.clone()).collect();}}
  if ["stage","unstage","commit","add"].contains(&operation)&&paths.is_empty(){return fail("没有选择文件 / 暂存区为空")}
  if paths.len()>200{return fail("单次最多处理 200 个文件")}
  let mut seen=HashSet::new();paths.retain(|p|seen.insert(p.clone()));
  for p in &paths{if client.kind=="svn"&&p.contains('@'){return fail("本版暂不处理包含 @ 的 SVN 文件路径")};let target=vcs_path(&client.repo.path,p)?;if !s.files.iter().any(|f|f.path==*p){return fail("文件状态已改变，请刷新")};if target.is_dir(){return fail("请逐个选择文件，本版不递归提交整个目录")}}
  if ["push","pull"].contains(&operation){if s.remote.is_empty(){return fail("当前仓库未配置 origin")};if s.branch=="(detached HEAD)"{return fail("游离 HEAD 不能使用此操作")};}
  let fingerprint=fingerprint(client,&s,&paths).await?;
  let destination=if client.kind=="git"&&operation=="commit"{"仅提交到本地仓库，不推送".into()}else if ["stage","unstage","add"].contains(&operation){"本地工作副本".into()}else{format!("{} · {}",if client.kind=="git"{"origin"}else{"SVN 服务器"},if operation=="push"{&s.push_remote}else{&s.remote})};
  let plan=Plan{token:id(),project:project.into(),repo:client.repo.id.clone(),operation:operation.into(),paths,message:message.into(),destination,branch:s.branch,fingerprint,created:Some(Instant::now())};self.items.insert(plan.token.clone(),plan.clone());Ok(plan)
 }
 pub async fn execute(&mut self,client:&Client,token:&str)->Result<String>{
  let p=self.items.remove(token).ok_or_else(||Error("确认已过期或已使用，请重新检查操作".into()))?;
  if p.repo!=client.repo.id||p.created.unwrap().elapsed()>Duration::from_secs(90){return fail("确认已过期或仓库不匹配")}
  let s=client.status().await?;if fingerprint(client,&s,&p.paths).await?!=p.fingerprint{return fail("确认后代码或版本库已变化，未执行，请刷新并重新确认")}
  let mut args:Vec<String>=vec![];let mut message_file:Option<tempfile::NamedTempFile>=None;
  match(client.kind.as_str(),p.operation.as_str()){
   ("git","stage")=>{args.extend(["add","--"].map(String::from));args.extend(p.paths.clone());}
   ("git","unstage")=>{args.extend(["restore","--staged","--"].map(String::from));args.extend(p.paths.clone());}
   ("git","commit")|("svn","commit")=>{let mut f=tempfile::NamedTempFile::new()?;f.write_all(p.message.as_bytes())?;f.flush()?;args.extend(["commit".into(),"-F".into(),f.path().to_string_lossy().into()]);if client.kind=="svn"{args.extend(["--depth".into(),"empty".into(),"--".into()]);args.extend(p.paths.clone());}message_file=Some(f);}
   ("git","pull")=>args.extend(["pull","--ff-only","--no-rebase","origin",&p.branch].map(String::from)),
   ("git","push")=>args.extend(["push".into(),"--porcelain".into(),"origin".into(),format!("HEAD:refs/heads/{}",p.branch)]),
   ("svn","update")=>args.extend(["update","--ignore-externals","--accept","postpone"].map(String::from)),
   ("svn","add")=>{args.extend(["add","--parents","--depth","empty","--"].map(String::from));args.extend(p.paths.clone());}
   _=>return fail("未支持的操作"),
  }
  let output=client.run_vec(args).await?;drop(message_file);process::checked(output).map(|s|redact(&s))
 }
}
async fn fingerprint(c:&Client,s:&Status,paths:&[String])->Result<String>{
 let mut h=Sha256::new();h.update(s.snapshot.as_bytes());h.update(c.executable.as_bytes());h.update(c.svn_config.as_deref().unwrap_or("").as_bytes());let mut total=0u64;let mut actual=0u64;
 for p in paths{h.update(p.as_bytes());let path=vcs_path(&c.repo.path,p)?;if path.is_file(){let n=path.metadata()?.len();total+=n;if total>16*1024*1024{return fail("待确认文件合计超过 16 MiB，本版不生成完整性确认")};let mut f=std::fs::File::open(path)?;let mut b=[0u8;8192];let mut read=0u64;loop{let n=f.read(&mut b)?;if n==0{break}read+=n as u64;actual+=n as u64;if read>16*1024*1024||actual>16*1024*1024{return fail("文件在读取时增长过大")}h.update(&b[..n]);}}else{h.update(b"<deleted-or-directory>");}}
 Ok(format!("{:x}",h.finalize()))
}
#[cfg(test)]mod tests{
 use super::*;
 #[test]fn git_spaces_and_rename(){let r=parse_git(" M a b.txt\0R  new.txt\0old.txt\0?? -file\0").unwrap();assert_eq!(r[0].path,"a b.txt");assert_eq!(r[1].original.as_deref(),Some("old.txt"));assert_eq!(r[2].path,"-file");}
 #[test]fn svn_props_conflict(){let r=parse_svn(r#"<status><target><entry path="a.txt"><wc-status item="normal" props="modified"/></entry><entry path="b"><wc-status item="normal" props="conflicted"/></entry></target></status>"#).unwrap();assert_eq!(r.len(),2);assert!(r[1].conflict);}
 #[test]fn stable_xml(){assert_eq!(canonical_xml(r#"<a x="1" y="2"><b>value</b></a>"#).unwrap(),canonical_xml(r#"<a y="2" x="1"> <b>value</b> </a>"#).unwrap());assert_ne!(canonical_xml(r#"<a revision="1"/>"#).unwrap(),canonical_xml(r#"<a revision="2"/>"#).unwrap());}
 #[test]fn hides_userinfo(){assert_eq!(redact("https://name:secret@example.com/repo"),"https://[凭据已隐藏]@example.com/repo");}
}
