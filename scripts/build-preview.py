"""Build a self-contained UI preview.

When Quasar assets are available, this embeds the actual Quasar runtime.
With --offline-controls, it uses two explicitly marked compatibility controls
for local interaction review. This is NOT a Quasar production-build test.
Never includes font files or accesses the network.
"""
from pathlib import Path
import argparse
import re
import json

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--vue', type=Path, required=True)
parser.add_argument('--quasar-js', type=Path)
parser.add_argument('--quasar-css', type=Path)
parser.add_argument('--offline-controls', action='store_true')
parser.add_argument('--output', type=Path, default=root / 'No-ide-preview.html')
args = parser.parse_args()

if not args.vue.is_file():
    raise SystemExit('Vue runtime file not found.')
if not args.offline_controls and not (args.quasar_js and args.quasar_css):
    raise SystemExit('Supply real Quasar assets, or explicitly select --offline-controls.')

code = (root / 'src/app.js').read_text(encoding='utf-8')
code = re.sub(r"import \{([^}]+)\} from 'vue'", r'const {\1} = Vue', code, count=1)
code = code.replace('export function createNoIdeApp()', 'function createNoIdeApp()')
code = re.sub(r"^import .+ from './(?:project-model|source-control|catalog)\.js'\n", '', code, flags=re.M)
code=re.sub(r"^import appTemplate from './layout.html\?raw'\n", '', code, flags=re.M)
modules=['const appTemplate = '+json.dumps((root/'src/layout.html').read_text(encoding='utf-8'),ensure_ascii=False)+';']
for name in ['catalog.js','project-model.js','source-control.js']:
    module=(root / 'src' / name).read_text(encoding='utf-8')
    module=re.sub(r"^import .+ from 'vue'\n", '', module, flags=re.M)
    module=re.sub(r'^export ', '', module, flags=re.M)
    modules.append(module)
code='\n'.join(modules)+'\n'+code
css = (root / 'src/styles.css').read_text(encoding='utf-8') + '\n' + (root / 'src/quasar-overrides.css').read_text(encoding='utf-8')
css += '\n' + (root / 'src/projects.css').read_text(encoding='utf-8') + '\n' + (root / 'src/source-control.css').read_text(encoding='utf-8')
vue = args.vue.read_text(encoding='utf-8')
if args.offline_controls:
    code = code.replace('示例项目与数据 · 未连接本地执行器', '示例数据 · 离线交互版 · 执行器未连接')
    bootstrap = '''
// OFFLINE REVIEW ONLY: small compatibility controls, not the Quasar runtime.
// The shipped src/main.js uses genuine Quasar QBtn / QToggle.
const ReviewButton = {
  props: { label:String, disable:Boolean, loading:Boolean },
  template: '<button type="button" class="q-btn" :disabled="disable || loading"><span class="q-btn__content"><slot></slot><span v-if="label">{{label}}</span></span></button>'
};
const ReviewToggle = {
  inheritAttrs:false,
  props: { modelValue:Boolean, label:String, disable:Boolean, color:String, size:String },
  emits:['update:modelValue'],
  template: '<label class="q-toggle offline-q-toggle"><input type="checkbox" role="switch" :checked="modelValue" :disabled="disable" :aria-label="$attrs[\\'aria-label\\'] || label" @change="$emit(\\'update:modelValue\\',$event.target.checked)"><span class="toggle-track"></span><span v-if="label">{{label}}</span></label>'
};
Vue.createApp(createNoIdeApp()).component('QBtn', ReviewButton).component('QToggle', ReviewToggle).mount('#app');
'''
    runtime = ''
    mode = 'offline-compatible-controls'
else:
    css = args.quasar_css.read_text(encoding='utf-8') + '\n' + css
    runtime = args.quasar_js.read_text(encoding='utf-8')
    bootstrap = "Vue.createApp(createNoIdeApp()).use(Quasar,{config:{brand:{primary:'#d74780'}}}).mount('#app'); document.documentElement.lang='zh-CN';"
    mode = 'quasar'

def esc_script(s):
    return re.sub(r'</script', '<\\/script', s, flags=re.I)

notice = (root / 'THIRD_PARTY_NOTICES.md').read_text(encoding='utf-8').replace('--', '—')
html = f'''<!doctype html>
<html lang="zh-CN" data-renderer="{mode}">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>No-ide · 交互预览</title>
<!-- Prototype only. No local execution, network requests, toolchain detection,
     or resource measurements. Renderer: {mode}. See repository README. -->
<!-- Third-party notice
{notice}
-->
<style>{css}</style></head>
<body><div id="app"></div>
<script>{esc_script(vue)}</script>
<script>{esc_script(runtime)}</script>
<script>{esc_script(code)}\n{esc_script(bootstrap)}</script>
</body></html>'''
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(html, encoding='utf-8')
print(f'Created {args.output} ({len(html.encode()):,} bytes), renderer={mode}')
