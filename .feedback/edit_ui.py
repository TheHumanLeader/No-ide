from pathlib import Path
root=Path.cwd()
p=root/'src/live-workbench.js';s=p.read_text()
s="import { activeActivity, mergeActivities, phaseLabel } from './activity-model.js'\n"+s
s=s.replace("const connected=ref(false)", "const activities=ref({}), pendingRuns=ref({})\n   const connected=ref(false)",1)
pos=s.index('   async function refresh()')
s=s[:pos]+'''   const taskFor=i=>activities.value[i.config_id]
   const updateBusy=i=>!!pendingRuns.value[i.config_id]||activeActivity(taskFor(i))
   const updateText=i=>pendingRuns.value[i.config_id]&&!activeActivity(taskFor(i))?'提交中…':activeActivity(taskFor(i))?phaseLabel(taskFor(i).phase)+'…':'应用改动'
   const activeTaskCount=computed(()=>Object.values(activities.value).filter(activeActivity).length)
   function receiveTasks(tasks,announce=false){activities.value=mergeActivities(activities.value,tasks);if(announce){for(const task of tasks){if(task.finished_at&&task.project===project.value?.id)notice.value=task.message}}}
''' +s[pos:]
s=s.replace('projects.value=d.store.projects;', 'receiveTasks(d.activities||[]);projects.value=d.store.projects;',1)
s=s.replace("if(m.type==='snapshot'){runs.value", "if(m.type==='activity')receiveTasks([m.data],true)\n     if(m.type==='snapshot'){activities.value=mergeActivities({},m.activities||[]);runs.value",1)
a=s.index('   async function run(i,op)');b=s.index('   async function runAll',a)
s=s[:a]+'''   async function run(i,op,extra={}){
    if(!connected.value){error.value='执行器未连接，无法确认或操作任务。';return}
    if(op!=='stop'&&op!=='cancel'&&updateBusy(i)){error.value='这份配置已有任务，请查看进度；没有重复排队。';return}
    const pid=project.value.id,key=i.config_id
    pendingRuns.value={...pendingRuns.value,[key]:{kind:op,since:Date.now()}}
    await act(async()=>{try{await api('run.'+op,{project:pid,instance:i.id,...extra});await refresh()}finally{const copy={...pendingRuns.value};delete copy[key];pendingRuns.value=copy}})
   }
   async function cancelBuild(i,task){await run(i,'cancel',{task_id:task.id})}
''' +s[b:]
s=s.replace('return {diffBusy,diffError,health,', 'return {activities,pendingRuns,taskFor,updateBusy,updateText,activeTaskCount,cancelBuild,api,diffBusy,diffError,health,',1)
p.write_text(s)
p=root/'src/incremental-workbench.js';s=p.read_text();s="import { BuildActivity } from './build-activity.js'\n"+s
start=s.index('  const newButton = ');end=s.index('\n  if (base.template',start)
s=s[:start]+'''  const newButton = `<button class="text-button task-apply" :disabled="!connected||updateBusy(i)||runs[i.id]?.state!=='running'" @click="run(i,'apply')" title="检查改动 → 增量构建 → 应用；进度和结果显示在下方">{{updateText(i)}}</button><button class="text-button" :disabled="!connected||updateBusy(i)||runs[i.id]?.state!=='running'" @click="run(i,'restart')" title="检查当前源码后，仅重启此实例；不默认清理">重启实例</button><button class="text-button" :disabled="!connected||updateBusy(i)||runs[i.id]?.state!=='running'" @click="repairBuild(i)" title="完整清理所需模块，较慢；不用于日常验证">清理重建</button>`
''' +s[end:]
s=s.replace('    ...base,\n    template:', '    ...base,\n    components: {...base.components, BuildActivity},\n    template:',1)
s=s.replace('.replace(\'· 运行次数 \',', '''.replace('<button class="text-button" @click="instanceForm(i)">实例设置</button></div></div>', '<button class="text-button" @click="instanceForm(i)">实例设置</button></div><build-activity :task="taskFor(i)" :pending="pendingRuns[i.config_id]" :connected="connected" :project="project" @cancel="cancelBuild(i,$event)" @restart="run(i,\\'restart\\')" /></div>')
      .replace(`@click="run(i,'stop')">停止</q-btn>`, `@click="run(i,'stop')" title="停止此实例；有共享构建时也会取消该构建，其他实例不停止">停止实例</q-btn>`)
      .replace(`<span>{{busy?'正在处理…':'仅本机访问'}}</span>`, `<span class="task-global-count" v-if="activeTaskCount">{{connected?'更新任务进行中':'任务状态待确认'}} · {{activeTaskCount}}</span><span v-else>{{busy?'正在处理请求…':'仅本机访问'}}</span>`)
      .replace('· 运行次数 ',''',1)
start=s.index('      const repairBuild = async instance => {');end=s.index('\n      return { ...state, repairBuild }',start)
s=s[:start]+'''      const repairBuild = async instance => {
        if (!window.confirm('清理所需模块并完整重建，可能较慢。日常验证请用“应用改动”。继续吗？')) return
        await state.run(instance,'repair',{confirmed:true})
      }
''' +s[end:]
p.write_text(s)
p=root/'src/runtime-logs.js';s=p.read_text()
s=s.replace("{{paused?'继续展示':'暂停展示'}}", "{{paused?'继续日志显示':'暂停日志显示'}}")
s=s.replace('@click="pause">', '@click="pause" title="只冻结日志面板；不暂停构建，也不停止实例">')
s=s.replace('<div class="live-log-search">', '<div class="live-log-pause-note">{{paused?\'日志显示已暂停；构建、任务进度和实例仍继续运行。\':\'暂停日志显示只冻结此面板，不影响构建和实例。\'}}</div>\n  <div class="live-log-search">',1)
s=s.replace('@change="$event.target.checked?resume():disableFollow()"', '@click.stop="autoScroll?disableFollow():resume()"')
p.write_text(s)
for p in (root/'tests').glob('*.py'):
 s=p.read_text().replace("name='暂停展示'", "name='暂停日志显示'").replace("name='继续展示'", "name='继续日志显示'")
 s=s.replace("report['backend_version']=n.api('state').get('version','0.4.2 (reused release)')", "report['backend_version']=__import__('urllib.request',fromlist=['urlopen']).urlopen(n.base+'/health').read().decode()")
 s=s.replace("name='停止',exact=True", "name='停止实例',exact=True")
 p.write_text(s)
