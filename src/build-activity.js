import { computed, ref, watch, onUnmounted } from 'vue'
import { activeActivity, phaseLabel, elapsedText } from './activity-model.js'
import './build-activity.css'
export const BuildActivity = {
  props: { task:Object, pending:Object, connected:Boolean, project:Object },
  emits: ['cancel','restart'],
  setup(props) {
    const now=ref(Date.now());let clock
    const active=computed(()=>activeActivity(props.task))
    const duration=computed(()=>props.task?elapsedText(props.task,now.value):'')
    const names=computed(()=>props.task?.instances.map(id=>props.project?.instances.find(i=>i.id===id)?.name||id).join('、'))
    const steps=[['checking','检查改动'],['building','构建与复核'],['applying','应用 / 启动'],['finished','结果']]
    const phaseIndex=computed(()=>({queued:0,model:0,checking:0,building:1,verifying:1,applying:2,restarting:2,waiting:2,finished:3}[props.task?.phase]??0))
    watch(()=>active.value&&props.connected,v=>{clearInterval(clock);now.value=Date.now();if(v)clock=setInterval(()=>now.value=Date.now(),1000)},{immediate:true})
    onUnmounted(()=>clearInterval(clock))
    return {active,duration,names,steps,phaseIndex,phaseLabel}
  },
  template:`<section v-if="task||pending" :class="['build-activity',task?.status||'pending',{'connection-lost':!connected}]" :data-task-id="task?.id" :data-phase="task?.phase" :data-status="task?.status" aria-label="本次更新任务">
    <div class="build-activity-heading"><span :class="['task-symbol',{spinning:active&&connected&&task?.status!=='cancelling'}]" aria-hidden="true">{{!connected?'!':active?'◌':task?.status==='succeeded'?'✓':task?.status==='failed'?'!':task?.status==='restart-required'?'!':'—'}}</span>
      <div class="task-summary" role="status" aria-live="polite" aria-atomic="true"><strong>{{!connected?'连接中断，任务状态待确认':pending&&!active?'正在发送请求…':task?.message}}</strong><span>{{pending&&!active?'这只表示请求发送中，尚未确认构建开始。':active?phaseLabel(task?.phase):task?.finished_at?'完成于 '+new Date(task.finished_at).toLocaleTimeString():'等待执行器反馈'}}</span></div>
      <span class="task-duration" v-if="task">{{active?'已用时':'耗时'}} {{duration}}</span>
    </div>
    <div v-if="task" class="task-stages" aria-label="阶段，不代表百分比"><span v-for="(step,index) in steps" :key="step[0]" :class="{current:index===phaseIndex}">{{index+1}} {{step[1]}}</span></div>
    <div class="task-scope" v-if="task"><span>影响实例：{{names}}</span><span v-if="task.build_mode">本次重编 <b>{{task.selected.length}}</b> 个 · 复用 <b>{{task.reused.length}}</b> 个</span></div>
    <div v-if="task?.status==='restart-required'" class="task-not-applied"><b>现在还不能验证全部新改动。</b> 需要重启才能完整生效，没有自动重启。</div>
    <details v-if="task?.detail||task?.selected.length||task?.reused.length" class="task-details"><summary>查看构建范围 / 原因</summary><p>{{task.detail}}</p><p v-if="task.selected.length">重编：{{task.selected.join('、')}}</p><p v-if="task.reused.length">复用：{{task.reused.join('、')}}</p></details>
    <footer class="task-footer"><span>{{!connected?'重新连接后会读取后台真实状态，未假定成功或停止。':active&&task?.cancellable?'取消只终止本次构建，不停止原有实例；同配置实例共享此构建。':active?'构建已结束，正在应用 / 启动；此阶段不提供暂停或回滚。':'结果会保留在这里，不会一闪而过。'}}</span><button v-if="task?.cancellable||task?.status==='cancelling'" class="task-cancel" :disabled="!connected||task.status==='cancelling'||pending" @click="$emit('cancel',task)">{{task.status==='cancelling'?'正在取消…':'取消本次构建'}}</button><button v-if="task?.status==='restart-required'" class="task-restart" :disabled="!connected||pending" @click="$emit('restart')">重启此实例以生效</button></footer>
  </section>`
}
