"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = fs.readFileSync(path.join(__dirname, "../src/static/dashboard.js"), "utf8");
const elements = new Map();
const element = id => {
  if (!elements.has(id)) elements.set(id, {value: "", style: {}, addEventListener() {}, focus() { this.focused = true; }});
  return elements.get(id);
};
const requests = [];
const saved = new Map();
let failRequest = false;
const context = vm.createContext({
  document: {body: {dataset: {qualityThreshold: "0.70"}}},
  $: element,
  setEnrollmentStep() {},
  localStorage: {getItem: key => saved.get(key) ?? null, setItem: (key,value) => saved.set(key,value)},
  text: (id, value) => { element(id).textContent = value; },
  api: async (url, options) => {
    requests.push({url, ...options});
    if (failRequest) throw new Error("Administrator authentication required.");
  }
});
const credentials = source.slice(source.indexOf("function credentials()"), source.indexOf("function setBusy("));
const quality = source.slice(source.indexOf("let currentThreshold ="), source.indexOf('const knobEl ='));
vm.runInContext(credentials + quality, context);

(async () => {
  await context.setQualityThreshold(0.55);
  assert.equal(requests.length, 0);
  assert.equal(element("admin-token").focused, true);
  assert.equal(element("quality-knob").value, "0.70");
  assert.match(element("quality-setting-status").textContent, /Enter the enrollment password/);

  element("admin-token").value = "test-token";
  await context.setQualityThreshold(0.62);
  assert.equal(requests.length, 1);
  assert.equal(requests[0].url, "/api/config/quality");
  assert.equal(requests[0].method, "POST");
  assert.equal(requests[0].headers.Authorization, "Bearer test-token");
  assert.equal(JSON.parse(requests[0].body).threshold, 0.62);
  assert.equal(element("quality-knob").value, "0.62");

  assert.equal(saved.get("face_access_quality_threshold"), "0.62");
  const reloadContext = vm.createContext({
    document: {body: {dataset: {qualityThreshold: "0.70"}}}, $: element,
    text: (id,value) => { element(id).textContent = value; },
    localStorage: {getItem: key => saved.get(key) ?? null},
    api: () => { throw new Error("Reload must not change the station setting"); }
  });
  vm.runInContext(credentials + quality, reloadContext);
  assert.equal(element("quality-restore").hidden, false);
  assert.match(element("quality-restore").textContent, /0.62/);
  failRequest = true;
  await context.setQualityThreshold(0.55);
  assert.equal(element("quality-knob").value, "0.62");
  assert.match(element("quality-setting-status").textContent, /Administrator authentication required/);

  await context.setQualityThreshold(0.65, false);
  assert.equal(requests.length, 2);
  assert.equal(element("quality-knob").value, "0.65");
  console.log("Quality control tests passed: credentials, authenticated request, rollback, read-only update.");
})().catch(error => { console.error(error); process.exitCode = 1; });
