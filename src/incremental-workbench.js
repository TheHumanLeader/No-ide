import './hot.css'
import hotOptions from './hot-options.html?raw'
import { createLiveWorkbench as createBase } from './log-follow-workbench.js'

// Native-only composition: keep existing SCM/runtime actions, separate repair
// from the everyday incremental operation. Never fall back to mock responses.
export function createLiveWorkbench(health) {
  let token = new URLSearchParams(location.hash.slice(1)).get('token') || ''
  if (!token) { try { token = sessionStorage.getItem('no-ide.native.token') || '' } catch {} }
  const base = createBase(health)
  const oldButton = `<button class="text-button" :disabled="!['running','building'].includes(runs[i.id]?.state)" @click="run(i,'update')" title="同配置的运行实例一起更新">重新构建</button>`
  const newButton = `<button class="text-button" :disabled="!['running','building'].includes(runs[i.id]?.state)" @click="run(i,'apply')" title="增量构建后应用；热替换模式不自动重启">应用改动</button><button class="text-button" :disabled="!['running','building'].includes(runs[i.id]?.state)" @click="run(i,'restart')" title="检查当前源码后，仅重启此实例；不默认清理">重启实例</button><button class="text-button" :disabled="!['running','building'].includes(runs[i.id]?.state)" @click="repairBuild(i)" title="完整清理所需模块，较慢；不用于日常验证">清理重建</button>`
  if (base.template.split(oldButton).length !== 2) throw Error('增量构建按钮布局不匹配，请使用完整同版本前端。')
  return {
    ...base,
    template: base.template.replace(oldButton, newButton)
      .replace('· 运行次数 ', '· 版本 ')
      .replace(`<section v-if="buildKind==='maven'" class="config-build-tool maven-workspace-options">`, hotOptions + `<section v-if="buildKind==='maven'" class="config-build-tool maven-workspace-options">`)
      .replace('<pre v-if="commandPreview">', `<p v-if="form.launcher.update_mode==='hotswap'">热替换运行：所选 Java → 内置 Agent → 私有工作区类路径 → 编译后的主类。私有路径在构建成功后生成；下方 Maven 命令仅用于构建。</p><pre v-if="commandPreview && form.launcher.update_mode!=='hotswap'">`).replace('<p v-if="runs[i.id]?.error"', '<p v-if="runs[i.id]?.update_status===\'restart-required\'" class="hot-pending" role="status">需重启：{{ runs[i.id].pending_reason }}（没有自动重启）</p><p v-if="runs[i.id]?.error"').replace(
      '停止后首次启动和“重新构建”会清理旧产物；普通文件修改走增量构建，删除文件时重新清理。',
      '首次建立可信基线后，只重编有变化及受影响的模块。未变模块复用，停止或退出后也会记住。删除类和资源会清理对应受影响模块；完整清理重建是独立修复操作。下方预览为完整基线命令，日常实际构建范围在日志中显示。'
    ),
    setup(...args) {
      const state = base.setup(...args)
      const repairBuild = async instance => {
        if (!window.confirm('清理所需模块并完整重建，可能较慢。日常验证请用“应用改动”。继续吗？')) return
        await state.act(async () => {
          if (!token) throw Error('本机会话已失效，请重新从执行器打开工作台。')
          const response = await fetch('/api/call', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
            body: JSON.stringify({ action: 'run.repair', params: { project: state.project.value.id, instance: instance.id, confirmed: true } })
          })
          const data = await response.json()
          if (!response.ok) throw Error(data.error || '未能启动清理重建。')
          state.notice.value = '已确认清理重建；不会删除源码或清空 Maven 仓库。'
          await state.refresh()
        })
      }
      return { ...state, repairBuild }
    }
  }
}
