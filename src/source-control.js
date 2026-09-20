import { ref, computed } from 'vue'

// Deliberately small, bounded, local sample texts. Never read from the chosen folder.
export function sampleRepositories() {
  return [
    {id:'commerce-git',name:'商城主仓库',type:'Git',root:'commerce/',branch:'main',remote:'origin/main',sample:true,ahead:0,behind:0,revision:0,busy:false,history:[],changes:[
      {id:'api',path:'services/order/OrderController.java',status:'M',before:'@RestController\nclass OrderController {\n  @GetMapping("/orders")\n  List<Order> list() {\n    return orders.findAll();\n  }\n}',after:'@RestController\nclass OrderController {\n  @GetMapping("/orders")\n  List<Order> list(@RequestParam int page) {\n    return orders.findPage(page, 20);\n  }\n}',staged:false},
      {id:'vite',path:'web/vite.config.js',status:'M',before:'export default defineConfig({\n  plugins: [vue()],\n  server: { port: 5173 }\n})',after:'export default defineConfig({\n  plugins: [vue()],\n  server: {\n    port: 5173,\n    strictPort: true\n  }\n})',staged:false},
      {id:'readme',path:'docs/local-run.md',status:'A',before:'',after:'# 本地启动\n\n运行网关、两个业务实例和 Vite 前端。\n每个实例使用独立端口。',staged:false}
    ]},
    {id:'commerce-svn',name:'公共组件库',type:'SVN',root:'shared-components/',branch:'trunk',remote:'示例 SVN 服务器 / trunk',sample:true,ahead:0,behind:0,revision:128,busy:false,history:[],changes:[
      {id:'shared',path:'src/OrderValidator.java',status:'M',before:'boolean valid(Order order) {\n  return order != null;\n}',after:'boolean valid(Order order) {\n  return order != null\n      && order.getAmount() > 0;\n}',staged:false,selected:false},
      {id:'guide',path:'README.md',status:'M',before:'# 公共组件\n\n支持 Java 项目。',after:'# 公共组件\n\n支持多个 Java 服务共享调用。',staged:false,selected:false}
    ]}
  ]
}
/** Exact line LCS for small preview texts. Bound O(n*m) memory and CPU. */
export function lineDiff(before='',after='') {
  if(before.length+after.length>65536)return {limited:true,rows:[]}
  const a=before===''?[]:before.split('\n'),b=after===''?[]:after.split('\n')
  if(a.length>240||b.length>240)return {limited:true,rows:[]}
  const table=Array.from({length:a.length+1},()=>new Uint16Array(b.length+1))
  for(let i=a.length-1;i>=0;i--)for(let j=b.length-1;j>=0;j--)
    table[i][j]=a[i]===b[j]?table[i+1][j+1]+1:Math.max(table[i+1][j],table[i][j+1])
  const rows=[];let i=0,j=0
  while(i<a.length||j<b.length){
    if(i<a.length&&j<b.length&&a[i]===b[j]){rows.push({kind:'same',old:i+1,new:j+1,text:a[i]});i++;j++}
    else if(i<a.length&&(j===b.length||table[i+1][j]>=table[i][j+1])){rows.push({kind:'remove',old:i+1,new:null,text:a[i++]})}
    else rows.push({kind:'add',old:null,new:j+1,text:b[j++]})
  }
  return {limited:false,rows}
}
export const SourceControl = {
  props:{project:{type:Object,required:true}},
  emits:['notice'],
  setup(props,{emit}) {
    const repoId=ref(props.project.repositories[0]?.id||''), fileId=ref(''),scope=ref('all'),layout=ref(window.matchMedia('(max-width: 600px)').matches?'unified':'split')
    const message=ref(''),confirmation=ref(null),info=ref(''),tab=ref('changes')
    const repo=computed(()=>props.project.repositories.find(r=>r.id===repoId.value)||props.project.repositories[0])
    const files=computed(()=>repo.value?.changes.filter(f=>scope.value==='all'||(scope.value==='staged'?f.staged:!f.staged))||[])
    const file=computed(()=>files.value.find(f=>f.id===fileId.value)||files.value[0])
    const diff=computed(()=>file.value?lineDiff(file.value.before,file.value.after):{rows:[],limited:false})
    const stats=computed(()=>({add:diff.value.rows.filter(r=>r.kind==='add').length,remove:diff.value.rows.filter(r=>r.kind==='remove').length}))
    const chosen=computed(()=>repo.value?.changes.filter(f=>repo.value.type==='Git'?f.staged:f.selected)||[])
    const say=text=>{info.value=text;emit('notice',text)}
    function switchRepo(){fileId.value='';scope.value='all';message.value='';confirmation.value=null;info.value='';tab.value='changes'}
    function toggle(f){if(repo.value.busy)return;if(repo.value.type==='Git')f.staged=!f.staged;else f.selected=!f.selected;confirmation.value=null}
    function selectAll(){const r=repo.value;if(!r||r.busy)return;const key=r.type==='Git'?'staged':'selected';const value=!r.changes.every(f=>f[key]);r.changes.forEach(f=>f[key]=value);confirmation.value=null}
    function prepare(action){
      const r=repo.value;if(!r||!r.sample||r.busy)return
      if(r.changes.some(f=>f.conflict)){say('存在未解决冲突，本次操作已阻止；不会覆盖本地文件。');return}
      if(action==='pull'&&r.changes.length){say('有本地改动，已阻止更新。先检查并提交；不会自动丢弃或覆盖。');return}
      if(action==='pull'&&r.ahead&&r.behind){say('分支已分叉，不能快进；需要先处理合并。');return}
      if(action==='commit'&&(!chosen.value.length||!message.value.trim())){say('先选择要提交的文件，并填写提交说明。');return}
      if(action==='push'&&(!r.ahead||r.behind)){say(r.behind?'远端领先，已阻止推送。':'没有待推送的本地提交。');return}
      confirmation.value={action,repoId:r.id,revision:r.revision,ids:chosen.value.map(f=>f.id),message:message.value.trim()}
    }
    function execute(){
      const c=confirmation.value,r=repo.value
      if(!c||r.id!==c.repoId||r.revision!==c.revision||!r.sample){confirmation.value=null;say('仓库状态已变化，请重新确认。');return}
      // This transaction modifies ONLY the sample state. There is no fetch or shell call.
      if(r.changes.some(f=>f.conflict)){confirmation.value=null;say('冲突未解决，已阻止操作。');return}
      if(c.action==='commit'){
        if(chosen.value.map(f=>f.id).sort().join('|')!==[...c.ids].sort().join('|')){confirmation.value=null;say('文件选择已变化，请重新确认。');return}
        const submitted=r.changes.filter(f=>c.ids.includes(f.id))
        r.changes=r.changes.filter(f=>!c.ids.includes(f.id));r.revision++
        if(r.type==='Git')r.ahead++
        r.history.unshift({id:r.type==='Git'?`sample-${r.revision}`:`r${r.revision}`,message:c.message,files:submitted.map(f=>f.path),remote:r.type==='SVN'})
        r.history=r.history.slice(0,50);message.value=''
        say(r.type==='Git'?`演示：${submitted.length} 个文件已本地提交，尚未推送。`:`演示：${submitted.length} 个文件已提交到示例 SVN 服务器。未连接真实仓库。`)
      }else if(c.action==='push'){
        r.ahead=0;r.history.forEach(h=>h.remote=true);say('演示：本地提交已推送。没有访问真实远程仓库。')
      }else{r.behind=0;say(r.type==='Git'?'演示：拉取检查完成，示例远端没有新提交；没有请求真实仓库。':'演示：工作副本已更新到示例最新版本；没有访问 SVN 服务器。')}
      confirmation.value=null
    }
    function conflict(){const f=file.value;if(!f)return;f.conflict=true;f.staged=false;f.selected=false;confirmation.value=null;say('已注入示例冲突。提交、拉取和推送被阻止，不会假装成功。')}
    function resolve(){if(!file.value)return;file.value.conflict=false;say('演示：保留当前一侧，已标记此文件冲突解决。未修改磁盘。')}
    return {repoId,repo,files,fileId,file,scope,layout,message,confirmation,info,tab,diff,stats,chosen,switchRepo,toggle,selectAll,prepare,execute,conflict,resolve}
  },
  template:`<section class="source-control">
    <div v-if="!repo" class="panel vcs-empty"><h2>这个项目还没有已连接的代码仓库</h2><p>本地 Git / SVN 检测与真实拉取、提交需要执行器。不会把目录名当作已连接的仓库。</p><small>切换到“示例商城”可体验独立的 Git / SVN 示例。</small></div>
    <template v-else>
      <div class="vcs-toolbar panel"><div class="repo-identity"><span :class="['repo-symbol',repo.type.toLowerCase()]">{{repo.type==='Git'?'G':'S'}}</span><div><select v-model="repoId" @change="switchRepo" aria-label="选择代码仓库"><option v-for="r in project.repositories" :key="r.id" :value="r.id">{{r.name}} · {{r.type}}</option></select><small>{{repo.root}} · {{repo.branch||'待检测'}}</small></div></div><div class="repo-actions"><span v-if="repo.type==='Git'&&repo.sample" class="sync-count">↓ {{repo.behind}}　↑ {{repo.ahead}}</span><q-btn class="app-btn secondary" :disable="!repo.sample" @click="prepare('pull')">{{repo.type==='Git'?'拉取代码':'更新工作副本'}}<span class="action-demo">演示</span></q-btn><q-btn v-if="repo.type==='Git'" class="app-btn secondary" :disable="!repo.sample||!repo.ahead" @click="prepare('push')">推送 <span class="action-demo">演示</span></q-btn></div></div>
      <div class="vcs-boundary"><span class="dot amber"></span>{{repo.sample?'以下为独立的示例仓库；Diff、拉取、提交和推送不会读取或修改你的代码。':'已保存仓库配置，等待本地执行器。没有检测、下载或连接真实仓库。'}}</div>
      <div v-if="!repo.sample" class="panel vcs-empty"><h2>等待连接执行器</h2><p>{{repo.importRequested?'仓库获取任务仅已记录，尚未 clone / checkout。':'仓库类型是配置值，尚未验证目录中的 .git / .svn。'}}</p><code>{{repo.remote}}</code></div>
      <template v-else>
      <div class="vcs-tabs"><button :class="{active:tab==='changes'}" @click="tab='changes'">本地变更 <b>{{repo.changes.length}}</b></button><button :class="{active:tab==='history'}" @click="tab='history'">提交记录 <b>{{repo.history.length}}</b></button><span>{{repo.type==='Git'?'提交到本地，再单独推送':'SVN 提交直接写入服务器；没有 Git 暂存区'}}</span></div>
      <div v-if="tab==='changes'" class="vcs-grid">
        <aside class="panel changed-files"><div class="changed-head"><h2>变更文件</h2><button @click="selectAll" :disabled="!repo.changes.length">{{repo.type==='Git'?'全部暂存 / 取消':'全选 / 取消'}}</button></div><select v-if="repo.type==='Git'" v-model="scope" aria-label="差异范围"><option value="all">全部变更</option><option value="working">未暂存 · 工作区</option><option value="staged">已暂存 · 索引</option></select><div class="file-list"><div v-for="f in files" :key="f.id" :class="['changed-file',{active:file?.id===f.id}]" @click="fileId=f.id"><input type="checkbox" :checked="repo.type==='Git'?f.staged:f.selected" @click.stop @change="toggle(f)" :aria-label="(repo.type==='Git'?'暂存 ':'选择 ')+f.path"><button @click.stop="fileId=f.id"><strong>{{f.path.split('/').pop()}}</strong><small>{{f.path}}</small></button><b :class="f.conflict?'conflict':f.status">{{f.conflict?'!':f.status}}</b></div><div v-if="!files.length" class="empty-log">{{repo.changes.length?'这个分组没有文件':'工作区干净，没有待提交的变更。'}}</div></div><footer>已{{repo.type==='Git'?'暂存':'选择'}} {{chosen.length}} / {{repo.changes.length}} 个文件</footer></aside>
        <section class="panel diff-panel"><header><div><h2>{{file?.path.split('/').pop()||'差异预览'}}</h2><small>{{file?file.path:'选择左侧文件查看 Diff'}}</small></div><span class="diff-stat"><b>+{{stats.add}}</b><i>−{{stats.remove}}</i></span><div class="mini-tabs"><button :class="{active:layout==='split'}" @click="layout='split'">并排</button><button :class="{active:layout==='unified'}" @click="layout='unified'">统一</button></div></header>
          <div v-if="file?.conflict" class="conflict-banner"><strong>此文件有示例冲突，提交已禁用。</strong><button @click="resolve">保留当前内容并标记解决（演示）</button></div>
          <template v-if="file"><div class="diff-labels"><span>{{repo.type==='Git'?'HEAD':'BASE'}} · 修改前</span><span>{{repo.type==='Git'&&file.staged?'暂存区':'工作区'}} · 修改后</span></div><div v-if="diff.limited" class="empty-log">文件超过预览上限，请使用外部差异工具。</div><div v-else :class="['diff-code',layout]" role="region" aria-label="代码差异" tabindex="0"><div v-for="(row,i) in diff.rows" :key="i" :class="['diff-line',row.kind]"><template v-if="layout==='split'"><div :class="['diff-cell',{blank:row.kind==='add'}]"><span class="line-number">{{row.old||''}}</span><span class="line-sign">{{row.kind==='remove'?'−':' '}}</span><code>{{row.kind==='add'?'':row.text}}</code></div><div :class="['diff-cell',{blank:row.kind==='remove'}]"><span class="line-number">{{row.new||''}}</span><span class="line-sign">{{row.kind==='add'?'+':' '}}</span><code>{{row.kind==='remove'?'':row.text}}</code></div></template><template v-else><span class="line-number">{{row.old||''}}</span><span class="line-number">{{row.new||''}}</span><span class="line-sign">{{row.kind==='add'?'+':row.kind==='remove'?'−':' '}}</span><code>{{row.text}}</code></template></div></div><footer class="diff-foot"><span>文本按行比较 · 示例文件，不是当前项目磁盘内容</span><button @click="conflict" :disabled="file.conflict">模拟冲突</button></footer></template><div v-else class="diff-empty"><strong>没有需要比较的文件</strong><p>已提交内容可在提交记录中查看。</p></div></section>
      </div>
      <section v-else class="panel vcs-history"><article v-for="h in repo.history" :key="h.id"><span>{{h.id}}</span><div><strong>{{h.message}}</strong><small v-for="p in h.files" :key="p">{{p}}</small></div><b>{{h.remote?'已到示例远端':'仅本地 · 未推送'}}</b></article><div v-if="!repo.history.length" class="empty-log">此预览中还没有提交记录。</div></section>
      <div class="panel commit-bar"><div><label for="commit-message">提交说明</label><input id="commit-message" v-model="message" placeholder="这次改了什么？" maxlength="500" :disabled="!repo.changes.length"><small>{{repo.type==='Git'?'只提交已暂存文件，未暂存内容不会顺带提交。':'仅提交勾选的文件，直接进入 SVN 服务器。'}}</small></div><q-btn class="app-btn primary" :disable="!chosen.length||!message.trim()||repo.changes.some(f=>f.conflict)" @click="prepare('commit')">{{repo.type==='Git'?'提交到本地':'提交到 SVN'}}<span class="action-demo">演示</span></q-btn></div>
      <div v-if="confirmation" class="vcs-confirm" role="region" aria-label="确认版本操作"><div><strong>{{confirmation.action==='commit'?(repo.type==='Git'?'确认本地提交':'确认远端提交'):confirmation.action==='push'?'确认推送':'确认拉取 / 更新'}} · 仅演示</strong><p>{{repo.name}} · {{repo.branch}} → {{confirmation.action==='commit'&&repo.type==='Git'?'本地提交记录':repo.remote}}</p><p v-if="confirmation.action==='commit'">{{confirmation.ids.length}} 个文件 · {{confirmation.message}}</p><small>不会执行真实 Git / SVN 命令。</small></div><button class="text-button" @click="confirmation=null">取消</button><q-btn class="app-btn primary" @click="execute">确认演示</q-btn></div>
      <p v-if="info" class="vcs-info" role="status">{{info}}</p>
      </template>
    </template>
  </section>`
}
