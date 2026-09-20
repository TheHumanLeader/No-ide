import { AppIcon, INITIAL } from './catalog.js'
import appTemplate from './layout.html?raw'
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { RUNTIMES, newId, validPort, nextPort, makeInstance, DirectoryPicker } from './project-model.js'
import { SourceControl, sampleRepositories } from './source-control.js'

// This module contains a PREVIEW adapter only. It never spawns a process,
// reads a local project, detects a toolchain, or sends a request to an app.
const STORAGE = 'no-ide.ui.v1'
const MAX_LOGS = 500
const MAX_LOG_BYTES = 96 * 1024
const now = () => new Date().toLocaleTimeString('zh-CN', { hour12:false })
const wait = (ms) => new Promise(resolve => setTimeout(resolve, ms))
const safeRead = () => { try { const v=JSON.parse(localStorage.getItem(STORAGE)||'{}'); return v && typeof v==='object' ? v : {} } catch { return {} } }

export function createNoIdeApp() {
 return {
  components: { AppIcon, DirectoryPicker, SourceControl },
  setup() {
    const saved = safeRead()
    const projects = ref([
      {id:'commerce',name:'示例商城',folder:{name:'commerce',origin:'sample'},sample:true,
        description:'多个 Java 服务、相同服务的多个实例、一个 Vite 前端。',
        configs:INITIAL.map(c=>({...c,projectId:'commerce'})),repositories:sampleRepositories()},
      {id:'sandbox',name:'空白实验项目',folder:{name:'sandbox',origin:'sample'},sample:true,
        description:'一个空项目，按需添加语言和运行实例。',configs:[],repositories:[]}
    ])
    const activeProjectId=ref('commerce')
    const activeProject=computed(()=>projects.value.find(p=>p.id===activeProjectId.value)||projects.value[0])
    const allServices=ref(projects.value[0].configs.map((c,i)=>makeInstance('commerce',c,{
      id:c.id,slug:c.slug,name:c.name+' · 01',port:c.port,state:c.state,
      version:c.version,step:c.state==='running'?4:0,last:c.last,auto:c.auto
    })))
    allServices.value.splice(2,0,makeInstance('commerce',projects.value[0].configs.find(c=>c.id==='api'),{
      id:'api-02',slug:'core-api#02',name:'业务服务 · 02',port:8081
    }))
    const services=computed(()=>allServices.value.filter(s=>s.projectId===activeProjectId.value))
    const projectDraft=ref({name:'',folder:null,source:'local',vcs:'auto',remote:''})
    const instanceForm=ref({configId:'',name:'',count:1,port:8080,type:'Java',command:'',folder:null,args:'',environment:''})
    const groupedServices=computed(()=>activeProject.value.configs.map(c=>({config:c,instances:visibleServices.value.filter(i=>i.configId===c.id)})).filter(g=>g.instances.length))
    const projectCount=p=>allServices.value.filter(s=>s.projectId===p.id).length
    const projectRunning=p=>allServices.value.filter(s=>s.projectId===p.id&&s.state==='running').length
    const currentConfig=computed(()=>selected.value?activeProject.value.configs.find(c=>c.id===selected.value.configId):null)
    const sameConfigCount=computed(()=>selected.value?services.value.filter(s=>s.configId===selected.value.configId).length:0)
    const settings = ref({ theme:saved.theme==='space'?'space':'pink', compact:!!saved.compact, motion:saved.motion!==false, auto:saved.auto!==false, demoDevice:false })
    const page=ref('run'), selectedId=ref('api'), filter=ref('all'), serviceSearch=ref(''), detailTab=ref('info'), outputTab=ref('logs')
    const outputScope=ref('all'), logLevel=ref('all'), logSearch=ref(''), logPaused=ref(false), pausedSnapshot=ref([]), logElement=ref(null)
    const collapsed=ref(false), mobileOpen=ref(false), modal=ref(null), toast=ref(null), globalSearch=ref(''), copyText=ref('')
    const requestPath=ref('/api/health'), requestMethod=ref('GET'), response=ref(null), batchBusy=ref(false)
    const formError=ref(''), configDraft=ref(null)
    const epochs=new Map(), queued=new Map(), logBytes=new TextEncoder()
    let toastTimer=0, mounted=true, batchEpoch=0, focusBeforeModal=null
    const logs=ref([
      {id:1,projectId:'commerce',time:'09:40:52',service:'task-worker',level:'INFO',message:'[示例] Uvicorn 启动完成，等待任务。'},
      {id:2,projectId:'commerce',time:'09:41:02',service:'core-api',level:'INFO',message:'[示例] 检测到 UserController.java 变化，合并本次修改。'},
      {id:3,projectId:'commerce',time:'09:41:03',service:'core-api',level:'BUILD',message:'[示例] 编译完成；开始应用重启。'},
      {id:4,projectId:'commerce',time:'09:41:06',service:'core-api',level:'READY',message:'[示例] 就绪检查通过 → http://localhost:8080'},
      {id:5,projectId:'commerce',time:'09:41:08',service:'web-console',level:'HMR',message:'[示例] 模块已替换 /src/pages/Dashboard.vue'},
      {id:6,projectId:'commerce',time:'09:41:08',service:'no-ide',level:'INFO',message:'交互预览已就绪。尚未连接执行器，没有启动任何本机进程。'}
    ])
    const history=ref([{id:1,projectId:'commerce',time:'09:41:08',service:'web-console',title:'模块热替换',result:'成功',detail:'Dashboard.vue · 示例记录'},{id:2,projectId:'commerce',time:'09:41:06',service:'core-api',title:'应用重启',result:'成功',detail:'UserController.java · 示例记录'}])
    let logId=6, historyId=2
    const nav=[{id:'run',icon:'grid',label:'运行台'},{id:'projects',icon:'folder',label:'项目管理'},{id:'vcs',icon:'branch',label:'代码管理'},{id:'history',icon:'clock',label:'运行记录'},{id:'env',icon:'chip',label:'环境与设备'},{id:'settings',icon:'settings',label:'设置'}]
    const titles={run:'运行台',vcs:'代码管理',projects:'项目管理',history:'运行记录',env:'环境与设备',settings:'设置'}
    const selected=computed(()=>services.value.find(s=>s.id===selectedId.value)||services.value[0]||null)
    const running=computed(()=>services.value.filter(s=>s.state==='running').length)
    const issues=computed(()=>services.value.filter(s=>s.error))
    const updating=computed(()=>services.value.filter(s=>s.busy).length)
    const visibleServices=computed(()=>services.value.filter(s=>(filter.value==='all'||(filter.value==='running'&&s.state==='running')||(filter.value==='issues'&&s.error))&&`${s.name} ${s.slug} ${s.type}`.toLowerCase().includes(serviceSearch.value.toLowerCase())))
    const searchResults=computed(()=>services.value.filter(s=>`${s.name} ${s.slug} ${s.type}`.toLowerCase().includes(globalSearch.value.toLowerCase())))
    const filteredLogs=computed(()=>(logPaused.value?pausedSnapshot.value:logs.value).filter(l=>l.projectId===activeProjectId.value&&(outputScope.value==='all'||l.service===selected.value?.slug)&&(logLevel.value==='all'||l.level==='ERROR')&&`${l.service} ${l.message}`.toLowerCase().includes(logSearch.value.toLowerCase())))
    const shownLogs=computed(()=>filteredLogs.value.slice(-120))
    const selectedHistory=computed(()=>history.value.filter(h=>h.service===selected.value?.slug))
    const projectHistory=computed(()=>history.value.filter(h=>h.projectId===activeProjectId.value))
    const stateLabel=s=>s.busy?(s.step===0?'发现改动':s.step===1?'构建中':s.step===2?'更新中':'等待就绪'):s.state==='running'?'运行中':s.type==='Android'&&!settings.value.demoDevice?'等待设备':'已停止'
    const stateClass=s=>s.busy?'working':s.state==='running'?'running':'stopped'
    const notify=(message,tone='info')=>{clearTimeout(toastTimer);toast.value={message,tone};toastTimer=setTimeout(()=>toast.value=null,3500)}
    function addLog(s,level,message){
      logs.value.push({id:++logId,projectId:s?.projectId||activeProjectId.value,time:now(),service:s?.slug||'no-ide',level,message:message.slice(0,2048)})
      if(logs.value.length>MAX_LOGS)logs.value.splice(0,logs.value.length-MAX_LOGS)
      let size=logs.value.reduce((n,l)=>n+logBytes.encode(JSON.stringify(l)).length,0)
      while(size>MAX_LOG_BYTES&&logs.value.length){size-=logBytes.encode(JSON.stringify(logs.value[0])).length;logs.value.shift()}
      nextTick(()=>{if(!logPaused.value&&logElement.value)logElement.value.scrollTop=logElement.value.scrollHeight})
    }
    const addHistory=(s,title,result,detail)=>{history.value.unshift({id:++historyId,projectId:s.projectId,time:now(),service:s.slug,title,result,detail});if(history.value.length>80)history.value.length=80}
    function pick(s){selectedId.value=s.id;detailTab.value='info';response.value=null;configDraft.value=null}
    function go(id){page.value=id;mobileOpen.value=false}
    function openModal(name){if(name==='add')projectDraft.value={name:'',folder:null,source:'local',vcs:'auto',remote:''};modal.value=name;formError.value=''}
    function openService(s){pick(s);go('run');modal.value=null}
    function nextEpoch(s){const id=(epochs.get(s.id)||0)+1;epochs.set(s.id,id);return id}
    function current(s,id){return mounted&&epochs.get(s.id)===id}
    async function updateService(s,{fail=false,start=false,manual=false}={}){
      if(s.busy){queued.set(s.id,{fail});s.pending=true;notify('连续改动已合并，当前流程结束后再更新。');return}
      if(s.type==='Android'&&!settings.value.demoDevice){openModal('device');return}
      if(!start&&s.state!=='running'){notify('先运行服务，再体验代码更新。');return}
      if(!start&&!manual&&(!settings.value.auto||!s.auto)){s.pending=true;queued.set(s.id,{fail});addLog(s,'INFO','[示例] 发现改动；自动更新已关闭，等待手动应用。');notify('改动已记录，点击“应用待处理改动”。');return}
      const token=nextEpoch(s); const wasRunning=s.state==='running';s.busy=true;s.step=0;s.pending=false;queued.delete(s.id)
      addLog(s,'INFO',start?'[示例] 创建运行任务。':'[示例] 检测到源码变化，合并本次修改。')
      for(let step=1;step<=3;step++){
        await wait(settings.value.motion?600:100);if(!current(s,token))return;s.step=step
        if(step===1)addLog(s,'BUILD','[示例] 正在构建受影响的模块…')
        if(step===2&&fail){
          s.busy=false;s.step=1;s.error={file:s.type==='Python'?'app/main.py:24':'src/main/java/UserController.java:42',message:'编译失败：找不到符号 userName',time:now()};
          addLog(s,'ERROR',`[示例] ${s.error.message}。${wasRunning?'未发布失败产物，旧版本继续运行。':'服务未启动。'}`)
          addHistory(s,'更新失败','失败',wasRunning?'旧版本继续运行 · 示例':'未启动 · 示例');if(activeProjectId.value===s.projectId)outputTab.value='issues';notify('模拟构建失败。旧版本没有被停止。','error');
          const pending=queued.get(s.id);if(pending){queued.delete(s.id);s.pending=false;void updateService(s,{...pending,manual:true})}return
        }
        if(step===2)addLog(s,'INFO',`[示例] 构建成功，执行${s.mode}。`)
        if(step===3)addLog(s,'INFO','[示例] 等待就绪检查…')
      }
      await wait(settings.value.motion?450:100);if(!current(s,token))return
      s.busy=false;s.step=4;s.state='running';s.version++;s.error=null;s.last=now()
      addLog(s,'READY',`[示例] ${start?'启动完成':s.mode+'完成'}，版本 v${s.version} 就绪。`)
      addHistory(s,start?'启动服务':s.mode,'成功',`v${s.version} · 示例流程，非实际构建`)
      notify(`${s.name}：${start?'已启动':s.mode+'完成'}（模拟）。`,'success')
      const pending=queued.get(s.id);if(pending){queued.delete(s.id);s.pending=false;void updateService(s,{...pending,manual:true})}
    }
    function stop(s){nextEpoch(s);queued.delete(s.id);s.busy=false;s.pending=false;s.state='stopped';s.step=0;s.error=null;addLog(s,'INFO','[示例] 已取消排队任务并停止服务。');addHistory(s,'停止服务','已停止','示例状态，无本机进程');notify(`${s.name}已停止（模拟）。`)}
    async function runAll(){if(batchBusy.value)return;const epoch=++batchEpoch;batchBusy.value=true;for(const s of [...services.value]){if(epoch!==batchEpoch||!mounted)break;if(s.state!=='running'&&!s.busy){if(s.type==='Android'&&!settings.value.demoDevice){addLog(s,'INFO','[示例] 跳过 Android：尚未选择示例设备。');continue}await updateService(s,{start:true})}}if(epoch===batchEpoch)batchBusy.value=false}
    function stopAll(){batchEpoch++;batchBusy.value=false;services.value.forEach(s=>{if(s.busy||s.state==='running')stop(s)});notify('本项目实例已全部停止（模拟），其他项目不受影响。')}
    function applyPending(s){const opts=queued.get(s.id)||{};queued.delete(s.id);void updateService(s,{...opts,manual:true})}
    function change(s,fail=false){
      // One changed configuration can affect several running instances.
      // Actual shared-build scheduling belongs to the future executor.
      services.value.filter(i=>i.configId===s.configId&&i.state==='running').forEach(i=>void updateService(i,{fail}))
    }
    function switchProject(id, target='run'){
      if(!projects.value.some(p=>p.id===id))return
      // Stop only a batch's future scheduled launches, not already running instances.
      batchEpoch++;batchBusy.value=false
      activeProjectId.value=id;selectedId.value=services.value[0]?.id||''
      filter.value='all';serviceSearch.value='';detailTab.value='info';response.value=null;configDraft.value=null
      page.value=target;mobileOpen.value=false;modal.value=null
    }
    function addProject(){
      const d=projectDraft.value,name=d.name.trim()||d.folder?.name
      if(!d.folder||!name){formError.value='先选择项目目录；项目名可以自动取目录名。';return}
      if(projects.value.some(p=>p.name===name)){formError.value='此项目名已存在，请换一个名称。';return}
      if(d.source==='remote'&&!d.remote.trim()){formError.value='请填写仓库地址。';return}
      if(d.source==='remote'&&(!/^[^/\\<>:"|?*]+$/.test(name)||name==='.'||name==='..')){formError.value='获取项目的名称不能包含路径分隔符或 ..。';return}
      const type=d.vcs==='auto'?'待检测':d.vcs
      const project={id:newId('project'),name,folder:{...d.folder},sample:false,configs:[],
        description:d.source==='remote'?'已记录获取任务，等待执行器；未下载代码。':'已选择本地目录，等待执行器。',
        repositories:d.vcs==='auto'?[]:[{id:newId('repo'),name:name+' 代码库',type,root:d.folder.name,
          branch:'',remote:d.remote.trim(),sample:false,importRequested:d.source==='remote',changes:[],history:[]}]}
      projects.value.push(project);switchProject(project.id)
      notify(d.source==='remote'?'项目已创建。仓库获取尚未执行，没有 clone / checkout。':'项目已创建，下一步添加运行实例。目录内容没有被读取。','success')
    }
    function openInstance(source=null){
      const c=source?activeProject.value.configs.find(c=>c.id===source.configId):activeProject.value.configs[0]
      instanceForm.value={configId:c?.id||'new',name:c?c.name:'',count:1,port:c?.type==='Android'?null:nextPort(allServices.value,c?.port||8080),
        type:c?.type||'Java',command:c?.command||RUNTIMES.Java.command,folder:null,args:source?.args||'',environment:source?.environment||''}
      formError.value='';modal.value='instance'
    }
    function chooseConfig(){
      const f=instanceForm.value,c=activeProject.value.configs.find(c=>c.id===f.configId)
      if(c){f.name=c.name;f.type=c.type;f.port=c.type==='Android'?null:nextPort(allServices.value,c.port);f.command=c.command}
      else {f.name='';chooseRuntime()}
    }
    function chooseRuntime(){const f=instanceForm.value,r=RUNTIMES[f.type];f.command=r.command;f.port=r.port===null?null:nextPort(allServices.value,r.port)}
    function addInstances(){
      const f=instanceForm.value,n=Number(f.count),name=f.name.trim()
      if(!name){formError.value='请填写实例名称。';return}
      if(!Number.isInteger(n)||n<1||n>8){formError.value='每次创建 1～8 个实例。';return}
      let config=activeProject.value.configs.find(c=>c.id===f.configId)
      const type=config?.type||f.type
      if(type!=='Android'&&(!validPort(f.port)||Number(f.port)+n-1>65535)){formError.value='端口应为 1～65535，连续实例端口不能超出范围。';return}
      const ports=type==='Android'?Array(n).fill(null):Array.from({length:n},(_,i)=>Number(f.port)+i)
      if(ports.some(p=>p!==null&&allServices.value.some(s=>s.port===p))){formError.value='端口与已有实例冲突，请调整起始端口。';return}
      if(!config){
        if(!f.command.trim()){formError.value='请填写新运行配置的启动命令。';return}
        const runtime=RUNTIMES[type]
        const c={id:newId('config'),projectId:activeProjectId.value,name,type,...runtime,port:ports[0],
          command:f.command.trim(),slug:newId('run'),path:f.folder?.name||activeProject.value.folder.name,
          watch:'src/**',description:'用户添加的运行配置，尚未执行。'}
        activeProject.value.configs.push(c);config=activeProject.value.configs.at(-1)
      }
      const existing=services.value.filter(s=>s.configId===config.id).length
      const created=ports.map((port,i)=>makeInstance(activeProjectId.value,config,{
        name:name+' · '+String(existing+i+1).padStart(2,'0'),slug:config.slug+'#'+(existing+i+1),port,args:f.args,environment:f.environment
      }))
      allServices.value.push(...created);pick(created[0]);go('run');modal.value=null
      notify(`已添加 ${n} 个实例，共享“${config.name}”配置，各自独立启停（模拟）。`,'success')
    }
    function editConfig(){if(!selected.value)return;configDraft.value={...selected.value};detailTab.value='config'}
    function saveConfig(){
      const d=configDraft.value
      if(!d||!d.command.trim()||!d.path.trim()){notify('运行目录和启动命令不能为空。','error');return}
      if(d.type!=='Android'&&!validPort(d.port)){notify('请输入有效端口。','error');return}
      if(d.type!=='Android'&&allServices.value.some(s=>s.id!==d.id&&s.port===Number(d.port))){notify('此端口已被其他实例配置使用。','error');return}
      Object.assign(currentConfig.value,{path:d.path,command:d.command,watch:d.watch,mode:d.mode})
      Object.assign(selected.value,{port:d.type==='Android'?null:Number(d.port),auto:d.auto,args:d.args,environment:d.environment})
      detailTab.value='info';notify('公共运行配置已保存，实例端口与参数单独保留；没有执行命令。','success')
    }
    async function copy(value){
      try{if(!navigator.clipboard?.writeText)throw Error('clipboard');await navigator.clipboard.writeText(value);notify('已复制。','success')}
      catch{copyText.value=value;modal.value='copy'}
    }
    function errorContext(s){return `[No-ide 交互预览 / 非真实执行]\n服务：${s.name} (${s.slug})\n环境示例：${s.runtime}\n工作目录示例：${s.path}\n命令示例：${s.command}\n错误示例：${s.error?.message||'当前没有错误'}\n位置示例：${s.error?.file||'—'}\n状态：${s.state==='running'?'旧版本仍运行（模拟）':'未运行（模拟）'}`}
    function copyError(s){void copy(errorContext(s))}
    function sendRequest(){response.value={status:selected.value.state==='running'?200:503,body:JSON.stringify({preview:true,networkRequestSent:false,service:selected.value.slug,path:requestPath.value,method:requestMethod.value,status:selected.value.state==='running'?'UP':'STOPPED',version:selected.value.version},null,2)};notify('已生成示例响应；没有发送网络请求。')}
    function downloadLogs(){const text='No-ide 交互预览日志（非真实执行）\n'+filteredLogs.value.map(l=>`${l.time} ${l.level} [${l.service}] ${l.message}`).join('\n');const u=URL.createObjectURL(new Blob([text],{type:'text/plain;charset=utf-8'}));const a=document.createElement('a');a.href=u;a.download='no-ide-preview.log';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);notify('已导出当前筛选的示例日志。')}
    function togglePause(){logPaused.value=!logPaused.value;if(logPaused.value)pausedSnapshot.value=logs.value.slice()}
    function clearLogs(){logs.value=logs.value.filter(l=>l.projectId!==activeProjectId.value);pausedSnapshot.value=pausedSnapshot.value.filter(l=>l.projectId!==activeProjectId.value);notify('已清空本项目日志，其他项目保留。')}
    function toggleTheme(){settings.value.theme=settings.value.theme==='pink'?'space':'pink'}
    function keydown(e){
      if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){e.preventDefault();globalSearch.value='';openModal('search')}
      if(e.key==='Escape'){modal.value=null;mobileOpen.value=false}
      if(e.key==='Tab'&&modal.value){const nodes=[...document.querySelectorAll('.modal [data-focus], .modal button:not([disabled]), .modal input:not([disabled]), .modal select, .modal textarea')].filter(el=>el.getClientRects().length);if(!nodes.length)return;const first=nodes[0],last=nodes[nodes.length-1];if(e.shiftKey&&(document.activeElement===first||!nodes.includes(document.activeElement))){e.preventDefault();last.focus()}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus()}}
    }
    watch(modal,async(v,old)=>{if(v&&!old)focusBeforeModal=document.activeElement;await nextTick();if(v)document.querySelector('.modal [data-focus], .modal input, .modal button')?.focus();else focusBeforeModal?.focus?.()})
    watch(settings,v=>{try{localStorage.setItem(STORAGE,JSON.stringify({theme:v.theme,compact:v.compact,motion:v.motion,auto:v.auto}))}catch{}},{deep:true})
    watch(detailTab,v=>{if(v==='config'&&selected.value)configDraft.value={...selected.value}})
    onMounted(()=>{document.addEventListener('keydown',keydown)})
    onUnmounted(()=>{mounted=false;batchEpoch++;clearTimeout(toastTimer);document.removeEventListener('keydown',keydown)})
    return {projects,activeProjectId,activeProject,projectDraft,instanceForm,projectCount,projectRunning,currentConfig,sameConfigCount,switchProject,openInstance,chooseConfig,chooseRuntime,addInstances,RUNTIMES,services,settings,page,selectedId,selected,filter,serviceSearch,detailTab,outputTab,outputScope,logLevel,logSearch,logPaused,logElement,collapsed,mobileOpen,modal,toast,globalSearch,searchResults,copyText,requestPath,requestMethod,response,batchBusy,formError,configDraft,nav,titles,running,issues,updating,visibleServices,groupedServices,filteredLogs,shownLogs,history,projectHistory,selectedHistory,stateLabel,stateClass,notify,pick,go,openModal,openService,updateService,stop,runAll,stopAll,applyPending,change,addProject,editConfig,saveConfig,copy,copyError,sendRequest,downloadLogs,togglePause,clearLogs,toggleTheme}
  },
  template: appTemplate
 }
}
