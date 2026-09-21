// Small editable tables. Values remain separate argv entries / key-value pairs.
export const ValueRows = {
  props:{modelValue:{type:Array,default:()=>[]},label:{type:String,default:'参数'},pair:Boolean,placeholder:String},
  emits:['update:modelValue'],
  methods:{set(i,k,v){const rows=this.modelValue.map(r=>({...r}));rows[i][k]=v;this.$emit('update:modelValue',rows)},add(){this.$emit('update:modelValue',[...this.modelValue,{key:'',value:''}])},remove(i){this.$emit('update:modelValue',this.modelValue.filter((_,n)=>n!==i))}},
  template:`<div class="value-rows"><div class="value-heading"><strong>{{label}}</strong><button type="button" class="text-button" @click="add">＋ 添加{{label}}</button></div><div v-for="(row,i) in modelValue" :key="i" class="value-row" :class="{pair}"><input v-if="pair" :value="row.key" @input="set(i,'key',$event.target.value)" :aria-label="label+'名称 '+(i+1)" placeholder="名称"><span v-if="pair">=</span><input :value="row.value" @input="set(i,'value',$event.target.value)" :aria-label="label+'值 '+(i+1)" :placeholder="placeholder||'值（空格保留为同一参数）'"><button type="button" @click="remove(i)" :aria-label="'删除'+label+' '+(i+1)">×</button></div><small v-if="!modelValue.length" class="value-empty">未设置，使用默认值。</small></div>`
}
export function asRows(value){return Array.isArray(value)?value.map(value=>({value})):Object.entries(value||{}).map(([key,value])=>({key,value}))}
export function argv(rows){return(rows||[]).map(r=>String(r.value??'')).filter(s=>s!=='')}
export function pairs(rows){const out={};for(const r of rows||[]){if(!r.key&&!r.value)continue;const key=String(r.key).trim();if(!key||/[=\0\r\n]/.test(key)||Object.hasOwn(out,key))throw Error('属性/变量名称不能为空、重复或包含等号、换行。');Object.defineProperty(out,key,{value:String(r.value??''),enumerable:true,configurable:true,writable:true})}return out}
