const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const ctx={};vm.createContext(ctx);vm.runInContext(fs.readFileSync(__dirname+'/../Layout.js','utf8'),ctx);
const left={name:'DP-1',width:2560,height:1440,x:0,y:0,scale:1.25,transform:0};
const right={name:'HDMI-A-1',width:1920,height:1080,x:2100,y:30,scale:1,transform:0};
const snap=ctx.snap([left,right],1,2060,10,30);
assert.equal(snap.x,2048);assert.equal(snap.y,0);
const row=ctx.row([left,right]);assert.equal(row[1].x,2048);assert.equal(row[1].y,0);
assert.equal(ctx.size({...left,transform:1}).w,1152);
const box=ctx.bounds([{...left,x:-2048}, {...right,x:0}]);assert.equal(box.x,-2048);assert.equal(box.w,3968);
for(const s of ctx.scales(left)) {
 const n=Number(s.value);assert.ok(Math.abs(left.width/n-Math.round(left.width/n))<.0001);
 assert.ok(Math.abs(left.height/n-Math.round(left.height/n))<.0001);
}
console.log('Layout geometry, snapping, rotation and fractional scales passed.');
