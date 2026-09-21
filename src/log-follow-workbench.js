import { createLiveWorkbench as createBaseWorkbench } from './live-workbench.js'
import { RuntimeLogs } from './runtime-logs.js'

// The hotfix replaces only the native log region. All project, configuration,
// execution and SCM actions remain those of the verified v0.4.2 workbench.
// Fail explicitly if a future layout changes the region instead of rendering
// a preview fallback or silently leaving the old non-following panel in place.
export function createLiveWorkbench(health) {
  const base = createBaseWorkbench(health)
  const marker = '<section class="panel live-log-panel">'
  const start = base.template.indexOf(marker)
  const end = base.template.indexOf('</section>', start)
  if (start < 0 || end < start || base.template.indexOf(marker, start + marker.length) !== -1) {
    throw new Error('日志组件挂载位置不匹配，请使用完整的同版本前端文件。')
  }
  return {
    ...base,
    components: { ...base.components, RuntimeLogs },
    template: base.template.slice(0, start)
      + '<runtime-logs :logs="logs" :project="project" :label="label" @copy="copyRuntimeLogs" />'
      + base.template.slice(end + '</section>'.length),
    setup(...args) {
      const state = base.setup(...args)
      const copyRuntimeLogs = text => state.act(async () => {
        await navigator.clipboard.writeText(text)
        state.notice.value = '已复制当前可见日志；分享前请检查是否含敏感信息。'
      })
      return { ...state, copyRuntimeLogs }
    }
  }
}
