"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const source = fs.readFileSync(path.join(__dirname, "../src/static/dashboard.js"), "utf8");
const context = vm.createContext({Date});
vm.runInContext(source.slice(source.indexOf("function formatLogTime("), source.indexOf("function renderHistory(")), context);
const log = {identity_id:1, name:"Alice", decision:"allow", reason:"identity_matched", action_outcome:"succeeded"};
let groups = context.stackRecentLogs([log, log, {...log, name:"Bob", identity_id:2}, log]);
assert.deepEqual(Array.from(groups, g => g.count), [2,1,1]);
assert.equal(context.stackRecentLogs([log, {...log, action_outcome:"failed"}]).length, 2);
assert.equal(context.stackRecentLogs([log, {...log, identity_id:3}]).length, 2);
assert.equal(context.formatLogTime(new Date(Date.now()-120000).toISOString()), "2 min ago");
assert.equal(context.formatLogTime("invalid"), "invalid");

const box = (left,top,width,height) => ({left,top,width,height,right:left+width,bottom:top+height});
const shell = {style:{}, offsetHeight:400, classList:{contains:()=>false}};
const top = {style:{}, getBoundingClientRect:()=>box(40,-500,800,500)};
const target = {getBoundingClientRect:()=>box(800,100,500,380)};
const card = {style:{}, getBoundingClientRect:()=>box(40,100,700,450)};
const motion = {matches:false, addEventListener(){}};
const layout = vm.createContext({
  $: id => ({"camera-shell":shell,"camera-slot":top,"enrollment-camera-slot":target})[id],
  document:{fullscreenElement:null,querySelector:()=>card,addEventListener(){}},
  window:{matchMedia:()=>motion,addEventListener(){}},
  innerWidth:1440,scrollY:800,requestAnimationFrame:()=>1
});
vm.runInContext(source.slice(source.indexOf("const reducedMotion ="), source.indexOf('$("quality-check").addEventListener')), layout);
layout.updateCameraStreamGlide();
assert.equal(shell.style.width, "500.0px");
assert.match(shell.style.transform, /translate3d/);
layout.innerWidth = 390;
layout.updateCameraStreamGlide();
assert.equal(shell.style.width, "");
assert.equal(shell.style.transform, "");
assert.equal(top.style.minHeight, "");
layout.innerWidth = 1440;
layout.updateCameraStreamGlide();
motion.matches = true;
layout.updateCameraStreamGlide();
assert.equal(shell.style.transform, "");
assert.equal(card.style.transform, "");
console.log("Website tests passed: grouping, relative times, glide, mobile reset, reduced motion.");
