import { metadataPath } from './selection.js'
import { useWorkbenchV04 } from './live-v04.js'
import environmentPanel from './environment-panel.html?raw'
import configurationDialogs from './configuration-dialogs.html?raw'
import changeGroups from './change-groups.html?raw'
import './workbench-v04.css'
import './hotfix.css'
import { ValueRows } from './visual-controls.js'
import liveTemplate from './live-layout.html?raw'
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'

// Native-only UI adapter. This module never falls back to simulated results.
export function createLiveWorkbench(health) {
 return {
  components:{ ValueRows },
  setup() {
   const projects=ref([]), selectedProject=ref(''), runs=ref({}), logs=ref([]), tools=ref(null), settings=ref({}), page=ref('run')
   const connected=ref(false), busy=ref(0), error=ref(''), notice=ref(''), modal=ref(''), form=ref({}), plan=ref(null)
   const repoId=ref(''), repoStatus=ref(null), selectedFiles=ref([]), file=ref(''), diff=ref(''), staged=ref(false), diffMode=ref('unified'), message=ref('')
   const diffBusy=ref(false),diffError=ref('');let diffTimer=0,diffPending=null,diffInFlight=false
   const scope=ref('global'), toolForm=ref({git:'',svn:'',svn_config_dir:''}), filter=ref(''), paused=ref(false), freezeLogs=ref([])
   let ws, reconnectTimer, frame, flushQueue=[], attempts=0, mounted=true, repoEpoch=0, diffEpoch=0
   let token=new URLSearchParams(location.hash.slice(1)).get('token')||''
   try { if(token)sessionStorage.setItem('no-ide.native.token',token);else token=sessionStorage.getItem('no-ide.native.token')||'' }catch{}
   if(location.hash.includes('token='))history.replaceState(null,'',location.pathname+location.search)
   const project=computed(()=>projects.value.find(p=>p.id===selectedProject.value)||null)
   const repo=computed(()=>project.value?.repos.find(r=>r.id===repoId.value)||null)
   const liveCount=computed(()=>project.value?.instances.filter(i=>['running','starting','building'].includes(runs.value[i.id]?.state)).length||0)
   const visibleLogs=computed(()=>{
    if(!project.value)return []
    const ids=new Set([...project.value.instances.map(i=>i.id),...project.value.configs.map(c=>c.id)])
    return (paused.value?freezeLogs.value:logs.value).filter(l=>ids.has(l.instance)&&l.text.toLowerCase().includes(filter.value.toLowerCase())).slice(-120)
   })
   const diffRows=computed(()=>diff.value.split('\n').slice(0,1500).map(text=>({text,kind:text.startsWith('+')&&!text.startsWith('+++')?'add':text.startsWith('-')&&!text.startsWith('---')?'del':text.startsWith('@')?'hunk':'context'})))
   const stateText=i=>({starting:'启动中',building:'构建中 · 旧进程保留',running:'运行中',stopping:'正在停止',stopped:'已停止',exited:'已结束',error:'有问题'}[runs.value[i.id]?.state]||'未启动')
   const label=id=>project.value?.instances.find(i=>i.id===id)?.name||project.value?.configs.find(c=>c.id===id)?.name||'运行器'
   async function api(action,params={}) {
    const r=await fetch('/api/call',{method:'POST',headers:{'Content-Type':'application/json',Authorization:'Bearer '+token},body:JSON.stringify({action,params})})
    const text=await r.text();let data;try{data=JSON.parse(text)}catch{data={error:text||'执行器没有返回有效响应'}}
    if(!r.ok){if(r.status===401){connected.value=false;throw Error('本地会话已失效，请使用执行器新打开的浏览器地址。')}throw Error(data.error||`请求失败 (${r.status})`)}return data
   }
   async function act(fn) {busy.value++;error.value='';try{return await fn()}catch(e){error.value=e.message||String(e)}finally{busy.value--}}
   async function refresh(){const d=await api('state');projects.value=d.store.projects;settings.value=d.store.tools;v04.setStore(d.store);runs.value=Object.fromEntries(d.runs.map(r=>[r.instance,r]));if(!projects.value.some(p=>p.id===selectedProject.value))selectedProject.value=projects.value[0]?.id||'';connected.value=true}
   function connect(){
    if(!mounted||!token)return;ws=new WebSocket(location.origin.replace(/^http/,'ws')+'/api/events')
    ws.onopen=()=>{ws.send(token);attempts=0;connected.value=true}
    ws.onmessage=e=>{let m;try{m=JSON.parse(e.data)}catch{return}
     if(m.type==='snapshot'){runs.value=Object.fromEntries(m.states.map(s=>[s.instance,s]));logs.value=m.logs.slice(-1000)}
     if(m.type==='state')runs.value={...runs.value,[m.data.instance]:m.data}
     if(m.type==='log'){flushQueue.push(m.data);if(flushQueue.length>256)flushQueue.splice(0,flushQueue.length-256);if(!frame)frame=requestAnimationFrame(()=>{logs.value=[...logs.value,...flushQueue].slice(-1000);flushQueue=[];frame=0})}
    }
    ws.onclose=()=>{connected.value=false;if(mounted&&attempts++<5)reconnectTimer=setTimeout(connect,Math.min(1000*2**attempts,10000))}
   }
   const pick=async kind=>(await api('fs.pick',{kind})).path
   async function chooseProjectFolder(){await act(async()=>{const p=await pick('folder');if(p){form.value.root=p;if(!form.value.name)form.value.name=p.replace(/[\\/]$/,'').split(/[\\/]/).pop()}})}
   async function chooseField(field,kind='file'){await act(async()=>{const p=await pick(kind);if(p)form.value[field]=p})}
   function openAdd(){form.value={name:'',root:'',trusted:false};modal.value='project'}
   function clearRepo(){repoEpoch++;diffEpoch++;clearTimeout(diffTimer);diffPending=null;diffBusy.value=false;diffError.value='';repoStatus.value=null;selectedFiles.value=[];file.value='';diff.value='';plan.value=null;modal.value=''}
   watch(selectedProject,()=>{clearRepo();repoId.value=project.value?.repos[0]?.id||'';if(page.value==='code'&&repoId.value)void act(loadRepo);if(page.value==='tools'){editTools();void act(detectTools)}})
   async function saveProject(){await act(async()=>{if(!form.value.trusted)throw Error('请先确认此项目受信任。');const p=await api('project.add',{name:form.value.name,root:form.value.root,confirmed:true});await refresh();selectedProject.value=p.id;modal.value='';notice.value='项目已添加，正在查找可运行入口；不会自动执行代码。';await nextTick();v04.configForm()})}
   function configForm(c){form.value=c?{id:c.id,name:c.name,cwd:c.cwd,program:c.command.program,args:c.command.args.join('\n'),buildProgram:c.build?.program||'',buildArgs:(c.build?.args||[]).join('\n'),watch:c.watch.join('\n'),env:Object.entries(c.env).map(([k,v])=>`${k}=${v}`).join('\n')}:{id:'',name:'',cwd:'.',program:'',args:'',buildProgram:'',buildArgs:'',watch:'',env:''};modal.value='config'}
   function useTemplate(type){const win=health.platform==='windows';const t={java:{name:'Java 服务',program:'java',args:'-jar\ntarget/app.jar\n--server.port={port}'},vite:{name:'Vite 前端',program:win?'npm.cmd':'npm',args:'run\ndev\n--\n--host\n127.0.0.1\n--port\n{port}'},node:{name:'Node 服务',program:'node',args:'src/index.js'},python:{name:'Python 服务',program:win?'python':'python3',args:'-u\napp.py'},spring:{name:'Spring Boot',program:win?'mvnw.cmd':'./mvnw',args:'spring-boot:run\n-Dspring-boot.run.arguments=--server.port={port}'},android:{name:'Android 构建',program:win?'gradlew.bat':'./gradlew',args:'assembleDebug'}}[type];Object.assign(form.value,t);notice.value='模板只填入命令；请按实际工程修改入口。没有执行或安装工具。'}
   const lines=s=>s.split('\n').map(v=>v.trim()).filter(Boolean)
   function envParse(s){const out={};for(const line of lines(s)){const i=line.indexOf('=');if(i<=0)throw Error('环境变量每行写成 KEY=value');out[line.slice(0,i)]=line.slice(i+1)}return out}
   async function saveConfig(){await act(async()=>{const f=form.value;await api('config.save',{project:project.value.id,config:{id:f.id,name:f.name,cwd:f.cwd,command:{program:f.program,args:lines(f.args)},build:f.buildProgram?{program:f.buildProgram,args:lines(f.buildArgs)}:null,watch:lines(f.watch),env:envParse(f.env)}});await refresh();modal.value='';notice.value='运行配置已保存。下一步添加一个或多个实例。'})}
   function instanceForm(i){if(!project.value?.configs.length){configForm();return}form.value=i?{...i,args:i.args.join('\n'),env:Object.entries(i.env).map(([k,v])=>`${k}=${v}`).join('\n')}:{id:'',name:'实例 '+String(project.value.instances.length+1).padStart(2,'0'),config_id:project.value.configs[0].id,port:null,args:'',env:''};modal.value='instance'}
   function cloneInstance(i){instanceForm({...i,id:'',name:i.name+' 副本',port:i.port?i.port+1:null})}
   async function saveInstance(){await act(async()=>{const f=form.value;await api('instance.save',{project:project.value.id,instance:{id:f.id,name:f.name,config_id:f.config_id,port:f.port?Number(f.port):null,args:lines(f.args),env:envParse(f.env)}});await refresh();modal.value='';notice.value='实例已保存。端口会实际替换命令中的 {port}，并设置 PORT 环境变量。'})}
   async function run(i,op){await act(async()=>{await api('run.'+op,{project:project.value.id,instance:i.id});await refresh()})}
   async function runAll(op){await act(async()=>{const p=project.value;for(const i of p.instances){const active=['running','starting','building','stopping'].includes(runs.value[i.id]?.state);if((op==='start'&&!active)||(op==='stop'&&active))await api('run.'+op,{project:p.id,instance:i.id})}await refresh()})}
   function editTools(){const src=scope.value==='global'?settings.value:project.value?.tools||{};toolForm.value={git:src.git||'',svn:src.svn||'',svn_config_dir:src.svn_config_dir||''}}
   watch(scope,()=>{editTools();void act(detectTools)})
   async function detectTools(){tools.value=await api('tools.detect',scope.value==='project'?{project:project.value?.id}:{})}
   async function pickTool(k){await act(async()=>{const path=await pick(k==='svn_config_dir'?'folder':'file');if(path)toolForm.value[k]=path})}
   async function saveTools(){await act(async()=>{await api('tools.save',{settings:toolForm.value,...(scope.value==='project'?{project:project.value.id}:{})});await refresh();await detectTools();notice.value='客户端配置已验证并保存。空路径使用自动选择或继承全局配置。'})}
   async function go(p){page.value=p;error.value='';if(p==='tools'){editTools();await act(detectTools)}if(p==='code'){repoId.value=project.value?.repos.some(r=>r.id===repoId.value)?repoId.value:project.value?.repos[0]?.id||'';await act(loadRepo)}}
   async function loadRepo(){if(!project.value||!repoId.value){clearRepo();return}const epoch=++repoEpoch,projectId=project.value.id,rid=repoId.value;const d=await api('vcs.status',{project:projectId,repo:rid});if(epoch!==repoEpoch||selectedProject.value!==projectId||repoId.value!==rid)return;repoStatus.value=d;selectedFiles.value=selectedFiles.value.filter(p=>d.files.some(f=>f.path===p));if(!d.files.some(f=>f.path===file.value)){file.value='';diff.value=''}}
   function selectFile(f){file.value=f.path;loadDiff()}
   function loadDiff(){
    diffEpoch++;diff.value='';diffError.value='';clearTimeout(diffTimer)
    if(metadataPath(file.value)){diffPending=null;diffBusy.value=false;diff.value='这是版本库管理数据，可以勾选并移动到任意本地分组。为避免误读或误提交，不加载其中内容；移动分组不会修改 .gitignore 或 svn:ignore。';return}
    if(!file.value||!repo.value){diffPending=null;diffBusy.value=false;return}
    diffPending={project:project.value.id,repo:repoId.value,path:file.value,staged:staged.value,epoch:diffEpoch};diffBusy.value=true
    diffTimer=setTimeout(drainDiff,140)
   }
   async function drainDiff(){
    if(diffInFlight||!diffPending||!mounted)return
    const request=diffPending;diffPending=null;diffInFlight=true
    try{const d=await api('vcs.diff',request);if(request.epoch===diffEpoch&&request.project===selectedProject.value&&request.repo===repoId.value)diff.value=d.diff}
    catch(e){if(request.epoch===diffEpoch)diffError.value=e.message||String(e)}
    finally{diffInFlight=false;if(diffPending)diffTimer=setTimeout(drainDiff,80);else diffBusy.value=false}
   }
   watch(staged,()=>void loadDiff())
   watch(file,v=>{if(!v){diffEpoch++;diffPending=null;clearTimeout(diffTimer);diffBusy.value=false;diff.value=''}})
   async function addRepo(){await act(async()=>{const dir=await pick('folder');if(!dir)return;const base=project.value.root.replace(/\\/g,'/').replace(/\/$/,'');const chosen=dir.replace(/\\/g,'/');const test=health.platform==='windows'?chosen.toLowerCase():chosen;const baseTest=health.platform==='windows'?base.toLowerCase():base;if(test!==baseTest&&!test.startsWith(baseTest+'/'))throw Error('仓库必须位于当前项目目录内；其他目录可创建独立项目。');const path=chosen.slice(base.length).replace(/^\//,'')||'.';const r=await api('repo.add',{project:project.value.id,path});await refresh();repoId.value=r.id;await loadRepo()})}
   const opName=o=>({stage:'暂存选中文件（不提交）',unstage:'取消暂存（不提交）',commit:repo.value?.kind==='svn'?'提交到 SVN 服务器':'提交到本地 Git 仓库',pull:'拉取 origin（仅快进）',push:'推送到 origin',update:'更新 SVN 工作副本',add:'纳入 SVN 版本控制（不提交）'}[o]||o)
   async function prepare(operation){await act(async()=>{plan.value=await api('vcs.prepare',{project:project.value.id,repo:repoId.value,operation,paths:selectedFiles.value,message:message.value});modal.value='confirm'})}
   async function execute(){await act(async()=>{const p=plan.value;if(!p)return;const r=await api('vcs.execute',{project:p.project,repo:p.repo,token:p.token,confirmed:true});modal.value='';plan.value=null;notice.value=r.output||'操作完成，请检查最新状态。';message.value='';selectedFiles.value=[];await loadRepo()})}
   function pause(){paused.value=!paused.value;if(paused.value)freezeLogs.value=logs.value.slice()}
   async function copyLogs(){await act(async()=>{await navigator.clipboard.writeText(visibleLogs.value.map(l=>`${new Date(l.time).toLocaleTimeString()} [${label(l.instance)}] ${l.text}`).join('\n'));notice.value='已复制当前可见日志；分享前请检查是否含敏感信息。'})}
   const v04=useWorkbenchV04({api,act,refresh,project,projects,repo,repoId,repoStatus,selectedFiles,file,diff,modal,form,page,notice,message,plan,loadRepo,selectFile,oldConfigForm:configForm,oldInstanceForm:instanceForm})
   onMounted(()=>{void act(async()=>{if(!token)throw Error('请从本地执行器自动打开的地址进入，以建立受保护的会话。');await refresh();connect();await detectTools()})})
   onUnmounted(()=>{mounted=false;clearTimeout(diffTimer);ws?.close();clearTimeout(reconnectTimer);if(frame)cancelAnimationFrame(frame)})
   return {diffBusy,diffError,health,projects,selectedProject,project,runs,logs,tools,settings,page,connected,busy,error,notice,modal,form,plan,repoId,repo,repoStatus,selectedFiles,file,diff,staged,diffMode,message,scope,toolForm,filter,paused,visibleLogs,diffRows,liveCount,stateText,label,act,refresh,go,openAdd,chooseProjectFolder,chooseField,saveProject,configForm,useTemplate,saveConfig,instanceForm,cloneInstance,saveInstance,run,runAll,editTools,detectTools,pickTool,saveTools,loadRepo,selectFile,addRepo,opName,prepare,execute,pause,copyLogs,...v04}
  },
  template: liveTemplate.replace('<!-- runtime-environments -->',environmentPanel).replace('<!-- configuration-dialogs -->',configurationDialogs).replace('<!-- change-groups -->',changeGroups)
 }
}
