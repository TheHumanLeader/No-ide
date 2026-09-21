import { computed, ref, shallowRef, watch, onMounted, onUnmounted } from 'vue'
import './runtime-logs.css'

// Only this panel scrolls; never use scrollIntoView (which moves the whole page).
// The parent keeps a bounded 1,000-record buffer. Review mode keeps one bounded
// snapshot, so trimming incoming records cannot move the text being read.
export const RuntimeLogs = {
  props: {
    logs: { type: Array, required: true },
    project: { type: Object, required: true },
    label: { type: Function, required: true }
  },
  emits: ['copy'],
  setup(props, { emit }) {
    const viewport = ref(null), content = ref(null)
    const filter = ref(''), following = ref(true), paused = ref(false)
    const heldLogs = shallowRef([])
    let lastRenderedSource = [], expectedTop = null, observer = null, alive = true
    let touchY = null
    const source = computed(() => paused.value || !following.value ? heldLogs.value : props.logs)
    const visibleLogs = computed(() => {
      const ids = new Set([...props.project.instances.map(i => i.id), ...props.project.configs.map(c => c.id)])
      const query = filter.value.toLowerCase()
      return source.value.filter(l => ids.has(l.instance) && l.text.toLowerCase().includes(query)).slice(-120)
    })
    const autoScroll = computed(() => following.value && !paused.value)
    const atBottom = el => el.scrollHeight - el.clientHeight - Math.max(0, el.scrollTop) <= 3
    function cancelScroll() { expectedTop = null }
    function scrollBottom(force = false) {
      if (!alive || !viewport.value || (!force && !autoScroll.value)) return
      // The log watcher runs after Vue has committed the DOM. The parent already
      // batches socket records once per frame. Scroll here, not in a second rAF:
      // a delayed follow frame could otherwise override a user's scrollbar drag.
      const el = viewport.value
      const top = Math.max(0, el.scrollHeight - el.clientHeight)
      if (Math.abs(el.scrollTop - top) <= 1) { expectedTop = null; return }
      expectedTop = top
      el.scrollTop = top
    }
    function hold() {
      if (!following.value || paused.value) return
      heldLogs.value = lastRenderedSource.slice(-1000)
      following.value = false
      cancelScroll()
    }
    function resume() {
      paused.value = false
      following.value = true
      heldLogs.value = []
      // The post-flush watcher scrolls again after live rows replace the snapshot.
      scrollBottom()
    }
    function pause() {
      if (paused.value) { resume(); return }
      if (following.value) heldLogs.value = lastRenderedSource.slice(-1000)
      paused.value = true
      following.value = false
      cancelScroll()
    }
    function onScroll() {
      const el = viewport.value
      if (!el) return
      if (expectedTop !== null && Math.abs(el.scrollTop - expectedTop) <= 3) {
        expectedTop = null
        return
      }
      if (!atBottom(el)) hold()
      else if (!paused.value && !following.value) resume()
    }
    function onWheel(event) { if (event.deltaY < 0) hold() }
    function onKey(event) {
      if (['ArrowUp', 'PageUp', 'Home'].includes(event.key) || (event.key === ' ' && event.shiftKey)) hold()
      if (event.key === 'End' && !paused.value) { event.preventDefault(); resume() }
    }
    function onTouchStart(event) { touchY = event.touches[0]?.clientY ?? null }
    function onTouchMove(event) {
      const y = event.touches[0]?.clientY
      if (touchY !== null && y !== undefined && y > touchY + 1) hold()
      if (y !== undefined) touchY = y
    }
    function copyLogs() {
      emit('copy', visibleLogs.value.map(l => `${new Date(l.time).toLocaleTimeString()} [${props.label(l.instance)}] ${l.text}`).join('\n'))
    }
    // Watch records, not length: the rolling window stays at 120 while new logs arrive.
    watch(visibleLogs, () => {
      lastRenderedSource = source.value
      scrollBottom()
    }, { flush: 'post', immediate: true })
    watch(filter, () => {
      if (!paused.value) resume()
      else scrollBottom(true)
    }, { flush: 'post' })
    watch(() => props.project.id, () => { filter.value = ''; resume() }, { flush: 'post' })
    onMounted(() => {
      lastRenderedSource = source.value
      if (typeof ResizeObserver !== 'undefined') {
        observer = new ResizeObserver(() => scrollBottom())
        observer.observe(viewport.value)
        observer.observe(content.value)
      }
      scrollBottom()
    })
    onUnmounted(() => { alive = false; cancelScroll(); observer?.disconnect() })
    return { viewport, content, filter, paused, following, visibleLogs, autoScroll,
      resume, hold, pause, onScroll, onWheel, onKey, onTouchStart, onTouchMove, copyLogs }
  },
  template: `
<section class="panel live-log-panel" data-log-panel-version="0.4.2-logfollow.1">
  <header class="panel-header">
    <div><h2>运行日志</h2><span class="tiny-muted">实时进程输出 · 最近 120 条</span></div>
    <div class="live-log-actions">
      <label class="log-auto-toggle"><input type="checkbox" aria-label="自动滚动日志" :checked="autoScroll" @change="$event.target.checked?resume():hold()">自动滚动</label>
      <button class="text-button" @click="pause">{{paused?'继续展示':'暂停展示'}}</button>
      <button class="text-button" @click="copyLogs">复制可见日志</button>
    </div>
  </header>
  <div class="live-log-search"><input v-model="filter" placeholder="筛选日志内容" aria-label="筛选日志内容"></div>
  <div class="live-log-viewport">
    <div ref="viewport" class="live-log-body" tabindex="0" role="region" aria-label="运行日志内容"
      @scroll.passive="onScroll" @wheel.passive="onWheel" @keydown="onKey"
      @touchstart.passive="onTouchStart" @touchmove.passive="onTouchMove">
      <div ref="content">
        <div v-for="l in visibleLogs" :key="l.seq" :data-log-seq="l.seq" class="live-log-row">
          <time>{{new Date(l.time).toLocaleTimeString()}}</time><span>{{label(l.instance)}}</span>
          <pre :class="{'error-text':l.stream==='stderr'||l.stream==='error'}">{{l.text}}</pre>
        </div>
        <div v-if="!visibleLogs.length" class="empty-log">{{filter?'没有匹配的日志。':'运行实例后，这里显示真实标准输出和错误。'}}</div>
      </div>
    </div>
    <button v-if="!autoScroll" class="log-back-bottom" @click="resume" aria-label="回到底部并恢复自动滚动">
      <span>{{paused?'展示已暂停':'正在查看历史'}}</span> ↓ 回到底部
    </button>
  </div>
</section>`
}
