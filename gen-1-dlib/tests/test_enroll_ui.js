"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");
const source = fs.readFileSync(path.join(__dirname,"../src/static/dashboard.js"),"utf8");
const elements = new Map();
function element(id) {
  if (!elements.has(id)) elements.set(id, {value:"", dataset:{}, classList:{toggle(){}},
    parentElement:{before(){}}, closest:()=>element(id+"-field"), before(){}, append(){}, focus(){},
    setAttribute(){}, addEventListener(type,fn){this[type]=fn;}});
  return elements.get(id);
}
let requests = 0, fail = false, settle;
const context = vm.createContext({
  $:element, busy:false,
  document:{createElement:tag=>element(tag === "div" ? "morph" : tag),addEventListener(){}},
  setTimeout:fn=>{settle=fn;return 1;},clearTimeout(){},
  text:(id,value)=>{element(id).textContent=value;},
  number:value=>String(value), announcements:{enrolled(){}}, updateStats:async()=>{},
  credentials:()=>({Authorization:"Bearer test-only"}),
  setBusy:value=>{context.busy=value;},
  api:async(url,options)=>{
    assert.equal(element("morph").dataset.step,"saving");
    assert.equal(context.busy,true);
    requests++; assert.equal(url,"/api/enroll");
    assert.equal(JSON.parse(options.body).name,"Preview");
    if(fail) throw new Error("Invalid password");
    return {message:"Enrolled",quality_score:0.9};
  }
});
vm.runInContext(source.slice(source.indexOf("const enrollButton ="),source.indexOf("function historyQuery()")),context);
const submit=()=>element("enroll-form").submit({preventDefault(){}});
(async()=>{
  await submit(); assert.equal(element("morph").dataset.step,"name");
  await submit(); assert.equal(requests,0);
  element("person-name").value="Preview";
  await submit(); assert.equal(element("morph").dataset.step,"password");
  assert.equal(requests,0);
  element("admin-token").value="test-only";
  await submit(); assert.equal(element("morph").dataset.step,"success");
  assert.equal(requests,1); assert.equal(element("admin-token").value,"");
  settle(); assert.equal(element("morph").dataset.step,"saved");
  await submit(); element("person-name").value="Preview"; await submit();
  fail=true; await submit();
  assert.equal(element("morph").dataset.step,"password");
  assert.equal(element("person-name").value,"Preview");
  assert.match(element("form-status").textContent,/Invalid password/);
  console.log("Enrollment UI tests passed: name, password, server success, retry, credential clearing.");
})().catch(error=>{console.error(error);process.exitCode=1;});
