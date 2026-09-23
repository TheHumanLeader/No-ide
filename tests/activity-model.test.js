import test from 'node:test'
import assert from 'node:assert/strict'
import { mergeActivities, activeActivity, elapsedText } from '../src/activity-model.js'
test('A late refresh cannot replace a completed activity with old progress',()=>{
 const old={id:'a',config:'c',revision:1,started_at:100,status:'running'}
 const done={...old,revision:4,status:'succeeded',finished_at:1100}
 assert.equal(mergeActivities({c:done},[old]).c,done)
 assert.equal(activeActivity(old),true);assert.equal(activeActivity(done),false)
 assert.equal(elapsedText(done,3000),'1 秒')
})
test('An old task cannot clobber the next task',()=>{
 const newer={id:'b',config:'c',revision:1,started_at:200,status:'queued'}
 assert.equal(mergeActivities({c:newer},[{id:'a',config:'c',revision:100,started_at:100}]).c,newer)
 assert.equal(activeActivity({...newer,status:'cancelling'}),true)
})
