"use strict";
const $ = id => document.getElementById(id);
const text = (id, value) => { $(id).textContent = value; };
const number = (value, digits = 1) => typeof value === "number" && Number.isFinite(value) ? value.toFixed(digits) : "—";
const actionLabels = {not_configured: "No hardware action configured", not_requested: "No action requested", succeeded: "Action completed", failed: "Action failed", cooldown_suppressed: "Action cooldown"};
const human = value => actionLabels[value] || (value || "Not recorded").replaceAll("_", " ");
let paused = false, busy = false, identities = [], historyRequest = 0;
async function api(url, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 20000);
  try {
    const response = await fetch(url, {...options, signal: controller.signal, cache: "no-store"});
    const data = await response.json();
    if (!response.ok || data.status === "error" || data.status === "unhealthy") throw new Error(data.message || "The station could not complete this request.");
    return data;
  } catch (error) {
    if (error.name === "AbortError") throw new Error("The station took too long to respond. Check the camera and try again.");
    throw error;
  } finally { clearTimeout(timer); }
}
function feedMessage(title, detail) {
  $("feed").hidden = true; $("feed-empty").hidden = false;
  text("feed-empty-title", title); text("feed-empty-text", detail);
}
function connectFeed() {
  if (paused) return;
  feedMessage("Connecting to your camera", "Waiting for the station's live feed.");
  $("feed").src = "/stream.mjpg?t=" + Date.now();
}
$("feed").addEventListener("load", () => {
  if (!paused) { $("feed").hidden = false; $("feed-empty").hidden = true; text("feed-label", "CAM 01 · LIVE"); }
});
$("feed").addEventListener("error", () => {
  if (!paused) { feedMessage("Camera feed unavailable", "Check the camera connection and station status, then reconnect."); text("feed-label", "CAM 01 · UNAVAILABLE"); }
});
$("retry").addEventListener("click", () => { if (paused) togglePause(); else connectFeed(); });
function togglePause() {
  paused = !paused; $("pause").setAttribute("aria-pressed", String(paused));
  text("pause", paused ? "Resume view" : "Pause view");
  if (paused) {
    $("feed").removeAttribute("src"); text("feed-label", "CAM 01 · VIEW PAUSED");
    feedMessage("Live view paused", "Recognition continues on the station. Resume whenever you're ready.");
    text("retry", "Resume view");
  } else { text("retry", "Reconnect"); connectFeed(); }
}
$("pause").addEventListener("click", togglePause);
$("fullscreen").addEventListener("click", async () => {
  try { if (document.fullscreenElement) await document.exitFullscreen(); else await $("camera-shell").requestFullscreen(); }
  catch { text("system-message", "Full screen is not available in this browser."); $("system-message").hidden = false; }
});
async function updateStats() {
  try {
    const data = await api("/api/stats");
    text("last-updated", "Updated " + new Date().toLocaleTimeString());
    text("connection", "Station online ●"); $("system-message").hidden = true;
    text("identities-open", data.identities_enrolled);
    const metrics = data.telemetry || {};
    text("capture-fps", number(metrics.capture_fps ?? data.fps));
    text("recognition-fps", number(metrics.recognition_fps)); text("latency", number(data.avg_latency_ms, 0));
    text("jpeg-fps", number(metrics.unique_jpeg_fps) + " FPS");
    const counts = metrics.counts || {};
    text("drops", [counts.dropped, counts.stale, counts.out_of_order].map(v => v ?? "—").join(" / "));
    text("metric-note", "Rates since startup. Capture and recognition are measured separately.");
    const camera = data.camera || {};
    text("camera-description", (camera.backend === "Picamera2Backend" ? "Pi Camera" : camera.backend === "SyntheticBackend" ? "Simulation · access disabled" : "Camera") + (camera.resolution ? " / " + camera.resolution.join(" × ") : ""));
    text("focus-state", camera.autofocus ? "Continuous autofocus enabled" : "Autofocus not reported by this camera");
  } catch (error) {
    text("connection", "Station unavailable ○");
    if ($("last-updated").textContent.startsWith("Updated ") && !$("last-updated").textContent.endsWith(" · stale"))
      text("last-updated", $("last-updated").textContent + " · stale");
    text("system-message", "Station unavailable. " + error.message); $("system-message").hidden = false;
    ["capture-fps", "recognition-fps", "latency", "jpeg-fps", "drops", "identities-open"].forEach(id => text(id, "—"));
    text("metric-note", "Measurements unavailable until the station reconnects.");
    text("focus-state", "Focus mode unavailable"); text("camera-description", "Station unavailable");
  }
}
function credentials() {
  const token = $("admin-token").value.trim();
  if (!token) { $("admin-token").focus(); throw new Error("Enter the enrollment password first."); }
  return {"Authorization": "Bearer " + token, "Content-Type": "application/json"};
}
function setBusy(value, action = "") {
  busy = value; $("enroll-button").disabled = value; $("quality-check").disabled = value;
  $("enroll-form").setAttribute("aria-busy", String(value));
  if (value) text("form-status", action);
}
function renderQuality(data) {
  text("quality-score", number(data.score, 2));
  text("quality-state", data.ready ? "READY TO CAPTURE" : "ADJUST CAPTURE");
  $("quality-fill").style.width = Math.max(0, Math.min(100, (data.score || 0) * 100)) + "%";
  for (const key of ["sharpness", "brightness", "size"]) {
    const component = (data.components || {})[key];
    text("q-" + key, component ? number(component.value, key === "size" ? 0 : 1) + " " + component.unit : "—");
  }
  $("quality-tips").replaceChildren(...(data.guidance || []).map(tip => {const li = document.createElement("li"); li.textContent = tip; return li;}));
  text("quality-time", "Checked " + new Date().toLocaleTimeString() + ". This result describes that capture only.");
}
$("quality-check").addEventListener("click", async () => {
  if (busy) return;
  try {
    const headers = credentials(); setBusy(true, "Checking the current camera frame…");
    const data = await api("/api/enrollment/quality", {method:"POST", headers});
    renderQuality(data); text("form-status", data.ready ? "This capture meets the quality threshold. Enrollment will validate a fresh frame." : "See the quality readings and guidance before trying again.");
  } catch (error) { renderQuality({score:null, ready:false, components:{}, guidance:[error.message]}); text("form-status", error.message); text("quality-state", "CHECK UNAVAILABLE"); text("quality-time", "No new capture was measured."); }
  finally { setBusy(false); }
});
$("show-token").addEventListener("click", () => {
  const show = $("admin-token").type === "password"; $("admin-token").type = show ? "text" : "password";
  text("show-token", show ? "Hide" : "Show"); $("show-token").setAttribute("aria-pressed", String(show));
});
$("enroll-form").addEventListener("submit", async event => {
  event.preventDefault(); if (busy) return;
  try {
    const headers = credentials(), name = $("person-name").value.trim();
    if (!name) throw new Error("Enter the identity name.");
    setBusy(true, "Validating a fresh capture and saving the identity…");
    const data = await api("/api/enroll", {method:"POST", headers, body:JSON.stringify({name})});
    text("form-status", data.message + ". Capture quality: " + number(data.quality_score, 3) + ".");
    announcements.enrolled(name);
    $("person-name").value = "";
    await updateStats();
  } catch (error) { text("form-status", error.message); }
  finally { setBusy(false); }
});
function historyQuery() {
  const query = new URLSearchParams({hours: $("history-hours").value});
  const name = $("history-name").value.trim(); if (name) query.set("name", name);
  $("export").href = "/api/csv?" + query;
  return query;
}
async function loadHistory() {
  const requestId = ++historyRequest, query = historyQuery(); query.set("limit", "100");
  try {
    const data = await api("/api/logs?" + query); if (requestId !== historyRequest) return;
    $("history-body").replaceChildren();
    for (const log of data.logs) {
      const row = document.createElement("tr");
      const stamp = new Date(log.timestamp);
      const values = [isNaN(stamp) ? log.timestamp : stamp.toLocaleString(), log.name,
        (log.decision || (log.status === "verified" ? "allow" : "deny")).toUpperCase(), human(log.reason), human(log.action_outcome)];
      values.forEach((value, index) => { const td = document.createElement("td");
        if (index === 2) { const badge = document.createElement("span"); badge.className = "decision" + (value === "ALLOW" ? " allow" : ""); badge.textContent = value; td.append(badge); }
        else td.textContent = value; row.append(td); });
      $("history-body").append(row);
    }
    if (!data.logs.length) emptyHistory("No decisions in this period.");
    text("history-status", "Showing " + data.logs.length + " most recent decisions (up to 100). CSV includes the full selected period.");
  } catch (error) { if (requestId !== historyRequest) return; emptyHistory("History is unavailable."); text("history-status", error.message); }
}
function emptyHistory(message) { const row = document.createElement("tr"), cell = document.createElement("td"); cell.colSpan = 5; cell.className = "table-empty"; cell.textContent = message; row.append(cell); $("history-body").replaceChildren(row); }
$("refresh-history").addEventListener("click", loadHistory);
$("history-hours").addEventListener("change", loadHistory);
let searchTimer; $("history-name").addEventListener("input", () => { clearTimeout(searchTimer); searchTimer = setTimeout(loadHistory, 350); });
function renderIdentities() {
  const query = $("identity-search").value.toLowerCase();
  const matches = identities.filter(identity => identity.name.toLowerCase().includes(query));
  $("identity-list").replaceChildren(...matches.map(identity => { const li = document.createElement("li"), name = document.createElement("span"), note = document.createElement("small"); name.textContent = identity.name; note.textContent = "Quality " + number(identity.quality_score, 2); li.append(name, note); return li; }));
  text("identity-status", matches.length + (matches.length === 1 ? " identity" : " identities"));
}
const identityDialog = $("identity-dialog");
let dialogCloseTimer;
function closeIdentities() {
  if (!identityDialog.open || identityDialog.classList.contains("is-closing")) return;
  identityDialog.classList.remove("is-open");
  identityDialog.classList.add("is-closing");
  const closeMs = window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 :
    parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--modal-close-dur")) || 150;
  dialogCloseTimer = setTimeout(() => identityDialog.close(), closeMs);
}
identityDialog.addEventListener("close", () => {
  clearTimeout(dialogCloseTimer);
  identityDialog.classList.remove("is-open", "is-closing");
  $("identities-open").focus({preventScroll:true});
});
identityDialog.addEventListener("cancel", event => { event.preventDefault(); closeIdentities(); });
$("identities-open").addEventListener("click", async () => {
  clearTimeout(dialogCloseTimer);
  identityDialog.classList.remove("is-closing");
  identityDialog.showModal();
  void identityDialog.offsetWidth;
  identityDialog.classList.add("is-open");
  $("identity-search").focus();
  $("identity-search").value = ""; identities = []; $("identity-list").replaceChildren(); text("identity-status", "Loading…");
  try { const data = await api("/api/identities"); identities = data.identities; renderIdentities(); }
  catch (error) { text("identity-status", error.message); }
});
$("identities-close").addEventListener("click", closeIdentities);
$("identity-search").addEventListener("input", renderIdentities);
function clock() { text("clock", new Date().toLocaleTimeString([], {hour12:false})); }
async function poll() { if (!document.hidden) { await updateStats(); await loadHistory(); } setTimeout(poll, 4000); }
clock(); setInterval(clock, 1000); connectFeed(); poll();

// Move the existing image and controls visually; never create another MJPEG client.
const cameraSlot = $("camera-slot"), cameraShell = $("camera-shell");
let docked = false, dockPosition = null, drag = null;
function setCameraDock(enabled) {
  if (document.fullscreenElement) return;
  if (enabled !== docked) {
    if (enabled) cameraSlot.style.minHeight = cameraSlot.getBoundingClientRect().height + "px";
    cameraShell.classList.toggle("is-floating", enabled);
    document.documentElement.classList.toggle("has-camera-dock", enabled);
    if (!enabled) cameraSlot.style.minHeight = "";
    docked = enabled;
    if (!enabled) { cameraShell.style.left = ""; cameraShell.style.top = ""; cameraShell.style.bottom = ""; cameraShell.style.transform = ""; }
    else if (dockPosition) placeDock(dockPosition.x, dockPosition.y);
  }
  if (enabled) document.documentElement.style.setProperty("--camera-dock-space", (cameraShell.getBoundingClientRect().height + 40) + "px");
}
function updateCameraDock() {
  const box = cameraSlot.getBoundingClientRect();
  const visible = Math.max(0, Math.min(box.bottom, innerHeight) - Math.max(box.top, 0));
  const editingOnMobile = innerWidth <= 700 && document.activeElement.matches("input, select, textarea");
  setCameraDock(!editingOnMobile && visible < Math.min(box.height * .5, innerHeight * .4));
}
const cameraObserver = new IntersectionObserver(updateCameraDock, {threshold:[0,.25,.5,.75,1]});
cameraObserver.observe(cameraSlot);
window.addEventListener("resize", updateCameraDock);
document.addEventListener("fullscreenchange", updateCameraDock);
// Keep focused form controls above the dock when navigating with the keyboard.
document.addEventListener("focusin", event => {
  updateCameraDock();
  if (docked && !cameraShell.contains(event.target) && !event.target.closest("dialog")) {
    const box = event.target.getBoundingClientRect();
    if (box.bottom > cameraShell.getBoundingClientRect().top) event.target.scrollIntoView({block:"center", behavior:"instant"});
  }
});
document.addEventListener("focusout", () => requestAnimationFrame(updateCameraDock));

// Drag the header, keeping playback controls separate.
const dragHandle = cameraShell.querySelector(".camera-top");
dragHandle.tabIndex = 0;
dragHandle.setAttribute("aria-label", "Move floating camera: drag or use arrow keys; Home resets position");
dragHandle.title = "Drag to move / Arrow keys to move / Home to reset";
function placeDock(x, y) {
  const box = cameraShell.getBoundingClientRect();
  dockPosition = {x: Math.max(8, Math.min(x, innerWidth-box.width-8)), y: Math.max(8, Math.min(y, innerHeight-box.height-8))};
  Object.assign(cameraShell.style, {left: dockPosition.x+"px", top: dockPosition.y+"px", bottom:"auto", transform:"none"});
}
dragHandle.addEventListener("pointerdown", event => {
  if (!docked || document.fullscreenElement || event.button !== 0) return;
  const box = cameraShell.getBoundingClientRect();
  drag = {id:event.pointerId, x:event.clientX-box.left, y:event.clientY-box.top};
  dragHandle.setPointerCapture(event.pointerId); event.preventDefault();
});
dragHandle.addEventListener("pointermove", event => {
  if (drag && drag.id === event.pointerId && docked && !document.fullscreenElement) placeDock(event.clientX-drag.x, event.clientY-drag.y);
});
for (const type of ["pointerup", "pointercancel", "lostpointercapture"]) dragHandle.addEventListener(type, () => { drag = null; });
dragHandle.addEventListener("keydown", event => {
  if (!docked || document.fullscreenElement) return;
  const delta = {ArrowLeft:[-20,0], ArrowRight:[20,0], ArrowUp:[0,-20], ArrowDown:[0,20]}[event.key];
  const box = cameraShell.getBoundingClientRect();
  if (delta) { event.preventDefault(); placeDock(box.left+delta[0], box.top+delta[1]); }
  if (event.key === "Home") { event.preventDefault(); placeDock((innerWidth-box.width)/2, innerHeight-box.height-16); }
});
window.addEventListener("resize", () => { if (docked && dockPosition && !document.fullscreenElement) placeDock(dockPosition.x, dockPosition.y); });

const announcements = new VoiceAnnouncements(window, message => text("speech-status", message));
$("speech-toggle").addEventListener("click", () => {
  announcements.toggle();
  $("speech-toggle").setAttribute("aria-pressed", String(announcements.enabled));
  text("speech-toggle", announcements.enabled ? "Mute voice" : "Enable voice");
});
document.addEventListener("visibilitychange", () => { if (document.hidden) announcements.cancel(); });
window.addEventListener("pagehide", () => announcements.cancel());
async function pollVoice() {
  if (announcements.enabled && !document.hidden) {
    try { const data = await api("/api/recognition/live"); if (!document.hidden) announcements.recognitions(data.faces); }
    catch { announcements.cancel(); text("speech-status", "Live recognition unavailable; announcements paused."); }
  }
  setTimeout(pollVoice, 700);
}
pollVoice();

// Decorative entrance only; station controls never wait for animation.
if (window.gsap) {
  const motion = gsap.matchMedia();
  motion.add("(prefers-reduced-motion: no-preference)", () => {
    gsap.from(".brand-mark, .focus-mark", {y: 8, duration: .65, ease: "power3.out", clearProps: "transform"});
  });
  document.addEventListener("visibilitychange", () => { if (document.hidden) motion.revert(); });
  window.addEventListener("pagehide", () => motion.revert());
}
