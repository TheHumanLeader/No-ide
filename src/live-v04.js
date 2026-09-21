import {ref,computed,watch} from 'vue'
import {asRows,argv,pairs} from './visual-controls.js'
import {toggleRows,selectVisible,fileGroup} from './selection.js'
export function useWorkbenchV04(ctx){
 const {api,act,refresh,project,repo,repoId,repoStatus,selectedFiles,file,diff,modal,form,page,notice,message,plan,loadRepo,selectFile,oldConfigForm,oldInstanceForm}=ctx
 const environments=ref([]),defaults=ref({}),candidates=ref([]),envWarnings=ref([]),envDraft=ref({}),discovery=ref(null),scanning=ref(false),scanRoot=ref('.'),selectedEntry=ref(-1),commandPreview=ref(null),configType=ref('auto')
 const buildSettings=ref({}),buildReports=ref(null),commandError=ref(''),buildDetecting=ref(false),buildDetectError=ref('')
 const activeGroup=ref('default'),moveTarget=ref(''),groupDraft=ref({}),dragFiles=ref([])
 const fileFilter=ref(''),groupSaving=ref(false),anchor=ref(''),groupCache=new Map()
 let epoch=0
 const kindLabel=k=>({java:'Java',node:'Node.js',python:'Python'}[k]||k)
 const kindOf=k=>['npm-script','node-file'].includes(k)?'node':k==='python-file'?'python':'java'
 const currentKind=computed(()=>form.value.launcher?kindOf(form.value.launcher.kind):null)
 const buildKind=computed(()=>['spring-maven','maven-main'].includes(form.value.launcher?.kind)?'maven':form.value.launcher?.kind==='gradle-task'?'gradle':'')
 const matchingEnvs=computed(()=>environments.value.filter(e=>e.kind===currentKind.value))
 const instanceKind=computed(()=>{const c=project.value?.configs.find(c=>c.id===form.value.config_id);return c?.launcher?kindOf(c.launcher.kind):null})
 const instanceEnvs=computed(()=>environments.value.filter(e=>e.kind===instanceKind.value))
 const groups=computed(()=>repoStatus.value?.groups||[{id:'default',name:'默认'}])
 const groupName=computed(()=>groups.value.find(g=>g.id===activeGroup.value)?.name||'默认')
 const groupFiles=computed(()=>(repoStatus.value?.files||[]).filter(f=>(f.group||'default')===activeGroup.value))
 const selectedSet=computed(()=>new Set(selectedFiles.value))
 const visibleGroupFiles=computed(()=>groupFiles.value.filter(f=>f.path.replaceAll('\\','/').toLowerCase().includes(fileFilter.value.replaceAll('\\','/').toLowerCase())))
 const allVisibleSelected=computed(()=>visibleGroupFiles.value.length>0&&visibleGroupFiles.value.every(f=>selectedSet.value.has(f.path)))
 const changeStatus=f=>({unversioned:'未纳入版本控制',modified:'已修改',added:'已加入版本控制',deleted:'已删除',missing:'文件缺失',' M':'已修改','M ':'已暂存修改','??':'未跟踪',properties:'属性修改'}[f.status]||f.status)
 const groupCount=id=>(repoStatus.value?.files||[]).filter(f=>(f.group||'default')===id).length
 const envName=id=>environments.value.find(e=>e.id===id)?.name||'继承配置 / 类型默认环境'
 function setStore(store){environments.value=store.environments||[];defaults.value=store.environment_defaults||{};buildSettings.value=store.build_tools||{}}
 async function detectEnvironments(){await act(async()=>{const d=await api('environments.detect',project.value?{project:project.value.id}:{});candidates.value=d.candidates;envWarnings.value=d.warnings;notice.value=`检测到 ${d.candidates.length} 个可用环境；未安装或更改任何系统软件。`})}
 async function addDetected(e,makeDefault=false){await act(async()=>{await api('environments.save',{kind:e.kind,path:e.program,name:e.name,default:makeDefault});await refresh();notice.value='运行环境已验证并添加，可以在配置和实例中下拉选择。'})}
 function environmentForm(e){envDraft.value=e?{...e,path:e.program,default:defaults.value[e.kind]===e.id}:{id:'',name:'',kind:'java',path:'',default:false};modal.value='environment'}
 async function pickEnvironment(kind){await act(async()=>{const result=await api('fs.pick',{kind});if(result.path)envDraft.value.path=result.path})}
 async function saveEnvironment(){await act(async()=>{await api('environments.save',envDraft.value);await refresh();modal.value='';notice.value='环境已保存；不会改动系统 JAVA_HOME、PATH 或项目源代码。'})}
 async function useDefault(e){await addDetected(e,true)}
 function removeEnvironment(e){envDraft.value={...e};modal.value='removeEnvironment'}
 async function confirmRemoveEnvironment(){await act(async()=>{await api('environments.remove',{id:envDraft.value.id,confirmed:true});await refresh();modal.value='';notice.value='已移除 No-ide 中的环境登记，未删除安装文件。'})}
 async function ensureKind(kind){
  if(environments.value.some(e=>e.kind===kind))return
  const d=await api('environments.detect',project.value?{project:project.value.id}:{});candidates.value=d.candidates;envWarnings.value=d.warnings
  for(const e of d.candidates.filter(e=>e.kind===kind).slice(0,12))await api('environments.save',{kind:e.kind,path:e.program,name:e.name})
  await refresh()
 }
 function applyEntry(index){
  const e=discovery.value?.entries?.[Number(index)];if(!e)return
  selectedEntry.value=Number(index);commandPreview.value=null;commandError.value='';const existingId=form.value.id||'';const existingName=form.value.name
  const args=e.kind==='npm-script'&&e.suggested_port?['--host','127.0.0.1','--port','{port}']:['spring-maven','gradle-task'].includes(e.kind)&&e.suggested_port?['--server.port={port}']:[]
  form.value={id:existingId,name:existingId?existingName:e.name,cwd:e.cwd,environment_id:defaults.value[e.environment_kind]||'',launcher:{kind:e.kind,target:e.target,sources:e.sources},argumentRows:asRows(args),vmRows:[],propertyRows:[],envRows:[],profileRows:[],watchRows:[],suggested_port:e.suggested_port}
  if(['java-main','node-file','python-file','spring-maven'].includes(e.kind)){
   const src=(e.cwd==='.'?'':e.cwd+'/')+'src'
   const paths=discovery.value.directories.includes(src)?[src]:['python-file','node-file'].includes(e.kind)?[(e.cwd==='.'?'':e.cwd+'/')+e.target]:e.kind==='java-main'?e.sources:[]
   form.value.watchRows=asRows(paths.slice(0,8))
  }
  const draft=form.value;void act(async()=>{await ensureKind(e.environment_kind);if(modal.value==='configV4'&&form.value===draft&&!form.value.environment_id)form.value.environment_id=defaults.value[e.environment_kind]||''})
 }
 async function scanEntries(){
  if(!project.value)return;const serial=++epoch,pid=project.value.id;scanning.value=true
  try{const d=await api('project.discover',{project:pid,directory:scanRoot.value});if(serial!==epoch||project.value?.id!==pid)return;discovery.value=d;if(!form.value.launcher&&d.entries.length)applyEntry(0)}finally{if(serial===epoch)scanning.value=false}
 }
 function configForm(c){
  if(c&&!c.launcher){oldConfigForm(c);return}
  commandPreview.value=null;commandError.value='';selectedEntry.value=-1;scanRoot.value='.';discovery.value=null
  form.value=c?{id:c.id,name:c.name,cwd:c.cwd,environment_id:c.environment_id||'',launcher:{...c.launcher},argumentRows:asRows(c.launcher.arguments),vmRows:asRows(c.launcher.vm_options),propertyRows:asRows(c.launcher.properties),envRows:asRows(c.env),profileRows:asRows(c.launcher.profiles),watchRows:asRows(c.watch)}:{id:'',name:'',cwd:'.',environment_id:'',launcher:null,argumentRows:[],vmRows:[],propertyRows:[],envRows:[],profileRows:[],watchRows:[]}
  modal.value='configV4';void act(scanEntries)
 }
 async function browseScan(){await act(async()=>{const p=(await api('fs.pick',{kind:'folder',directory:project.value.root})).path;if(!p)return;scanRoot.value=(await api('project.relative',{project:project.value.id,path:p})).path;await scanEntries()})}
 async function chooseWorkingDir(){await act(async()=>{const p=(await api('fs.pick',{kind:'folder',directory:project.value.root})).path;if(p)form.value.cwd=(await api('project.relative',{project:project.value.id,path:p})).path})}
 async function chooseEntryFile(){await act(async()=>{const path=(await api('fs.pick',{kind:'file',directory:project.value.root})).path;if(!path)return;const rel=(await api('project.relative',{project:project.value.id,path})).path;const ext=rel.split('.').pop().toLowerCase();let kind={py:'python-file',js:'node-file',mjs:'node-file',cjs:'node-file',jar:'java-jar'}[ext];
  if(ext==='java'){scanRoot.value=rel.includes('/')?rel.slice(0,rel.lastIndexOf('/')):'.';await scanEntries();return}
  if(!kind)throw Error('请选择 Java、JAR、Node.js 或 Python 入口；package.json / pom.xml 请使用“选择模块目录”。')
  const cwd=rel.includes('/')?rel.slice(0,rel.lastIndexOf('/')):'.',target=rel.split('/').pop(),e={name:target,kind,cwd,target,sources:[],environment_kind:kindOf(kind),description:'手动选择的实际文件',suggested_port:null};discovery.value=discovery.value||{entries:[],directories:['.'],warnings:[]};discovery.value.entries.push(e);applyEntry(discovery.value.entries.length-1)
 })}
 function serializeConfig(){const f=form.value;if(!f.launcher)throw Error('请先选择识别出的运行入口，或点“选择入口文件”。');return{id:f.id||'',name:f.name,cwd:f.cwd,environment_id:f.environment_id||null,command:{program:'auto',args:[]},watch:argv(f.watchRows),env:pairs(f.envRows),launcher:{...f.launcher,arguments:argv(f.argumentRows),vm_options:argv(f.vmRows),properties:pairs(f.propertyRows),profiles:argv(f.profileRows)}}}
 async function previewCommand(){commandPreview.value=null;commandError.value='';await act(async()=>{try{commandPreview.value=await api('launch.preview',{project:project.value.id,config:serializeConfig()})}catch(e){commandError.value=e.message||String(e)}})}
 async function detectBuildTools(){
  if(buildDetecting.value)return
  buildDetecting.value=true;buildDetectError.value=''
  try{buildReports.value=await api('build_tools.detect')}catch(e){buildDetectError.value=e.message||String(e)}finally{buildDetecting.value=false}
 }
 async function saveBuildTool(kind,path){await act(async()=>{await api('build_tools.save',{kind,path});await refresh();await detectBuildTools();notice.value='构建工具配置已保存；不修改系统 PATH，也不重新创建项目。'})}
 async function pickBuildTool(kind){await act(async()=>{const path=(await api('fs.pick',{kind:kind==='maven_settings'?'file':'folder'})).path;if(path){await api('build_tools.save',{kind,path});await refresh();await detectBuildTools();notice.value='已记住所选位置，项目可直接使用。'}})}
 async function pickConfigBuildTool(){await act(async()=>{const p=(await api('fs.pick',{kind:'folder'})).path;if(p)form.value.launcher.build_tool_path=p});await previewCommand()}
 function configEnvironment(c){if(!c.launcher)return '高级命令指定';const k=kindOf(c.launcher.kind);const id=c.environment_id||defaults.value[k];const e=environments.value.find(e=>e.id===id);return e?e.name+' · '+e.version:'未选择 '+kindLabel(k)+' 环境'}
 function configBuild(c){const k=c.launcher?.kind;if(['spring-maven','maven-main'].includes(k))return c.launcher.build_tool_path||'Maven · 自动（项目包装器优先）';if(k==='gradle-task')return c.launcher.build_tool_path||'Gradle · 自动（项目包装器优先）';return c.build?.program||'使用入口对应方式'}
 function configInstances(c){return project.value?.instances.filter(i=>i.config_id===c.id)||[]}
 function cloneConfig(c){configForm(JSON.parse(JSON.stringify({...c,id:'',name:c.name+' 副本'})))}
 function addConfigInstance(c){instanceForm();form.value.config_id=c.id}
 watch(page,p=>{if(p==='environments')void detectBuildTools()})

 async function saveVisualConfig(){await act(async()=>{const wasExisting=!!form.value.id;let c;try{c=await api('config.save',{project:project.value.id,config:serializeConfig()})}catch(e){commandError.value=e.message||String(e);return}const port=form.value.suggested_port;await refresh();modal.value='';notice.value='已保存自动运行配置。参数、属性和环境选择会实际传入进程。';if(!wasExisting&&!project.value.instances.some(i=>i.config_id===c.id)){instanceForm();form.value.config_id=c.id;form.value.port=port||null}})}
 function advancedConfig(){const c=project.value?.configs.find(c=>c.id===form.value.id);oldConfigForm(c&&!c.launcher?c:null);notice.value='高级自定义使用原始程序和参数；通常直接选择自动发现的入口即可。'}
 function instanceForm(i){if(!project.value?.configs.length){configForm();return}oldInstanceForm(i);form.value.environment_id=i?.environment_id||'';form.value.argumentRows=asRows(i?.args||[]);form.value.envRows=asRows(i?.env||{})}
 function cloneInstance(i){instanceForm({...i,id:'',name:i.name+' 副本',port:i.port?i.port+1:null})}
 async function saveVisualInstance(){await act(async()=>{const f=form.value;await api('instance.save',{project:project.value.id,instance:{id:f.id||'',name:f.name,config_id:f.config_id,port:f.port?Number(f.port):null,environment_id:f.environment_id||null,args:argv(f.argumentRows),env:pairs(f.envRows)}});await refresh();modal.value='';notice.value='实例已保存。运行环境可继承配置，也可独立选择。'})}
 watch(repoId,()=>{activeGroup.value='default';moveTarget.value='';selectedFiles.value=[];anchor.value='';fileFilter.value=''})
 watch(activeGroup,()=>{selectedFiles.value=[];anchor.value='';fileFilter.value='';file.value='';diff.value=''})
 watch(repoStatus,()=>{if(!groups.value.some(g=>g.id===activeGroup.value))activeGroup.value='default';selectedFiles.value=selectedFiles.value.filter(p=>groupFiles.value.some(f=>f.path===p))})
 function cacheKey(){return `${project.value?.id}/${repoId.value}`}
 function applyGroups(g,key=cacheKey()){
  const old=groupCache.get(key);if(old&&old.revision>g.revision)g=old;else{groupCache.set(key,g);if(groupCache.size>8)groupCache.delete(groupCache.keys().next().value)}
  if(key!==cacheKey())return
  if(repo.value)repo.value.groups=g
  if(repoStatus.value){repoStatus.value.groups=g.items;repoStatus.value.group_meta=g;repoStatus.value.files=repoStatus.value.files.map(f=>({...f,group:fileGroup(g,f.path,f.original)}))}
 }
 watch(repoStatus,d=>{if(d?.group_meta)applyGroups(d.group_meta)})
 function groupForm(g){groupDraft.value=g?{...g}:{id:'',name:''};modal.value='changeGroup'}
 async function saveGroup(){await act(async()=>{const key=cacheKey();const g=await api('vcs.group.save',{project:project.value.id,repo:repoId.value,group:groupDraft.value.id,name:groupDraft.value.name});applyGroups(g,key);modal.value='';notice.value='分组已保存，无需重新扫描仓库。'})}
 function deleteGroup(g){groupDraft.value={...g};modal.value='deleteGroup'}
 async function confirmDeleteGroup(){await act(async()=>{const key=cacheKey();const g=await api('vcs.group.delete',{project:project.value.id,repo:repoId.value,group:groupDraft.value.id,confirmed:true});applyGroups(g,key);activeGroup.value='default';modal.value='';notice.value='已删除分组，归属回到默认；没有删除源文件。'})}
 async function moveFiles(group,paths=selectedFiles.value){
  if(!group||!paths.length||groupSaving.value)return
  const selected=[...paths],key=cacheKey(),pid=project.value.id,rid=repoId.value
  const originals=(repoStatus.value?.files||[]).filter(f=>selected.includes(f.path)&&f.original).map(f=>f.original)
  const move=[...new Set([...selected,...originals])];groupSaving.value=true
  try{await act(async()=>{const g=await api('vcs.group.move',{project:pid,repo:rid,group,paths:move,revision:repoStatus.value?.group_meta?.revision});applyGroups(g,key);if(key===cacheKey()){selectedFiles.value=selectedFiles.value.filter(p=>!move.includes(p));moveTarget.value='';notice.value=`已将 ${selected.length} 项移入分组。只保存本机归属，没有运行 Git / SVN，也没有提交代码。`;}})}finally{groupSaving.value=false}
 }
 function toggleFile(event,f){const result=toggleRows(visibleGroupFiles.value.map(x=>x.path),selectedFiles.value,anchor.value,f.path,event.shiftKey);selectedFiles.value=result.selected;anchor.value=result.anchor;if(!event.shiftKey&&result.selected.includes(f.path))void selectFile(f)}
 function startDrag(event,path){if(!selectedSet.value.has(path))selectedFiles.value=[path];dragFiles.value=[...selectedFiles.value];event.dataTransfer.setData('text/plain',JSON.stringify(dragFiles.value));event.dataTransfer.effectAllowed='move'}
 function dropGroup(event,id){event.preventDefault();const paths=dragFiles.value.filter(p=>repoStatus.value?.files.some(f=>f.path===p));dragFiles.value=[];if(paths.length)void moveFiles(id,paths)}
 function selectGroupAll(force=false){selectedFiles.value=selectVisible(visibleGroupFiles.value.map(f=>f.path),selectedFiles.value,force===true||!allVisibleSelected.value?'all':'none')}
 function invertSelection(){selectedFiles.value=selectVisible(visibleGroupFiles.value.map(f=>f.path),selectedFiles.value,'invert')}
 async function prepareGroup(operation,wholeGroup=false){await act(async()=>{
  const scoped=['stage','unstage','commit','add'].includes(operation);const paths=scoped?(wholeGroup?[...groupFiles.value.map(f=>f.path)]:[...selectedFiles.value]):[];
  if(scoped&&!paths.length)throw Error('请先勾选文件；点整行、全选或 Shift 连选都可以。')
  plan.value=await api('vcs.prepare',{project:project.value.id,repo:repoId.value,operation,paths,message:message.value,...(scoped?{group:activeGroup.value}:{}),whole_files:operation==='commit'});modal.value='confirm'
 })}
 return{buildDetecting,buildDetectError,buildSettings,buildReports,buildKind,commandError,detectBuildTools,saveBuildTool,pickBuildTool,pickConfigBuildTool,configEnvironment,configBuild,configInstances,cloneConfig,addConfigInstance,fileFilter,groupSaving,selectedSet,visibleGroupFiles,allVisibleSelected,changeStatus,toggleFile,invertSelection,environments,defaults,candidates,envWarnings,envDraft,discovery,scanning,scanRoot,selectedEntry,commandPreview,configType,currentKind,matchingEnvs,instanceKind,instanceEnvs,kindLabel,kindOf,envName,setStore,detectEnvironments,addDetected,environmentForm,pickEnvironment,saveEnvironment,useDefault,removeEnvironment,confirmRemoveEnvironment,ensureKind,applyEntry,scanEntries,configForm,browseScan,chooseWorkingDir,chooseEntryFile,previewCommand,saveVisualConfig,advancedConfig,instanceForm,cloneInstance,saveVisualInstance,activeGroup,moveTarget,groupDraft,groups,groupName,groupFiles,groupCount,groupForm,saveGroup,deleteGroup,confirmDeleteGroup,moveFiles,startDrag,dropGroup,selectGroupAll,prepare:prepareGroup}
}
