import test from 'node:test'
import assert from 'node:assert/strict'
import { reactive } from 'vue'
import { makeInstance, nextPort, validPort } from '../src/project-model.js'
import { lineDiff, sampleRepositories } from '../src/source-control.js'

test('shared configuration and independent instance overrides',()=>{
  const c=reactive({id:'c',name:'API',slug:'api',type:'Java',port:8080,command:'old'})
  const a=makeInstance('p',c,{port:8080}),b=makeInstance('p',c,{port:8081})
  c.command='new';assert.equal(a.command,'new');assert.equal(b.command,'new')
  a.state='running';assert.equal(b.state,'stopped');assert.equal(b.port,8081)
})
test('ports validate and reserve separately',()=>{
  assert.ok(validPort(65535));assert.ok(!validPort(0));assert.ok(!validPort(65536))
  assert.equal(nextPort([{port:8080},{port:8081}],8080),8082)
})
test('line diff reconstructs both sides, including additions and removals',()=>{
  for(const [a,b] of [['a\nb\nc','a\nx\nc'],['','new'],['old',''],['a\n','a\n'],['x\nx','x'],['<script>','<img>']]){
    const d=lineDiff(a,b)
    assert.equal(d.rows.filter(r=>r.kind!=='add').map(r=>r.text).join('\n'),a)
    assert.equal(d.rows.filter(r=>r.kind!=='remove').map(r=>r.text).join('\n'),b)
  }
})
test('diff work is bounded',()=>{
  assert.ok(lineDiff('x'.repeat(70000),'a').limited)
  assert.ok(lineDiff(Array(242).fill('a').join('\n'),'a').limited)
})
test('sample repositories never reuse state by reference',()=>{
  const a=sampleRepositories(),b=sampleRepositories();a[0].changes.shift()
  assert.equal(b[0].changes.length,3);assert.ok(a.every(r=>r.sample))
})
