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
export const AppIcon = {
  props: { name: String, size: { default: 18 } },
  setup: () => ({ icons: ICONS }),
  template: `<svg :width="size" :height="size" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path v-for="(p,i) in (icons[name] || icons.code)" :key="i" :d="p"></path></svg>`
}
export const INITIAL = [
  { id:'web', name:'管理前端', slug:'web-console', type:'JavaScript', runtime:'Vue 3 · Quasar', mark:'V', tone:'mint', port:5173, mode:'模块热替换', state:'running', version:4, command:'npm run dev', path:'C:\\Projects\\no-ide\\web', watch:'src/**', auto:true, last:'09:41:08', description:'页面变化，即刻可见。' },
  { id:'api', name:'业务服务', slug:'core-api', type:'Java', runtime:'Java 21 · Spring Boot', mark:'J', tone:'peach', port:8080, mode:'应用重启', state:'running', version:3, command:'./mvnw spring-boot:run', path:'C:\\Projects\\no-ide\\core-api', watch:'src/main/**', auto:true, last:'09:41:06', description:'订单、用户与核心业务接口。' },
  { id:'worker', name:'任务服务', slug:'task-worker', type:'Python', runtime:'Python 3.12 · Uvicorn', mark:'Py', tone:'blue', port:8000, mode:'进程重启', state:'running', version:2, command:'python -m uvicorn app:app --reload', path:'C:\\Projects\\no-ide\\worker', watch:'app/**', auto:true, last:'09:40:52', description:'异步处理和自动化任务。' },
  { id:'gateway', name:'网关服务', slug:'gateway', type:'Java', runtime:'Java 21 · Spring Boot', mark:'J', tone:'peach', port:9000, mode:'应用重启', state:'stopped', version:0, command:'./mvnw spring-boot:run', path:'C:\\Projects\\no-ide\\gateway', watch:'src/main/**', auto:true, last:'—', description:'统一入口，与业务服务协同运行。' },
  { id:'android', name:'安卓客户端', slug:'android-app', type:'Android', runtime:'Gradle · Android SDK', mark:'A', tone:'green', port:null, mode:'重新部署', state:'stopped', version:0, command:'./gradlew assembleDebug', path:'C:\\Projects\\no-ide\\android', watch:'app/src/**', auto:false, last:'—', description:'构建、安装到设备并查看运行日志。' },
  { id:'node', name:'Node 工具服务', slug:'node-tools', type:'Node.js', runtime:'Node.js 22', mark:'N', tone:'lime', port:3000, mode:'进程重启', state:'stopped', version:0, command:'node --watch src/index.js', path:'C:\\Projects\\no-ide\\tools', watch:'src/**', auto:true, last:'—', description:'轻量接口与开发工具。' }
]
