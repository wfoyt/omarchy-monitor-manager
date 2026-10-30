function copy(value) { return JSON.parse(JSON.stringify(value)) }
function size(m) {
  return m.transform % 2 ? {w: m.height / m.scale, h: m.width / m.scale}
                         : {w: m.width / m.scale, h: m.height / m.scale}
}
function bounds(displays) {
  if (!displays.length) return {x: 0, y: 0, w: 1920, h: 1080}
  var x = Infinity, y = Infinity, right = -Infinity, bottom = -Infinity
  displays.forEach(function(m) {
    var s = size(m)
    x = Math.min(x, m.x); y = Math.min(y, m.y)
    right = Math.max(right, m.x + s.w); bottom = Math.max(bottom, m.y + s.h)
  })
  return {x: x, y: y, w: right - x, h: bottom - y}
}
function snap(displays, index, x, y, threshold) {
  var m = displays[index], s = size(m), bx = x, by = y, dx = threshold, dy = threshold
  displays.forEach(function(o, i) {
    if (i === index) return
    var z = size(o)
    var xs = [o.x, o.x + z.w, o.x - s.w, o.x + z.w - s.w]
    var ys = [o.y, o.y + z.h, o.y - s.h, o.y + z.h - s.h]
    xs.forEach(function(v) { if (Math.abs(v-x) < dx) {dx = Math.abs(v-x); bx = v} })
    ys.forEach(function(v) { if (Math.abs(v-y) < dy) {dy = Math.abs(v-y); by = v} })
  })
  return {x: Math.round(bx), y: Math.round(by)}
}
function row(displays) {
  var list = copy(displays), x = 0
  list.sort(function(a,b) {return a.x-b.x})
  list.forEach(function(m) {m.x = x; m.y = 0; x += Math.round(size(m).w)})
  return displays.map(function(m) {return list.filter(function(o){return o.name === m.name})[0]})
}
function resolutions(m) {
  if (!m) return []
  var seen = {}, result = []
  m.modes.forEach(function(mode) {
    var key = mode.width + 'x' + mode.height
    if (!seen[key]) {seen[key] = true; result.push({value:key, label:mode.width + ' × ' + mode.height})}
  })
  return result
}
function rates(m) {
  if (!m) return []
  return m.modes.filter(function(v) {return v.width === m.width && v.height === m.height})
    .sort(function(a,b){return b.rate-a.rate})
    .map(function(v){return {value:String(v.rate), label:formatRate(v.rate) + ' Hz'}})
}
function formatRate(rate) { return String(Math.round(rate*100)/100) }
function scales(m) {
  if (!m) return []
  function gcd(a,b) {while(b) {var t = a % b; a=b; b=t} return a}
  var divisor = gcd(m.width*120, m.height*120), values = [m.scale]
  ;[.75,1,1.25,1.5,1.6,1.75,2,2.5,3,4].forEach(function(s) {
    var k = Math.round(s*120)
    while(k <= 480 && divisor % k !== 0) k++
    var n = k/120
    if(k <= 480 && !values.some(function(v){return Math.abs(v-n)<.0001})) values.push(n)
  })
  return values.sort(function(a,b){return a-b}).map(function(v) {
    return {value:String(v), label:(Math.round(v*1000)/10) + '%' + (v===1 ? ' · native size' : '')}
  })
}
if (typeof module !== 'undefined') module.exports = {copy:copy,size:size,bounds:bounds,snap:snap,row:row,resolutions:resolutions,rates:rates,scales:scales}
