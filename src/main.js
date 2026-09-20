import { createApp } from 'vue'
import { Quasar, QBtn, QToggle } from 'quasar'
import 'quasar/dist/quasar.prod.css'
import './styles.css'
import './quasar-overrides.css'
import './projects.css'
import './source-control.css'
import { createNoIdeApp } from './app.js'

async function boot() {
  let health = null
  if (['127.0.0.1', 'localhost'].includes(location.hostname)) {
    try {
      const response = await fetch('/api/health', { signal: AbortSignal.timeout(1800) })
      if (response.ok && response.headers.get('content-type')?.includes('application/json')) {
        const data = await response.json()
        if (data.name === 'no-ide') health = data
      }
    } catch { /* Static preview / Vite has no native backend. */ }
  }
  let component
  if (health) {
    // Import failures must not silently replace real operations with mock data.
    const { createLiveWorkbench } = await import('./live-workbench.js')
    await import('./live.css')
    component = createLiveWorkbench(health)
  } else {
    component = createNoIdeApp()
  }
  createApp(component).use(Quasar, {
    components: { QBtn, QToggle },
    config: { brand: { primary: '#dc4d86', positive: '#27896d', negative: '#d34d65' } }
  }).mount('#app')
  document.documentElement.lang = 'zh-CN'
}
boot().catch(error => {
  document.getElementById('app').textContent = '本地操作台加载失败，请重新解压完整运行包。' + error.message
})
