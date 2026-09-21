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
