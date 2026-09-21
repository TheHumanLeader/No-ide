import {ref,computed,watch} from 'vue'
import {asRows,argv,pairs} from './visual-controls.js'
export function useWorkbenchV04(ctx){
 const {api,act,refresh,project,repo,repoId,repoStatus,selectedFiles,file,diff,modal,form,page,notice,message,plan,loadRepo,oldConfigForm,oldInstanceForm}=ctx
 const environments=ref([]),defaults=ref({}),candidates=ref([]),envWarnings=ref([]),envDraft=ref({}),discovery=ref(null),scanning=ref(false),scanRoot=ref('.'),selectedEntry=ref(-1),commandPreview=ref(null),configType=ref('auto')
 const activeGroup=ref('default'),moveTarget=ref(''),groupDraft=ref({}),dragFiles=ref([])
 let epoch=0
 const kindLabel=k=>({java:'Java',node:'Node.js',python:'Python'}[k]||k)
 const kindOf=k=>['npm-script','node-file'].includes(k)?'node':k==='python-file'?'python':'java'
 const currentKind=computed(()=>form.value.launcher?kindOf(form.value.launcher.kind):null)
 const matchingEnvs=computed(()=>environments.value.filter(e=>e.kind===currentKind.value))
 const instanceKind=computed(()=>{const c=project.value?.configs.find(c=>c.id===form.value.config_id);return c?.launcher?kindOf(c.launcher.kind):null})
 const instanceEnvs=computed(()=>environments.value.filter(e=>e.kind===instanceKind.value))
 const groups=computed(()=>repoStatus.value?.groups||[{id:'default',name:'默认'}])
 const groupName=computed(()=>groups.value.find(g=>g.id===activeGroup.value)?.name||'默认')
 const groupFiles=computed(()=>(repoStatus.value?.files||[]).filter(f=>(f.group||'default')===activeGroup.value))
 const groupCount=id=>(repoStatus.value?.files||[]).filter(f=>(f.group||'default')===id).length
 const envName=id=>environments.value.find(e=>e.id===id)?.name||'继承配置 / 类型默认环境'
 function setStore(store){environments.value=store.environments||[];defaults.value=store.environment_defaults||{}}
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
  selectedEntry.value=Number(index);commandPreview.value=null
  const args=e.kind==='npm-script'&&e.suggested_port?['--host','127.0.0.1','--port','{port}']:['spring-maven','gradle-task'].includes(e.kind)&&e.suggested_port?['--server.port={port}']:[]
  form.value={id:'',name:e.name,cwd:e.cwd,environment_id:defaults.value[e.environment_kind]||'',launcher:{kind:e.kind,target:e.target,sources:e.sources},argumentRows:asRows(args),vmRows:[],propertyRows:[],envRows:[],profileRows:[],watchRows:[],suggested_port:e.suggested_port}
  if(['java-main','node-file','python-file','spring-maven'].includes(e.kind)){
   const src=(e.cwd==='.'?'':e.cwd+'/')+'src'
   const paths=discovery.value.directories.includes(src)?[src]:['python-file','node-file'].includes(e.kind)?[(e.cwd==='.'?'':e.cwd+'/')+e.target]:e.kind==='java-main'?e.sources:[]
   form.value.watchRows=asRows(paths.slice(0,8))
  }
  const draft=form.value;void act(async()=>{await ensureKind(e.environment_kind);if(modal.value==='configV4'&&form.value===draft&&!form.value.environment_id)form.value.environment_id=defaults.value[e.environment_kind]||''})
 }
 async function scanEntries(){
  if(!project.value)return;const serial=++epoch,pid=project.value.id;scanning.value=true
  try{const d=await api('project.discover',{project:pid,directory:scanRoot.value});if(serial!==epoch||project.value?.id!==pid)return;discovery.value=d;if(!form.value.id&&d.entries.length)applyEntry(0)}finally{if(serial===epoch)scanning.value=false}
 }
 function configForm(c){
  if(c&&!c.launcher){oldConfigForm(c);return}
  commandPreview.value=null;selectedEntry.value=-1;scanRoot.value='.';discovery.value=null
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
 async function previewCommand(){await act(async()=>{commandPreview.value=await api('launch.preview',{project:project.value.id,config:serializeConfig()})})}
 async function saveVisualConfig(){await act(async()=>{const c=await api('config.save',{project:project.value.id,config:serializeConfig()});const port=form.value.suggested_port;await refresh();modal.value='';notice.value='已保存自动运行配置。参数、属性和环境选择会实际传入进程。';if(!project.value.instances.some(i=>i.config_id===c.id)){instanceForm();form.value.config_id=c.id;form.value.port=port||null}})}
 function advancedConfig(){const c=project.value?.configs.find(c=>c.id===form.value.id);oldConfigForm(c&&!c.launcher?c:null);notice.value='高级自定义使用原始程序和参数；通常直接选择自动发现的入口即可。'}
 function instanceForm(i){if(!project.value?.configs.length){configForm();return}oldInstanceForm(i);form.value.environment_id=i?.environment_id||'';form.value.argumentRows=asRows(i?.args||[]);form.value.envRows=asRows(i?.env||{})}
 function cloneInstance(i){instanceForm({...i,id:'',name:i.name+' 副本',port:i.port?i.port+1:null})}
 async function saveVisualInstance(){await act(async()=>{const f=form.value;await api('instance.save',{project:project.value.id,instance:{id:f.id||'',name:f.name,config_id:f.config_id,port:f.port?Number(f.port):null,environment_id:f.environment_id||null,args:argv(f.argumentRows),env:pairs(f.envRows)}});await refresh();modal.value='';notice.value='实例已保存。运行环境可继承配置，也可独立选择。'})}
 watch(repoId,()=>{activeGroup.value='default';moveTarget.value='';selectedFiles.value=[]})
 watch(activeGroup,()=>{selectedFiles.value=[];file.value='';diff.value=''})
 watch(repoStatus,()=>{if(!groups.value.some(g=>g.id===activeGroup.value))activeGroup.value='default';selectedFiles.value=selectedFiles.value.filter(p=>groupFiles.value.some(f=>f.path===p))})
 function groupForm(g){groupDraft.value=g?{...g}:{id:'',name:''};modal.value='changeGroup'}
 async function saveGroup(){await act(async()=>{await api('vcs.group.save',{project:project.value.id,repo:repoId.value,group:groupDraft.value.id,name:groupDraft.value.name});await refresh();await loadRepo();modal.value='';notice.value='分组已保存到本机；刷新、重启和提交后仍记忆文件归属。'})}
 function deleteGroup(g){groupDraft.value={...g};modal.value='deleteGroup'}
 async function confirmDeleteGroup(){await act(async()=>{await api('vcs.group.delete',{project:project.value.id,repo:repoId.value,group:groupDraft.value.id,confirmed:true});activeGroup.value='default';await refresh();await loadRepo();modal.value='';notice.value='分组已删除，归属文件回到“默认”。磁盘文件没有移动或删除。'})}
 async function moveFiles(group,paths=selectedFiles.value){if(!group||!paths.length)return;await act(async()=>{await api('vcs.group.move',{project:project.value.id,repo:repoId.value,group,paths:[...paths]});await refresh();await loadRepo();selectedFiles.value=[];moveTarget.value='';notice.value='文件分组已记住。只提交其他分组时，不会包含这些文件。'})}
 function startDrag(event,path){dragFiles.value=selectedFiles.value.includes(path)?[...selectedFiles.value]:[path];event.dataTransfer.setData('text/plain',JSON.stringify(dragFiles.value));event.dataTransfer.effectAllowed='move'}
 function dropGroup(event,id){event.preventDefault();const paths=dragFiles.value.filter(p=>repoStatus.value?.files.some(f=>f.path===p));dragFiles.value=[];if(paths.length)void moveFiles(id,paths)}
 function selectGroupAll(){selectedFiles.value=selectedFiles.value.length===groupFiles.value.length?[]:groupFiles.value.map(f=>f.path)}
 async function prepareGroup(operation){await act(async()=>{
  const scoped=['stage','unstage','commit','add'].includes(operation);const paths=scoped?(selectedFiles.value.length?[...selectedFiles.value]:groupFiles.value.map(f=>f.path)):[];
  plan.value=await api('vcs.prepare',{project:project.value.id,repo:repoId.value,operation,paths,message:message.value,...(scoped?{group:activeGroup.value}:{}),whole_files:operation==='commit'});modal.value='confirm'
 })}
 return{environments,defaults,candidates,envWarnings,envDraft,discovery,scanning,scanRoot,selectedEntry,commandPreview,configType,currentKind,matchingEnvs,instanceKind,instanceEnvs,kindLabel,kindOf,envName,setStore,detectEnvironments,addDetected,environmentForm,pickEnvironment,saveEnvironment,useDefault,removeEnvironment,confirmRemoveEnvironment,ensureKind,applyEntry,scanEntries,configForm,browseScan,chooseWorkingDir,chooseEntryFile,previewCommand,saveVisualConfig,advancedConfig,instanceForm,cloneInstance,saveVisualInstance,activeGroup,moveTarget,groupDraft,groups,groupName,groupFiles,groupCount,groupForm,saveGroup,deleteGroup,confirmDeleteGroup,moveFiles,startDrag,dropGroup,selectGroupAll,prepare:prepareGroup}
}
