import test from 'node:test'
import assert from 'node:assert/strict'
import {toggleRows,selectVisible,fileGroup,metadataPath} from '../src/selection.js'
const paths=Array.from({length:2000},(_,n)=>`file-${n}.txt`)
test('whole row toggles the same selection represented by its checkbox',()=>{
 let r=toggleRows(paths,[],'',paths[0]);assert.deepEqual(r.selected,[paths[0]])
 r=toggleRows(paths,r.selected,r.anchor,paths[0]);assert.deepEqual(r.selected,[])
})
test('Shift click selects 150 files in one synchronous operation',()=>{
 const a=toggleRows(paths,[],'',paths[0]);const b=toggleRows(paths,a.selected,a.anchor,paths[149],true)
 assert.equal(b.selected.length,150);assert.equal(b.anchor,paths[0])
})
test('reverse Shift range, select all and invert do not duplicate paths',()=>{
 const a=toggleRows(paths,[],'',paths[149]);const b=toggleRows(paths,a.selected,a.anchor,paths[0],true)
 assert.equal(b.selected.length,150);assert.equal(new Set(b.selected).size,150)
 assert.equal(selectVisible(paths,b.selected).length,2000)
 assert.equal(selectVisible(paths,paths,'invert').length,0)
})
test('selecting filtered rows preserves selections outside that filter',()=>{
 assert.deepEqual(selectVisible(['a','b'],['z'],'all'),['z','a','b'])
 assert.deepEqual(selectVisible(['a','b'],['a','b','z'],'none'),['z'])
})

test('metadata paths can be labelled without being previewed as text',()=>{
 const meta={items:[{id:'default'},{id:'keep'}],assignments:{'.git':'keep','nested/.svn':'keep','.git/specific':'default'}}
 assert.equal(fileGroup(meta,'.git/config'),'keep')
 assert.equal(fileGroup(meta,'nested\\.svn\\wc.db'),'keep')
 assert.equal(fileGroup(meta,'.git/specific/file'),'default')
 assert.equal(fileGroup(meta,'.gitignore'),'default')
 assert.ok(metadataPath('.git'));assert.ok(metadataPath('nested/.GIT/config'))
 assert.ok(!metadataPath('.gitignore'));assert.ok(!metadataPath('.github/workflows/test.yml'))
})
