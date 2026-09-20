import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'

// This module contains a PREVIEW adapter only. It never spawns a process,
// reads a local project, detects a toolchain, or sends a request to an app.
const STORAGE = 'no-ide.ui.v1'
const MAX_LOGS = 500
const MAX_LOG_BYTES = 96 * 1024
const ICONS = {
  grid: ['M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z'],
  folder: ['M3 7a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z'],
  clock: ['M12 8v4l3 2', 'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0'],
  chip: ['M8 8h8v8H8zM6 3v3M12 3v3M18 3v3M6 18v3M12 18v3M18 18v3M3 6h3M3 12h3M3 18h3M18 6h3M18 12h3M18 18h3', 'M6 6h12v12H6z'],
  settings: ['M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8', 'M9 3h6l1 3 3 1 2 5-2 5-3 1-1 3H9l-1-3-3-1-2-5 2-5 3-1z'],
  play: ['M8 5l11 7-11 7z'], stop: ['M6 6h12v12H6z'],
  refresh: ['M20 7v5h-5M4 17v-5h5', 'M6.1 6a8 8 0 0 1 13.4 3M4.5 15A8 8 0 0 0 18 18'],
  plus: ['M12 5v14M5 12h14'], search: ['M21 21l-5-5', 'M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0'],
  arrow: ['M5 12h14M14 7l5 5-5 5'], chevron: ['M9 5l7 7-7 7'], down: ['M6 9l6 6 6-6'],
  bolt: ['M13 2L4 14h7l-1 8 10-13h-7z'], check: ['M5 12l4 4L19 6'],
  close: ['M6 6l12 12M18 6L6 18'], external: ['M14 3h7v7M21 3L10 14', 'M10 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-5'],
  code: ['M8 7l-5 5 5 5M16 7l5 5-5 5M14 4l-4 16'],
  terminal: ['M4 7l5 5-5 5M12 17h7'],
  alert: ['M12 8v5M12 17h.01', 'M10.3 3.9L2 18a2 2 0 0 0 1.7 3h16.6a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z'],
  copy: ['M9 9h12v12H9z', 'M5 15H3V3h12v2'], trash: ['M3 6h18M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7M14 10v7'],
  pause: ['M8 5v14M16 5v14'], menu: ['M4 6h16M4 12h16M4 18h16'],
  branch: ['M6 3v12a4 4 0 0 0 4 4h2M18 4v4a4 4 0 0 1-4 4H6', 'M9 18a3 3 0 1 1-6 0 3 3 0 0 1 6 0M21 4a3 3 0 1 1-6 0 3 3 0 0 1 6 0'],
  monitor: ['M3 4h18v13H3zM12 17v4M8 21h8'], phone: ['M7 2h10a2 2 0 0 1 2 2v16a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2zM11 18h2'],
  link: ['M10 13a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-2 2M14 11a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l2-2'],
  sun: ['M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5L19 19M5 19l1.5-1.5M17.5 6.5L19 5', 'M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0'],
  download: ['M12 3v12M7 10l5 5 5-5M4 16v5h16v-5'],
  leaf: ['M20 3C9 2 2 9 5 16s17 3 15-13zM5 19L16 8'],
  info: ['M12 11v6M12 7h.01', 'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0']
}
const AppIcon = {
  props: { name: String, size: { default: 18 } },
  setup: () => ({ icons: ICONS }),
  template: `<svg :width="size" :height="size" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path v-for="(p,i) in (icons[name] || icons.code)" :key="i" :d="p"></path></svg>`
}
const INITIAL = [
  { id:'web', name:'管理前端', slug:'web-console', type:'JavaScript', runtime:'Vue 3 · Quasar', mark:'V', tone:'mint', port:5173, mode:'模块热替换', state:'running', version:4, command:'npm run dev', path:'C:\\Projects\\no-ide\\web', watch:'src/**', auto:true, last:'09:41:08', description:'页面变化，即刻可见。' },
  { id:'api', name:'业务服务', slug:'core-api', type:'Java', runtime:'Java 21 · Spring Boot', mark:'J', tone:'peach', port:8080, mode:'应用重启', state:'running', version:3, command:'./mvnw spring-boot:run', path:'C:\\Projects\\no-ide\\core-api', watch:'src/main/**', auto:true, last:'09:41:06', description:'订单、用户与核心业务接口。' },
  { id:'worker', name:'任务服务', slug:'task-worker', type:'Python', runtime:'Python 3.12 · Uvicorn', mark:'Py', tone:'blue', port:8000, mode:'进程重启', state:'running', version:2, command:'python -m uvicorn app:app --reload', path:'C:\\Projects\\no-ide\\worker', watch:'app/**', auto:true, last:'09:40:52', description:'异步处理和自动化任务。' },
  { id:'gateway', name:'网关服务', slug:'gateway', type:'Java', runtime:'Java 21 · Spring Boot', mark:'J', tone:'peach', port:9000, mode:'应用重启', state:'stopped', version:0, command:'./mvnw spring-boot:run', path:'C:\\Projects\\no-ide\\gateway', watch:'src/main/**', auto:true, last:'—', description:'统一入口，与业务服务协同运行。' },
  { id:'android', name:'安卓客户端', slug:'android-app', type:'Android', runtime:'Gradle · Android SDK', mark:'A', tone:'green', port:null, mode:'重新部署', state:'stopped', version:0, command:'./gradlew assembleDebug', path:'C:\\Projects\\no-ide\\android', watch:'app/src/**', auto:false, last:'—', description:'构建、安装到设备并查看运行日志。' },
  { id:'node', name:'Node 工具服务', slug:'node-tools', type:'Node.js', runtime:'Node.js 22', mark:'N', tone:'lime', port:3000, mode:'进程重启', state:'stopped', version:0, command:'node --watch src/index.js', path:'C:\\Projects\\no-ide\\tools', watch:'src/**', auto:true, last:'—', description:'轻量接口与开发工具。' }
]
const now = () => new Date().toLocaleTimeString('zh-CN', { hour12:false })
const wait = (ms) => new Promise(resolve => setTimeout(resolve, ms))
const safeRead = () => { try { const v=JSON.parse(localStorage.getItem(STORAGE)||'{}'); return v && typeof v==='object' ? v : {} } catch { return {} } }

export function createNoIdeApp() {
 return {
  components: { AppIcon },
  setup() {
    const saved = safeRead()
    const services = ref(INITIAL.map(s=>({...s, busy:false, step:4, error:null, pending:false})))
    const settings = ref({ theme:saved.theme==='space'?'space':'pink', compact:!!saved.compact, motion:saved.motion!==false, auto:saved.auto!==false, demoDevice:false })
    const page=ref('run'), selectedId=ref('api'), filter=ref('all'), serviceSearch=ref(''), detailTab=ref('info'), outputTab=ref('logs')
    const outputScope=ref('all'), logLevel=ref('all'), logSearch=ref(''), logPaused=ref(false), pausedSnapshot=ref([]), logElement=ref(null)
    const collapsed=ref(false), mobileOpen=ref(false), modal=ref(null), toast=ref(null), globalSearch=ref(''), copyText=ref('')
    const requestPath=ref('/api/health'), requestMethod=ref('GET'), response=ref(null), batchBusy=ref(false)
    const form=ref({name:'', type:'Java', path:'', port:8081, command:''}), formError=ref(''), configDraft=ref(null)
    const epochs=new Map(), queued=new Map(), logBytes=new TextEncoder()
    let toastTimer=0, mounted=true, batchEpoch=0, focusBeforeModal=null
    const logs=ref([
      {id:1,time:'09:40:52',service:'task-worker',level:'INFO',message:'[示例] Uvicorn 启动完成，等待任务。'},
      {id:2,time:'09:41:02',service:'core-api',level:'INFO',message:'[示例] 检测到 UserController.java 变化，合并本次修改。'},
      {id:3,time:'09:41:03',service:'core-api',level:'BUILD',message:'[示例] 编译完成；开始应用重启。'},
      {id:4,time:'09:41:06',service:'core-api',level:'READY',message:'[示例] 就绪检查通过 → http://localhost:8080'},
      {id:5,time:'09:41:08',service:'web-console',level:'HMR',message:'[示例] 模块已替换 /src/pages/Dashboard.vue'},
      {id:6,time:'09:41:08',service:'no-ide',level:'INFO',message:'交互预览已就绪。尚未连接执行器，没有启动任何本机进程。'}
    ])
    const history=ref([{id:1,time:'09:41:08',service:'web-console',title:'模块热替换',result:'成功',detail:'Dashboard.vue · 示例记录'},{id:2,time:'09:41:06',service:'core-api',title:'应用重启',result:'成功',detail:'UserController.java · 示例记录'}])
    let logId=6, historyId=2
    const nav=[{id:'run',icon:'grid',label:'运行台'},{id:'projects',icon:'folder',label:'项目管理'},{id:'history',icon:'clock',label:'运行记录'},{id:'env',icon:'chip',label:'环境与设备'},{id:'settings',icon:'settings',label:'设置'}]
    const titles={run:'运行台',projects:'项目管理',history:'运行记录',env:'环境与设备',settings:'设置'}
    const selected=computed(()=>services.value.find(s=>s.id===selectedId.value)||services.value[0])
    const running=computed(()=>services.value.filter(s=>s.state==='running').length)
    const issues=computed(()=>services.value.filter(s=>s.error))
    const updating=computed(()=>services.value.filter(s=>s.busy).length)
    const visibleServices=computed(()=>services.value.filter(s=>(filter.value==='all'||(filter.value==='running'&&s.state==='running')||(filter.value==='issues'&&s.error))&&`${s.name} ${s.slug} ${s.type}`.toLowerCase().includes(serviceSearch.value.toLowerCase())))
    const searchResults=computed(()=>services.value.filter(s=>`${s.name} ${s.slug} ${s.type}`.toLowerCase().includes(globalSearch.value.toLowerCase())))
    const filteredLogs=computed(()=>(logPaused.value?pausedSnapshot.value:logs.value).filter(l=>(outputScope.value==='all'||l.service===selected.value.slug)&&(logLevel.value==='all'||l.level==='ERROR')&&`${l.service} ${l.message}`.toLowerCase().includes(logSearch.value.toLowerCase())))
    const shownLogs=computed(()=>filteredLogs.value.slice(-120))
    const selectedHistory=computed(()=>history.value.filter(h=>h.service===selected.value.slug))
    const stateLabel=s=>s.busy?(s.step===0?'发现改动':s.step===1?'构建中':s.step===2?'更新中':'等待就绪'):s.state==='running'?'运行中':s.type==='Android'&&!settings.value.demoDevice?'等待设备':'已停止'
    const stateClass=s=>s.busy?'working':s.state==='running'?'running':'stopped'
    const notify=(message,tone='info')=>{clearTimeout(toastTimer);toast.value={message,tone};toastTimer=setTimeout(()=>toast.value=null,3500)}
    function addLog(s,level,message){
      logs.value.push({id:++logId,time:now(),service:s?.slug||'no-ide',level,message:message.slice(0,2048)})
      if(logs.value.length>MAX_LOGS)logs.value.splice(0,logs.value.length-MAX_LOGS)
      let size=logs.value.reduce((n,l)=>n+logBytes.encode(JSON.stringify(l)).length,0)
      while(size>MAX_LOG_BYTES&&logs.value.length){size-=logBytes.encode(JSON.stringify(logs.value[0])).length;logs.value.shift()}
      nextTick(()=>{if(!logPaused.value&&logElement.value)logElement.value.scrollTop=logElement.value.scrollHeight})
    }
    const addHistory=(s,title,result,detail)=>{history.value.unshift({id:++historyId,time:now(),service:s.slug,title,result,detail});if(history.value.length>80)history.value.length=80}
    function pick(s){selectedId.value=s.id;detailTab.value='info';response.value=null;configDraft.value=null}
    function go(id){page.value=id;mobileOpen.value=false}
    function openModal(name){modal.value=name;formError.value=''}
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
          addHistory(s,'更新失败','失败',wasRunning?'旧版本继续运行 · 示例':'未启动 · 示例');outputTab.value='issues';notify('模拟构建失败。旧版本没有被停止。','error');
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
    async function runAll(){if(batchBusy.value)return;const epoch=++batchEpoch;batchBusy.value=true;for(const s of services.value){if(epoch!==batchEpoch||!mounted)break;if(s.state!=='running'&&!s.busy){if(s.type==='Android'&&!settings.value.demoDevice){addLog(s,'INFO','[示例] 跳过 Android：尚未选择示例设备。');continue}await updateService(s,{start:true})}}if(epoch===batchEpoch)batchBusy.value=false}
    function stopAll(){batchEpoch++;batchBusy.value=false;services.value.forEach(s=>{if(s.busy||s.state==='running')stop(s)});notify('工作区已全部停止（模拟）。')}
    function applyPending(s){const opts=queued.get(s.id)||{};queued.delete(s.id);void updateService(s,{...opts,manual:true})}
    function change(s,fail=false){void updateService(s,{fail});}
    function addProject(){
      const f=form.value
      if(!f.name.trim()||!f.path.trim()){formError.value='请填写项目名称和项目目录。';return}
      if(f.type!=='Android'&&(!Number.isInteger(Number(f.port))||Number(f.port)<1||Number(f.port)>65535)){formError.value='端口应为 1～65535 的整数。';return}
      if(services.value.some(s=>s.name===f.name.trim())){formError.value='这个项目名称已存在。';return}
      if(f.type!=='Android'&&services.value.some(s=>s.port===Number(f.port))){formError.value='这个示例端口已被其他服务配置使用。';return}
      const maps={Java:['J','peach','应用重启','./mvnw spring-boot:run'],JavaScript:['V','mint','模块热替换','npm run dev'],'Node.js':['N','lime','进程重启','node --watch src/index.js'],Python:['Py','blue','进程重启','python app.py'],Android:['A','green','重新部署','./gradlew assembleDebug']}
      const m=maps[f.type]||maps.Java, s={id:`project-${Date.now()}`,name:f.name.trim(),slug:`project-${services.value.length+1}`,type:f.type,runtime:f.type,mark:m[0],tone:m[1],mode:m[2],command:f.command.trim()||m[3],path:f.path.trim(),port:f.type==='Android'?null:Number(f.port),state:'stopped',version:0,auto:true,busy:false,step:0,pending:false,error:null,watch:'src/**',last:'—',description:'在预览中添加的项目，本次会话有效。'}
      services.value.push(s);pick(s);go('run');modal.value=null;notify('项目已添加到预览。未访问该目录，也未执行命令。','success');form.value={name:'',type:'Java',path:'',port:8081,command:''}
    }
    function editConfig(){configDraft.value={...selected.value};detailTab.value='config'}
    function saveConfig(){
      const d=configDraft.value
      if(!d||!d.command.trim()||!d.path.trim()){notify('项目目录和运行命令不能为空。','error');return}
      if(d.type!=='Android'&&(!Number.isInteger(Number(d.port))||Number(d.port)<1||Number(d.port)>65535)){notify('请输入有效端口。','error');return}
      if(d.type!=='Android'&&services.value.some(s=>s.id!==d.id&&s.port===Number(d.port))){notify('此端口已被其他示例服务配置使用。','error');return}
      Object.assign(selected.value,{path:d.path,command:d.command,port:d.type==='Android'?null:Number(d.port),watch:d.watch,mode:d.mode,auto:d.auto});detailTab.value='info';notify('运行配置已保存到本次预览；没有执行命令。','success')
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
    function clearLogs(){logs.value=[];pausedSnapshot.value=[];notify('已清空示例日志展示。')}
    function toggleTheme(){settings.value.theme=settings.value.theme==='pink'?'space':'pink'}
    function keydown(e){
      if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){e.preventDefault();globalSearch.value='';openModal('search')}
      if(e.key==='Escape'){modal.value=null;mobileOpen.value=false}
      if(e.key==='Tab'&&modal.value){const nodes=[...document.querySelectorAll('.modal [data-focus], .modal button:not([disabled]), .modal input:not([disabled]), .modal select, .modal textarea')].filter(el=>el.getClientRects().length);if(!nodes.length)return;const first=nodes[0],last=nodes[nodes.length-1];if(e.shiftKey&&(document.activeElement===first||!nodes.includes(document.activeElement))){e.preventDefault();last.focus()}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus()}}
    }
    watch(modal,async(v,old)=>{if(v&&!old)focusBeforeModal=document.activeElement;await nextTick();if(v)document.querySelector('.modal [data-focus], .modal input, .modal button')?.focus();else focusBeforeModal?.focus?.()})
    watch(settings,v=>{try{localStorage.setItem(STORAGE,JSON.stringify({theme:v.theme,compact:v.compact,motion:v.motion,auto:v.auto}))}catch{}},{deep:true})
    watch(detailTab,v=>{if(v==='config')configDraft.value={...selected.value}})
    onMounted(()=>{document.addEventListener('keydown',keydown)})
    onUnmounted(()=>{mounted=false;batchEpoch++;clearTimeout(toastTimer);document.removeEventListener('keydown',keydown)})
    return {services,settings,page,selectedId,selected,filter,serviceSearch,detailTab,outputTab,outputScope,logLevel,logSearch,logPaused,logElement,collapsed,mobileOpen,modal,toast,globalSearch,searchResults,copyText,requestPath,requestMethod,response,batchBusy,form,formError,configDraft,nav,titles,running,issues,updating,visibleServices,filteredLogs,shownLogs,history,selectedHistory,stateLabel,stateClass,notify,pick,go,openModal,openService,updateService,stop,runAll,stopAll,applyPending,change,addProject,editConfig,saveConfig,copy,copyError,sendRequest,downloadLogs,togglePause,clearLogs,toggleTheme}
  },
  template: `
<div class="no-ide" :class="[{compact:settings.compact, 'no-motion':!settings.motion, 'sidebar-collapsed':collapsed},'theme-'+settings.theme]">
  <aside class="sidebar" :class="{'mobile-open':mobileOpen}">
    <a class="brand" href="#" @click.prevent="go('run')" aria-label="No-ide 首页"><span class="brand-symbol">n<span>›</span></span><span class="brand-word">No-ide<small>少一点工具，多一点创造。</small></span></a>
    <div class="workspace-switch"><span class="workspace-avatar">N</span><div><strong>本地开发空间</strong><small>个人工作区 · 示例</small></div><app-icon name="down" :size="15"></app-icon></div>
    <div class="nav-caption">工作空间</div>
    <nav aria-label="主导航"><button v-for="n in nav" :key="n.id" :class="['nav-item',{active:page===n.id}]" @click="go(n.id)" :aria-label="n.label" :aria-current="page===n.id?'page':undefined"><app-icon :name="n.icon" :size="19"></app-icon><span>{{n.label}}</span><b v-if="n.id==='run'">{{services.length}}</b></button></nav>
    <div class="sidebar-projects"><div class="nav-caption">已固定工作区 <button title="添加项目" aria-label="添加项目" @click="openModal('add')"><app-icon name="plus" :size="15"></app-icon></button></div><button class="pinned-project" @click="go('run');filter='all'"><i class="dot pink"></i><span>No-ide 本地开发</span><small>{{services.length}}</small></button><div class="project-branch"><app-icon name="branch" :size="13"></app-icon><span>main</span><small>示例</small></div></div>
    <div class="sidebar-bottom"><div class="executor-card"><span class="executor-icon"><app-icon name="monitor"></app-icon></span><div><strong>本地执行器</strong><small><i class="dot gray"></i> 尚未连接</small></div><button @click="openModal('connect')" title="连接说明" aria-label="连接说明"><app-icon name="info" :size="16"></app-icon></button></div><div class="profile"><span class="profile-avatar">我</span><div><strong>我的工作台</strong><small>先看操作，再连接运行</small></div><button @click="collapsed=!collapsed" title="折叠侧栏" aria-label="折叠侧栏"><app-icon name="menu" :size="17"></app-icon></button></div></div>
  </aside>
  <button v-if="mobileOpen" class="sidebar-mask" @click="mobileOpen=false" aria-label="关闭导航"></button>
  <main class="main">
    <header class="topbar"><div class="breadcrumb"><button class="mobile-menu" @click="mobileOpen=!mobileOpen" aria-label="展开导航"><app-icon name="menu"></app-icon></button><span>工作空间</span><app-icon name="chevron" :size="13"></app-icon><strong>No-ide 本地开发</strong><span class="branch-badge"><app-icon name="branch" :size="13"></app-icon> main</span></div><div class="topbar-right"><button class="search-trigger" @click="globalSearch='';openModal('search')"><app-icon name="search" :size="16"></app-icon><span>搜索服务</span><kbd>Ctrl K</kbd></button><button class="icon-btn" @click="toggleTheme" aria-label="切换主题" title="切换粉色 / 星空主题"><app-icon name="sun"></app-icon></button><span class="top-avatar">我</span></div></header>
    <div class="page-body">
      <section class="page-heading"><div><div class="heading-line"><h1>{{titles[page]}}</h1><span class="preview-pill"><span></span>交互预览</span></div><p>{{page==='run'?'代码交给 AI，运行留在这里。':page==='projects'?'把不同语言的项目，放在同一个工作空间。':page==='history'?'每一次启动、更新和停止，都有迹可循。':page==='env'?'需要的时候再启动，不让工具链常驻。':'让工作台按你的习惯运行。'}}</p></div><div class="heading-actions" v-if="page==='run'||page==='projects'"><q-btn class="app-btn secondary" @click="openModal('add')"><app-icon name="plus" :size="16"></app-icon><span>添加项目</span></q-btn><q-btn class="app-btn primary" :disable="batchBusy" @click="runAll"><app-icon name="play" :size="15"></app-icon><span>{{batchBusy?'正在启动…':'运行全部'}}</span></q-btn><q-btn class="app-btn icon-only secondary" @click="stopAll" aria-label="停止全部" title="停止全部"><app-icon name="stop" :size="16"></app-icon></q-btn></div></section>
      <template v-if="page==='run'">
        <section class="overview-strip"><div><span class="overview-icon rose"><app-icon name="folder"></app-icon></span><div><small>工作区服务</small><strong>{{services.length}}<span> 个</span></strong></div></div><div><span class="overview-icon mint"><app-icon name="play"></app-icon></span><div><small>正在运行</small><strong>{{running}}<span> 个</span></strong></div></div><div><span class="overview-icon sand"><app-icon :name="issues.length?'alert':'check'"></app-icon></span><div><small>待处理问题</small><strong>{{issues.length}}<span> 个</span></strong></div></div><div class="auto-overview"><span class="overview-icon blue"><app-icon name="bolt"></app-icon></span><div><small>自动更新</small><strong class="auto-text">{{settings.auto?'改完即运行':'手动应用改动'}}</strong></div><q-toggle v-model="settings.auto" color="primary" size="34px" aria-label="自动更新"></q-toggle></div></section>
        <div class="runtime-grid">
          <section class="panel services-panel"><header class="panel-header"><div><h2>服务</h2><span class="count">{{services.length}}</span></div><div class="tiny-muted"><i class="dot green"></i> {{updating?updating+' 个任务处理中':'所有状态均为示例'}}</div></header><div class="service-toolbar"><div class="mini-tabs"><button @click="filter='all'" :class="{active:filter==='all'}">全部</button><button @click="filter='running'" :class="{active:filter==='running'}">运行中</button><button @click="filter='issues'" :class="{active:filter==='issues'}">有问题<span v-if="issues.length" class="small-count">{{issues.length}}</span></button></div><div class="service-search"><app-icon name="search" :size="15"></app-icon><input v-model="serviceSearch" placeholder="筛选服务" aria-label="筛选服务"></div></div>
          <div class="service-list"><article v-for="s in visibleServices" :key="s.id" :class="['service-row',{selected:selectedId===s.id}]" @click="pick(s)" tabindex="0" @keydown.enter="pick(s)" :aria-label="s.name+' '+stateLabel(s)"><span :class="['language-icon',s.tone]">{{s.mark}}</span><div class="service-main"><div class="service-title"><strong>{{s.name}}</strong><span v-if="s.error" class="issue-mark" title="最近一次更新失败">!</span></div><div class="service-meta"><span>{{s.slug}}</span><span class="meta-dot">·</span><span>{{s.port?':'+s.port:'Android'}}</span></div></div><div class="service-end"><span :class="['status',stateClass(s)]"><i class="dot"></i>{{stateLabel(s)}}</span><div class="row-actions"><q-btn class="app-btn row-action" v-if="s.state!=='running'&&!s.busy" @click.stop="updateService(s,{start:true})" :aria-label="'运行'+s.name" :title="'运行'+s.name"><app-icon name="play" :size="15"></app-icon></q-btn><q-btn class="app-btn row-action" v-else @click.stop="stop(s)" :aria-label="'停止'+s.name" :title="'停止'+s.name"><app-icon name="stop" :size="14"></app-icon></q-btn><q-btn class="app-btn row-action" :disable="s.busy||s.state!=='running'" @click.stop="updateService(s,{manual:true})" :aria-label="'重新运行'+s.name" title="重新运行"><app-icon name="refresh" :size="15"></app-icon></q-btn></div></div></article><div v-if="!visibleServices.length" class="empty-state small"><app-icon :name="filter==='issues'?'check':'search'" :size="28"></app-icon><strong>{{filter==='issues'?'目前没有待处理问题':'没有匹配的服务'}}</strong><span>{{filter==='issues'?'可以在右侧体验一次编译失败。':'换个关键词或筛选条件试试。'}}</span><button class="text-button" @click="filter='all';serviceSearch=''">显示全部服务</button></div></div>
          <footer class="service-footer"><app-icon name="info" :size="14"></app-icon><span>各服务独立更新，互不打断。</span><button @click="go('projects')">管理项目 <app-icon name="arrow" :size="13"></app-icon></button></footer></section>
          <section class="panel detail-panel"><header class="detail-header"><div class="detail-title"><span :class="['language-icon small',selected.tone]">{{selected.mark}}</span><div><h2>{{selected.name}}</h2><p>{{selected.runtime}}</p></div></div><q-btn class="app-btn row-action" @click="editConfig" aria-label="配置当前服务" title="配置当前服务"><app-icon name="settings" :size="17"></app-icon></q-btn></header><div class="detail-tabs"><button @click="detailTab='info'" :class="{active:detailTab==='info'}">运行信息</button><button @click="detailTab='preview'" :class="{active:detailTab==='preview'}">结果预览</button><button @click="editConfig" :class="{active:detailTab==='config'}">运行配置</button></div>
          <div v-if="detailTab==='info'" class="detail-content"><div class="endpoint-row"><span><app-icon :name="selected.type==='Android'?'phone':'link'" :size="16"></app-icon><code>{{selected.port?'localhost:'+selected.port:settings.demoDevice?'示例 Android 设备':'尚未选择设备'}}</code></span><button @click="detailTab='preview'">打开预览 <app-icon name="external" :size="13"></app-icon></button></div><div class="info-grid"><div><small>更新方式</small><strong><app-icon name="bolt" :size="14"></app-icon>{{selected.mode}}</strong></div><div><small>当前版本 <span class="muted">· 示例</span></small><strong>{{selected.version?'v'+selected.version:'尚未运行'}}</strong></div><div><small>最近更新 <span class="muted">· 示例</span></small><strong>{{selected.last}}</strong></div><div><small>自动监听</small><q-toggle v-model="selected.auto" color="primary" size="30px" :label="selected.auto?'已开启':'已关闭'" aria-label="当前服务自动监听"></q-toggle></div></div><div class="flow-heading"><strong>从改动到就绪</strong><span>{{selected.busy?'正在演示…':selected.error?'上次更新未完成':'更新过程可见'}}</span></div><div class="update-flow"><div v-for="(label,i) in ['发现改动','构建','更新','就绪']" :key="label" :class="{done:selected.step>i,active:selected.busy&&selected.step===i,failed:selected.error&&i===1}"><span><app-icon v-if="selected.step>i&&!selected.error" name="check" :size="12"></app-icon><template v-else>{{i+1}}</template></span><small>{{label}}</small></div></div><div v-if="selected.error" class="feedback error"><app-icon name="alert" :size="18"></app-icon><div><strong>更新失败，旧版本继续运行</strong><span>构建产物未发布。先修复问题，再重新更新。</span></div></div><div v-else-if="selected.pending" class="feedback pending"><app-icon name="clock" :size="18"></app-icon><div><strong>有待处理的代码改动</strong><button class="text-button" @click="applyPending(selected)">应用待处理改动 →</button></div></div><div v-else class="feedback"><app-icon :name="selected.state==='running'?'check':'info'" :size="18"></app-icon><div><strong>{{selected.busy?'更新流程正在进行':selected.state==='running'?'服务已就绪，随时查看结果':'服务尚未运行'}}</strong><span>{{selected.state==='running'?'不需要打开 IDE，也能知道发生了什么。':'点击左侧运行按钮，体验完整启动过程。'}}</span></div></div><div class="demo-actions"><q-btn class="app-btn soft" :disable="selected.state!=='running'" @click="change(selected)"><app-icon name="bolt" :size="15"></app-icon>模拟代码改动</q-btn><button class="failure-demo" :disabled="selected.state!=='running'" @click="change(selected,true)">模拟编译失败</button></div><p class="detail-note">仅演示交互，不执行编译、不保留真实应用状态。</p></div>
          <div v-else-if="detailTab==='preview'" class="detail-content preview-content"><div class="preview-notice"><app-icon name="info" :size="15"></app-icon>示例响应 · 不发送网络请求</div><div v-if="selected.type==='Android'" class="device-preview"><app-icon name="phone" :size="44"></app-icon><strong>{{settings.demoDevice?'示例设备已选中':'尚未连接 Android 设备'}}</strong><p>真实设备画面和日志，需要连接本地执行器。</p><q-btn class="app-btn soft" @click="openModal('device')">设备说明</q-btn></div><template v-else><div class="request-bar"><select v-model="requestMethod" aria-label="请求方法"><option>GET</option><option>POST</option></select><input v-model="requestPath" aria-label="接口路径" placeholder="/api/health"><q-btn class="app-btn primary" @click="sendRequest">试运行</q-btn></div><div class="response-title"><span>响应内容</span><b v-if="response" :class="response.status===200?'success-text':'error-text'">{{response.status}} {{response.status===200?'OK':'Unavailable'}}</b><span v-else class="muted">待请求</span></div><pre class="response-code">{{response?response.body:'// 点击「试运行」查看示例响应\\n// 这里不会访问 localhost\\n// 真实结果将在接入执行器后显示'}}</pre></template></div>
          <form v-else-if="configDraft" class="detail-content config-form" @submit.prevent="saveConfig"><label>项目目录<input v-model="configDraft.path" required></label><label>运行命令<input v-model="configDraft.command" class="mono" required></label><div class="form-columns"><label>端口<input v-model="configDraft.port" :disabled="selected.type==='Android'" type="number" min="1" max="65535"></label><label>更新方式<select v-model="configDraft.mode"><option>模块热替换</option><option>应用重启</option><option>进程重启</option><option>重新部署</option></select></label></div><label>监听范围<input v-model="configDraft.watch"></label><div class="config-footer"><span>仅保存到本次预览</span><q-btn class="app-btn primary" @click="saveConfig">保存配置</q-btn></div></form></section>
        </div>
        <section class="panel output-panel"><header class="output-header"><div class="output-tabs"><button @click="outputTab='logs'" :class="{active:outputTab==='logs'}"><app-icon name="terminal" :size="16"></app-icon>运行日志</button><button @click="outputTab='issues'" :class="{active:outputTab==='issues'}">问题 <span :class="['tab-count',{danger:issues.length}]">{{issues.length}}</span></button><button @click="outputTab='changes'" :class="{active:outputTab==='changes'}">变更记录</button></div><div class="output-controls"><select v-model="outputScope" aria-label="日志服务范围"><option value="all">全部服务</option><option value="selected">当前服务</option></select><button @click="togglePause" :aria-label="logPaused?'继续日志':'暂停日志'" :title="logPaused?'继续日志':'暂停日志'" :class="{selected:logPaused}"><app-icon :name="logPaused?'play':'pause'" :size="15"></app-icon></button><button @click="downloadLogs" aria-label="导出日志" title="导出日志"><app-icon name="download" :size="15"></app-icon></button><button @click="clearLogs" aria-label="清空日志" title="清空日志"><app-icon name="trash" :size="15"></app-icon></button></div></header>
        <template v-if="outputTab==='logs'"><div class="log-toolbar"><div class="log-search"><app-icon name="search" :size="13"></app-icon><input v-model="logSearch" placeholder="搜索日志内容…" aria-label="搜索日志"></div><label><input type="checkbox" :checked="logLevel==='error'" @change="logLevel=$event.target.checked?'error':'all'">仅错误</label><span>{{logPaused?'展示已暂停，后台仍有界收集':'实时展示'}} · 示例日志</span></div><div class="log-body" ref="logElement"><div class="log-row" v-for="l in shownLogs" :key="l.id"><time>{{l.time}}</time><span :class="['log-level',l.level.toLowerCase()]">{{l.level}}</span><span class="log-service">{{l.service}}</span><span class="log-message">{{l.message}}</span></div><div class="empty-log" v-if="!shownLogs.length">{{logSearch||logLevel!=='all'?'没有匹配的日志。':'这里还没有日志。运行服务或模拟代码改动即可查看。'}}</div></div><footer class="log-footer"><span><i class="dot green"></i>界面就绪 <span class="muted">· 执行器未连接</span></span><span>保留 {{filteredLogs.length}} 条 · 最多渲染最近 120 条</span></footer></template>
        <div v-else-if="outputTab==='issues'" class="issues-body"><div v-if="!issues.length" class="empty-state horizontal"><span class="success-circle"><app-icon name="check" :size="23"></app-icon></span><div><strong>当前没有待处理问题</strong><span>可以在右侧点击“模拟编译失败”，查看错误反馈。</span></div></div><div v-for="s in issues" :key="s.id" class="issue-row"><app-icon name="alert" :size="21"></app-icon><div><strong>{{s.name}} · {{s.error.message}}</strong><code>{{s.error.file}}</code><span>示例错误 · {{s.state==='running'?'旧版本继续运行，失败产物未发布':'当前已停止'}}</span></div><button class="text-button" @click="copyError(s)"><app-icon name="copy" :size="14"></app-icon>复制给 AI</button><q-btn class="app-btn soft" @click="updateService(s,{manual:true})" :disable="s.busy">重试更新</q-btn></div></div><div v-else class="changes-body"><div v-for="h in history.slice(0,8)" :key="h.id" class="change-row"><time>{{h.time}}</time><i :class="['dot',h.result==='失败'?'red':'green']"></i><strong>{{h.service}}</strong><span>{{h.title}}</span><small>{{h.detail}}</small></div><div v-if="!history.length" class="empty-log">还没有运行记录。</div></div></section>
      </template>
      <section v-else-if="page==='projects'" class="projects-page"><div class="section-intro"><span><app-icon name="folder" :size="18"></app-icon>No-ide 本地开发 <small>{{services.length}} 个服务</small></span><span class="muted">独立运行，也能一起工作</span></div><div class="project-cards"><article v-for="s in services" :key="s.id" class="panel project-card"><header><span :class="['language-icon',s.tone]">{{s.mark}}</span><span :class="['status',stateClass(s)]"><i class="dot"></i>{{stateLabel(s)}}</span></header><h2>{{s.name}}</h2><p>{{s.description}}</p><code>{{s.path}}</code><div class="project-card-tags"><span>{{s.type}}</span><span>{{s.mode}}</span></div><footer><button @click="openService(s)">进入运行台 <app-icon name="arrow" :size="15"></app-icon></button><button @click="openService(s);editConfig()" aria-label="配置项目"><app-icon name="settings" :size="17"></app-icon></button></footer></article><button class="add-project-card" @click="openModal('add')"><span><app-icon name="plus" :size="25"></app-icon></span><strong>添加一个项目</strong><small>无需迁移代码，使用原有工程</small></button></div></section>
      <section v-else-if="page==='history'" class="panel history-panel"><header class="panel-header"><div><h2>最近活动</h2><span class="count">{{history.length}}</span></div><span class="tiny-muted">全部为当前预览中的示例记录</span></header><div class="history-list"><article v-for="h in history" :key="h.id" class="history-row"><span :class="['history-symbol',h.result==='失败'?'bad':'good']"><app-icon :name="h.result==='失败'?'alert':h.title==='停止服务'?'stop':'check'" :size="17"></app-icon></span><div><strong>{{h.title}} <span>{{h.service}}</span></strong><p>{{h.detail}}</p></div><span :class="h.result==='失败'?'error-text':'muted'">{{h.result}}</span><time>{{h.time}}</time></article></div></section>
      <section v-else-if="page==='env'" class="environment-page"><div class="connection-banner"><span class="overview-icon blue"><app-icon name="monitor" :size="23"></app-icon></span><div><h2>连接执行器，才开始真实运行</h2><p>当前不会读取你的电脑。工具版本、内存占用、设备状态都将在连接后显示。</p></div><q-btn class="app-btn primary" @click="openModal('connect')">连接说明 <app-icon name="arrow" :size="15"></app-icon></q-btn></div><h2 class="section-title">语言与工具链</h2><div class="toolchain-grid"><article class="panel tool-card" v-for="tool in [{name:'Java',mark:'J',tone:'peach',desc:'JDK · Maven · Gradle',text:'单体 / Spring Boot / 多服务'},{name:'JavaScript / Node.js',mark:'N',tone:'mint',desc:'Node.js · npm / pnpm',text:'前端热替换 / 服务进程重启'},{name:'Python',mark:'Py',tone:'blue',desc:'Python · 虚拟环境',text:'脚本 / Web 服务自动重载'},{name:'Android',mark:'A',tone:'green',desc:'Android SDK · ADB',text:'构建 / 安装 / 启动 / 日志'}]" :key="tool.name"><header><span :class="['language-icon',tool.tone]">{{tool.mark}}</span><span class="status stopped"><i class="dot"></i>未检测</span></header><h3>{{tool.name}}</h3><p>{{tool.desc}}</p><small>{{tool.text}}</small><button class="text-button" @click="openModal('connect')">连接后检测 <app-icon name="arrow" :size="14"></app-icon></button></article></div><h2 class="section-title">Android 设备</h2><div class="panel device-empty"><app-icon name="phone" :size="34"></app-icon><div><strong>{{settings.demoDevice?'已启用示例 Android 设备':'没有已连接的设备'}}</strong><p>{{settings.demoDevice?'仅用于演示部署流程，不代表连接了真实手机。':'真实设备列表由本地执行器通过 ADB 获取。'}}</p></div><q-btn class="app-btn secondary" @click="openModal('device')">体验设备流程</q-btn></div></section>
      <section v-else-if="page==='settings'" class="settings-page"><div class="panel settings-card"><header><h2>外观</h2><p>清爽、直接，把空间留给操作。</p></header><div class="setting-row"><div><strong>主题颜色</strong><p>默认粉色，也可以切换星空色。</p></div><div class="theme-options"><button @click="settings.theme='pink'" :class="{active:settings.theme==='pink'}"><span class="theme-dot pink"></span>樱花粉</button><button @click="settings.theme='space'" :class="{active:settings.theme==='space'}"><span class="theme-dot space"></span>星空蓝</button></div></div><div class="setting-row"><div><strong>紧凑布局</strong><p>缩小服务行距，在一屏内显示更多内容。</p></div><q-toggle v-model="settings.compact" color="primary" aria-label="紧凑布局"></q-toggle></div><div class="setting-row"><div><strong>界面动效</strong><p>轻量反馈，并尊重系统的减少动态效果设置。</p></div><q-toggle v-model="settings.motion" color="primary" aria-label="界面动效"></q-toggle></div></div><div class="panel settings-card"><header><h2>运行偏好</h2><p>此处只保存界面偏好，不会执行本机命令。</p></header><div class="setting-row"><div><strong>自动应用代码改动</strong><p>关闭后，发现的改动等待你手动应用。</p></div><q-toggle v-model="settings.auto" color="primary" aria-label="自动应用代码改动"></q-toggle></div><div class="setting-row"><div><strong>日志保留策略</strong><p>最多 500 条 / 96 KiB（先到为准），仅渲染最近 120 条。</p></div><span class="subtle-badge"><app-icon name="leaf" :size="14"></app-icon>有界缓冲</span></div><div class="setting-row"><div><strong>真实资源统计</strong><p>后端、浏览器、构建工具和应用需要分别统计。</p></div><span class="muted">等待真实执行器</span></div></div><div class="settings-footnote"><app-icon name="info" :size="16"></app-icon>外观和自动更新偏好保存在此浏览器；项目、日志、运行状态刷新后恢复示例。</div></section>
      <footer class="page-footnote"><span>No-ide <b>·</b> 少一点切换，多一点创造。</span><span><i class="dot amber"></i>示例项目与数据 · 未连接本地执行器</span></footer>
    </div>
  </main>
  <transition name="toast"><div v-if="toast" class="toast-message" :class="toast.tone" role="status"><app-icon :name="toast.tone==='error'?'alert':toast.tone==='success'?'check':'info'" :size="18"></app-icon><span>{{toast.message}}</span><button @click="toast=null" aria-label="关闭提示"><app-icon name="close" :size="15"></app-icon></button></div></transition>
  <div v-if="modal" class="modal-backdrop" @mousedown.self="modal=null"><section class="modal" :class="{'search-modal':modal==='search'}" role="dialog" aria-modal="true" :aria-label="modal==='add'?'添加项目':modal==='search'?'搜索服务':'操作说明'"><button class="modal-close" @click="modal=null" aria-label="关闭弹窗"><app-icon name="close" :size="20"></app-icon></button>
    <template v-if="modal==='add'"><span class="modal-kicker">WORKSPACE</span><h2>添加一个项目</h2><p class="modal-subtitle">选择类型，填入目录，其他的交给工作台。</p><form @submit.prevent="addProject"><label>项目名称<input v-model="form.name" data-focus placeholder="例如：订单服务" maxlength="40" required></label><div class="form-columns"><label>项目类型<select v-model="form.type"><option>Java</option><option>JavaScript</option><option>Node.js</option><option>Python</option><option>Android</option></select></label><label>服务端口<input v-model="form.port" type="number" min="1" max="65535" :disabled="form.type==='Android'"></label></div><label>本地项目目录<input v-model="form.path" placeholder="C:\\Projects\\my-project" required></label><label>运行命令 <span class="muted">可选</span><input v-model="form.command" placeholder="留空，使用对应类型的示例命令"></label><div class="form-hint"><app-icon name="info" :size="16"></app-icon>交互预览只记录配置，不读取目录，不执行命令。</div><div v-if="formError" class="form-error" role="alert">{{formError}}</div><div class="modal-actions"><q-btn class="app-btn secondary" @click="modal=null">取消</q-btn><q-btn class="app-btn primary" @click="addProject">添加到工作区 <app-icon name="arrow" :size="15"></app-icon></q-btn></div></form></template>
    <template v-else-if="modal==='search'"><div class="command-search"><app-icon name="search" :size="22"></app-icon><input v-model="globalSearch" data-focus placeholder="搜索服务名称、语言…" @keydown.enter="searchResults.length&&openService(searchResults[0])"><kbd>ESC</kbd></div><div class="command-caption">服务</div><div class="command-results"><button v-for="s in searchResults" :key="s.id" @click="openService(s)"><span :class="['language-icon small',s.tone]">{{s.mark}}</span><div><strong>{{s.name}}</strong><small>{{s.slug}} · {{s.runtime}}</small></div><app-icon name="arrow" :size="16"></app-icon></button><div v-if="!searchResults.length" class="empty-log">没有找到匹配的服务。</div></div></template>
    <template v-else-if="modal==='copy'"><span class="modal-kicker">COPY CONTEXT</span><h2>复制运行上下文</h2><p class="modal-subtitle">浏览器未授予剪贴板权限，请选中下方内容复制。</p><textarea class="copy-area" :value="copyText" readonly @focus="$event.target.select()" data-focus></textarea><div class="modal-actions"><q-btn class="app-btn primary" @click="modal=null">完成</q-btn></div></template>
    <template v-else-if="modal==='device'"><span class="modal-illustration"><app-icon name="phone" :size="35"></app-icon></span><h2>先体验设备部署流程</h2><p class="modal-subtitle">这里尚未连接真实手机。启用示例设备后，可以在运行台体验 Android 的构建、安装和就绪反馈。</p><div class="explain-box"><strong>真实运行时</strong><p>选择 ADB 设备 → Gradle 构建 → 安装 → 启动 → 查看设备日志。</p><small>重新部署不等于原地热替换。</small></div><div class="modal-actions"><q-btn class="app-btn secondary" @click="modal=null">暂不体验</q-btn><q-btn class="app-btn primary" @click="settings.demoDevice=true;modal=null;notify('已启用示例设备，没有连接真实手机。')">启用示例设备</q-btn></div></template>
    <template v-else><span class="modal-illustration"><app-icon name="monitor" :size="35"></app-icon></span><h2>操作台已就位，执行器还未接入</h2><p class="modal-subtitle">这一版先确认你每天怎么用：运行项目、应用改动、看结果、处理错误。</p><div class="explain-box"><strong>这一版可以体验</strong><p>服务启停、更新流程、编译失败、旧版本保留、日志筛选、配置和项目管理。</p><strong>尚未执行</strong><p>真实构建、进程管理、工具检测、手机连接、接口请求和性能测量。</p></div><div class="modal-actions"><q-btn class="app-btn primary" @click="modal=null">继续体验 <app-icon name="arrow" :size="16"></app-icon></q-btn></div></template>
  </section></div>
</div>`
 }
}
