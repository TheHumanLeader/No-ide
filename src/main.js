import { createApp } from 'vue'
import { Quasar, QBtn, QToggle } from 'quasar'
import 'quasar/dist/quasar.prod.css'
import './styles.css'
import './quasar-overrides.css'
import './projects.css'
import './source-control.css'
import { createNoIdeApp } from './app.js'

createApp(createNoIdeApp()).use(Quasar, {
  components: { QBtn, QToggle },
  config: { brand: { primary: '#dc4d86', positive: '#27896d', negative: '#d34d65' } }
}).mount('#app')

// Keep document language Chinese for system-font fallback.
document.documentElement.lang = 'zh-CN'
