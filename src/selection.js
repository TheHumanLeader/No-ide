// Selection is synchronous and independent of diff/network requests.
export function toggleRows(paths, selected, anchor, path, shift=false, checked=null) {
  const items = new Set(selected), end = paths.indexOf(path), start = paths.indexOf(anchor)
  if (end < 0) return {selected:[...items],anchor}
  const next = checked ?? !items.has(path)
  for (const p of shift && start >= 0 ? paths.slice(Math.min(start,end),Math.max(start,end)+1) : [path]) {
    if (next) items.add(p); else items.delete(p)
  }
  return {selected:[...items],anchor:shift && start>=0 ? anchor : path}
}
export function selectVisible(paths, selected, mode='all') {
  const out = new Set(selected)
  for (const p of paths) { if(mode==='none'||(mode==='invert'&&out.has(p)))out.delete(p);else out.add(p) }
  return [...out]
}

// Must match Rust groups::path_key / Groups::of. No disk or repository command.
export function groupKey(path) {
 return String(path ?? '').replaceAll('\\','/').split('/').filter(x=>x && x!=='.').join('/')
}
export function fileGroup(meta, path, original=null) {
 const has=id=>(meta.items||[]).some(g=>g.id===id)
 const assigned=key=>{
  const a=meta.assignments||{}, raw=Object.hasOwn(a,key)?a[key]:a[key.replaceAll('/','\\')]
  return has(raw)?raw:null
 }
 let key=groupKey(path)
 const exact=assigned(key) || (original!=null?assigned(groupKey(original)):null)
 if(exact)return exact
 while(key.includes('/')) {key=key.slice(0,key.lastIndexOf('/'));const id=assigned(key);if(id)return id}
 return 'default'
}
export function metadataPath(path) {
 return String(path).replaceAll('\\','/').split('/').some(p=>['.git','.svn'].includes(p.replace(/[. ]+$/,'').toLowerCase()))
}
