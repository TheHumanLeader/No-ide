/** Project → shared run configurations → independently controlled instances.
 * This is an in-memory review model, NOT a local process or filesystem adapter.
 */
export const RUNTIMES = {
  Java: { mark:'J', tone:'peach', runtime:'Java · Spring Boot', mode:'应用重启', command:'./mvnw spring-boot:run', port:8080 },
  JavaScript: { mark:'V', tone:'mint', runtime:'JavaScript · Vite', mode:'模块热替换', command:'npm run dev', port:5173 },
  'Node.js': { mark:'N', tone:'lime', runtime:'Node.js', mode:'进程重启', command:'node --watch src/index.js', port:3000 },
  Python: { mark:'Py', tone:'blue', runtime:'Python', mode:'进程重启', command:'python app.py', port:8000 },
  Android: { mark:'A', tone:'green', runtime:'Gradle · Android SDK', mode:'重新部署', command:'./gradlew assembleDebug', port:null }
}
let sequence = 0
export const newId = prefix => `${prefix}-${Date.now().toString(36)}-${++sequence}`
export const validPort = port => Number.isInteger(Number(port)) && Number(port)>0 && Number(port)<65536
export function nextPort(instances, from=8080) {
  const used = new Set(instances.map(i=>i.port))
  for(let port=Number(from)||8080; port<=65535; port++) if(!used.has(port)) return port
  for(let port=1024;port<Number(from);port++) if(!used.has(port))return port
  return null
}
export function makeInstance(projectId, config, values={}) {
  const instance = {
    id:newId('instance'), projectId, configId:config.id,
    name:config.name+' · 01', slug:config.slug+'#01',
    port:config.port, args:'', environment:'', auto:true,
    state:'stopped', version:0, busy:false, step:0, error:null, pending:false, last:'—', ...values
  }
  // Shared properties stay linked to the SAME reactive configuration.
  for(const key of ['type','runtime','mark','tone','path','command','mode','watch','description'])
    Object.defineProperty(instance,key,{enumerable:true,get:()=>config[key]})
  Object.defineProperty(instance,'configName',{enumerable:true,get:()=>config.name})
  return instance
}
export const DirectoryPicker = {
  props: { modelValue:Object, label:{default:'项目目录'} },
  emits:['update:modelValue'],
  data:()=>({fallback:!('showDirectoryPicker' in window),problem:''}),
  methods: {
    async choose() {
      this.problem=''
      if(this.fallback){this.$refs.folderInput.click();return}
      try {
        // Direct user gesture. No traversal, file reads, upload, or write access.
        const handle=await window.showDirectoryPicker({mode:'read',id:'no-ide-directory'})
        this.$emit('update:modelValue',{name:handle.name,origin:'browser',absolutePath:null})
      } catch(error) {
        if(error.name==='AbortError')return
        this.problem='浏览器未允许目录访问；可以点击“兼容选择”。不会上传文件。'
        this.fallback=true
      }
    },
    selected(event) {
      const first=event.target.files?.[0]
      if(!first){this.problem='未选择目录。兼容选择器无法识别空目录。';return}
      const name=(first.webkitRelativePath||'').split('/')[0]
      if(!name){this.problem='浏览器未返回目录信息，请使用支持目录选择的浏览器。';return}
      this.$emit('update:modelValue',{name,origin:'browser-fallback',absolutePath:null})
      event.target.value='' // release File references; do not read or retain bytes
    }
  },
  template:`<div class="directory-picker"><span class="field-title">{{label}}</span><div class="folder-choice" :class="{chosen:modelValue}"><span class="folder-glyph">▱</span><div><strong>{{modelValue?.name || '选择电脑上的文件夹'}}</strong><small>{{modelValue?'已选择 · 浏览器不提供完整磁盘路径':'点击选择，不用手写路径'}}</small></div><button type="button" class="pick-folder" @click="choose">{{fallback?'兼容选择':modelValue?'重新选择':'选择文件夹'}}</button></div><input ref="folderInput" type="file" webkitdirectory multiple hidden @change="selected"><p class="folder-privacy">只记录目录名，不上传、不扫描内容、不修改文件。完整本机路径待执行器接入。</p><p v-if="fallback" class="folder-privacy">兼容选择可能枚举目录文件，请优先选择小目录；不会发送文件。</p><p v-if="problem" class="form-error" role="alert">{{problem}}</p></div>`
}
