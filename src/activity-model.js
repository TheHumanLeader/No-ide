export const activeActivity = task => !!task && ['queued', 'running', 'cancelling'].includes(task.status)
export const phaseLabel = phase => ({queued:'排队中',checking:'检查中',model:'解析模块中',building:'构建中',verifying:'复核中',applying:'应用中',restarting:'重启中',waiting:'等待就绪',finished:'已结束'}[phase] || '处理中')
export function mergeActivities(current, incoming = []) {
  let next = current
  for (const task of incoming) {
    if (!task?.config || !task.id) continue
    const old = next[task.config]
    if (old && (old.id === task.id ? old.revision >= task.revision : old.started_at > task.started_at)) continue
    if (next === current) next = {...current}
    next[task.config] = task
  }
  return next
}
export const elapsedText = (task, now) => {
  const seconds = Math.max(0, Math.floor(((task.finished_at ?? now) - task.started_at) / 1000))
  return seconds < 60 ? `${seconds} 秒` : `${Math.floor(seconds / 60)} 分 ${seconds % 60} 秒`
}
