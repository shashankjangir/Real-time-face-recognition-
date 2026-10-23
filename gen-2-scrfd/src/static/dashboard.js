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
function adaptFeed() {
  const feed = $("feed");
  if (feed && feed.naturalWidth > 0 && feed.naturalHeight > 0) {
    const ratio = `${feed.naturalWidth} / ${feed.naturalHeight}`;
    const stages = document.querySelectorAll(".camera-stage");
    stages.forEach(st => st.style.aspectRatio = ratio);
    document.documentElement.style.setProperty("--feed-aspect", ratio);
  }
}
$("feed").addEventListener("load", () => {
  if (!paused) {
    $("feed").hidden = false;
    $("feed-empty").hidden = true;
    text("feed-label", "CAM 01 · LIVE");
    adaptFeed();
  }
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
    if (typeof data.quality_threshold === "number") {
      const serverVal = Math.round(data.quality_threshold * 100) / 100;
      lastConfirmedThreshold = serverVal;
      const knob = $("quality-knob");
      if (document.activeElement !== knob && Math.abs(currentThreshold - serverVal) > 0.005) {
        setQualityThreshold(serverVal, false);
      }
    }
    if (Array.isArray(camera.resolution) && camera.resolution.length === 2 && camera.resolution[0] > 0 && camera.resolution[1] > 0) {
      const stage = $("camera-stage");
      if (stage && (!stage.style.aspectRatio || stage.style.aspectRatio === "auto")) {
        stage.style.aspectRatio = `${camera.resolution[0]} / ${camera.resolution[1]}`;
      }
    }
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
let currentThreshold = parseFloat(document.body.dataset.qualityThreshold) || 0.70;
let lastConfirmedThreshold = currentThreshold;
let lastQualityData = null;

function setQualityThreshold(val, syncBackend = true) {
  val = Math.max(0.55, Math.min(0.70, Math.round(val * 100) / 100));
  currentThreshold = val;
  const formatted = val.toFixed(2);
  const knob = $("quality-knob");
  if (knob && knob.value !== formatted) knob.value = formatted;
  const knobVal = $("quality-knob-value");
  if (knobVal) text("quality-knob-value", formatted);
  const req = $("quality-required");
  if (req) text("quality-required", "Required: " + formatted);
  const marker = $("quality-marker");
  if (marker) marker.style.left = (val * 100) + "%";
  document.body.dataset.qualityThreshold = formatted;

  if (lastQualityData && typeof lastQualityData.score === "number") {
    text("quality-state", lastQualityData.score >= val ? "READY TO CAPTURE" : "ADJUST CAPTURE");
  }

  if (syncBackend) {
    const prevConfirmed = lastConfirmedThreshold;
    api("/api/config/quality", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({threshold: val})
    }).then(() => {
      lastConfirmedThreshold = val;
      try { localStorage.setItem("face_access_quality_threshold", formatted); } catch {}
    }).catch(err => {
      text("form-status", "Quality threshold save failed: " + err.message);
      setQualityThreshold(prevConfirmed, false);
    });
  }
}

const knobEl = $("quality-knob");
if (knobEl) {
  knobEl.addEventListener("input", e => setQualityThreshold(parseFloat(e.target.value), false));
  knobEl.addEventListener("change", e => setQualityThreshold(parseFloat(e.target.value), true));
}

try {
  const savedThresh = localStorage.getItem("face_access_quality_threshold");
  if (savedThresh) {
    const num = parseFloat(savedThresh);
    if (!isNaN(num) && num >= 0.55 && num <= 0.70) setQualityThreshold(num, true);
  }
} catch {}

let smoothedQualityScore = null;

function renderQuality(data, isManual = true) {
  lastQualityData = data;
  const scoreNum = typeof data.score === "number" ? data.score : null;
  text("quality-score", scoreNum !== null ? number(scoreNum, 2) : "—");
  const isReady = scoreNum !== null ? scoreNum >= currentThreshold : !!data.ready;
  const stateEl = $("quality-state");
  if (stateEl) {
    if (scoreNum !== null) {
      stateEl.textContent = isReady ? "READY TO CAPTURE" : "ADJUST CAPTURE";
      stateEl.classList.toggle("is-ready", isReady);
      stateEl.classList.toggle("is-adjust", !isReady);
    } else {
      stateEl.textContent = data.face_count === 0 ? "NO FACE" : (data.face_count > 1 ? "MULTIPLE FACES" : "NOT CHECKED");
      stateEl.classList.remove("is-ready", "is-adjust");
    }
  }
  const fill = $("quality-fill");
  if (fill) fill.style.width = Math.max(0, Math.min(100, (scoreNum || 0) * 100)) + "%";
  for (const key of ["sharpness", "brightness", "size"]) {
    const component = (data.components || {})[key];
    text("q-" + key, component ? number(component.value, key === "size" ? 0 : 1) + " " + component.unit : "—");
  }
  if (data.guidance && data.guidance.length) {
    $("quality-tips").replaceChildren(...data.guidance.map(tip => {const li = document.createElement("li"); li.textContent = tip; return li;}));
  }
  if (isManual) {
    text("quality-time", "Checked " + new Date().toLocaleTimeString() + ". This result describes that capture only.");
  }
}

let qualityPollTimer = null;
async function pollLiveQuality() {
  if (!paused && !document.hidden) {
    try {
      const data = await api("/api/quality/live");
      if (data && (data.status === "success" || data.status === "no_frame")) {
        if (typeof data.score === "number") {
          smoothedQualityScore = smoothedQualityScore === null
            ? data.score
            : (smoothedQualityScore * 0.72 + data.score * 0.28);
          renderQuality({ ...data, score: smoothedQualityScore }, false);
          text("quality-time", "Live camera active · " + Math.round(smoothedQualityScore * 100) + "% quality score");
        } else {
          smoothedQualityScore = null;
          renderQuality({ ...data, score: null }, false);
          text("quality-time", (data.guidance && data.guidance[0]) || "Position yourself in front of the camera.");
        }
      }
    } catch {}
  }
  qualityPollTimer = setTimeout(pollLiveQuality, 450);
}
pollLiveQuality();

function updateQualityGlide() {
  const card = $("quality-card");
  const initAnchor = $("quality-anchor-initial");
  const targetAnchor = $("quality-anchor-enrollment");
  if (!card || !initAnchor || !targetAnchor) return;

  if (window.innerWidth <= 1000) {
    card.style.transform = "";
    return;
  }

  const initRect = initAnchor.getBoundingClientRect();
  const targetRect = targetAnchor.getBoundingClientRect();

  const initPageX = initRect.left + window.scrollX;
  const initPageY = initRect.top + window.scrollY;
  const targetPageX = targetRect.left + window.scrollX;
  const targetPageY = targetRect.top + window.scrollY;

  const deltaX = targetPageX - initPageX;
  const deltaY = targetPageY - initPageY;

  const scrollY = window.scrollY;
  const scrollStart = Math.max(0, initAnchor.offsetTop - 40);
  const scrollEnd = Math.max(scrollStart + 80, targetAnchor.offsetTop - 140);

  const rawT = (scrollY - scrollStart) / (scrollEnd - scrollStart);
  const t = Math.max(0, Math.min(1, rawT));

  const ease = 0.5 - 0.5 * Math.cos(Math.PI * t);

  const curX = deltaX * ease;
  const curY = deltaY * ease;

  card.style.transform = `translate3d(${curX.toFixed(2)}px, ${curY.toFixed(2)}px, 0)`;

  const cameraShell = $("camera-shell");
  if (cameraShell && cameraShell.classList.contains("is-floating")) {
    if (!dockPosition) {
      if (t > 0.08) {
        cameraShell.style.left = "24px";
        cameraShell.style.right = "auto";
        cameraShell.style.transform = "none";
      } else {
        cameraShell.style.left = "50%";
        cameraShell.style.right = "auto";
        cameraShell.style.transform = "translateX(-50%)";
      }
      const streamScale = 1.0 - (0.22 * ease);
      cameraShell.style.setProperty("--dock-scale", streamScale.toFixed(3));
    }
  }
}

window.addEventListener("scroll", () => requestAnimationFrame(updateQualityGlide), {passive: true});
window.addEventListener("resize", () => requestAnimationFrame(updateQualityGlide));
requestAnimationFrame(updateQualityGlide);

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
let historyVisibleLimit = 10;
let allRecentLogs = [];
let lastHistorySig = "";
let lastRenderedLimit = 10;

function formatLogTime(timestamp) {
  const stamp = new Date(timestamp);
  if (isNaN(stamp.getTime())) return timestamp;
  const now = new Date();
  const isToday = stamp.getFullYear() === now.getFullYear() &&
                  stamp.getMonth() === now.getMonth() &&
                  stamp.getDate() === now.getDate();
  const timePart = stamp.toLocaleTimeString([], {hour: "2-digit", minute: "2-digit", second: "2-digit"});
  if (isToday) return timePart;
  const datePart = stamp.toLocaleDateString([], {month: "short", day: "numeric"});
  return `${datePart}, ${timePart}`;
}

function stackRecentLogs(logs, maxCount) {
  const stacked = [];
  for (const log of logs) {
    const decision = (log.decision || (log.status === "verified" ? "allow" : "deny")).toUpperCase();
    let name = (log.name || "Unknown").trim();
    const reason = log.reason || "";
    const outcome = log.action_outcome || "";
    const last = stacked[stacked.length - 1];

    if (last && last.name === name && last.decision === decision && last.reason === reason && last.action_outcome === outcome) {
      last.count += 1;
    } else {
      stacked.push({
        ...log,
        name,
        decision,
        reason,
        action_outcome: outcome,
        count: 1
      });
      if (typeof maxCount === "number" && stacked.length >= maxCount) break;
    }
  }

  return stacked;
}

function renderHistory(logs) {
  const historyList = $("history-list");
  if (!historyList) return;
  const showMoreBtn = $("history-show-more");

  if (!logs || !logs.length) {
    emptyHistory("No decisions recorded in this period.");
    text("history-status", "No decisions found for the selected filter.");
    if (showMoreBtn) showMoreBtn.hidden = true;
    return;
  }

  const allStacked = stackRecentLogs(logs);
  const displayed = allStacked.slice(0, historyVisibleLimit);

  historyList.replaceChildren();

  for (const item of displayed) {
    const row = document.createElement("div");
    row.className = "phone-history-row";

    const avatar = document.createElement("div");
    const isAllow = item.decision === "ALLOW";
    avatar.className = "phone-row-avatar " + (isAllow ? "allow" : "deny");
    avatar.innerHTML = isAllow
      ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg>'
      : '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>';

    const main = document.createElement("div");
    main.className = "phone-row-main";

    const title = document.createElement("div");
    title.className = "phone-row-title";

    const nameEl = document.createElement("span");
    nameEl.className = "phone-row-name";
    nameEl.textContent = item.count > 1 ? `${item.name} (${item.count} events)` : item.name;

    const badge = document.createElement("span");
    badge.className = "phone-row-badge " + (isAllow ? "allow" : "deny");
    badge.textContent = item.decision;

    title.append(nameEl, badge);

    const sub = document.createElement("div");
    sub.className = "phone-row-sub";
    sub.textContent = `${human(item.reason)} · ${human(item.action_outcome)}`;

    main.append(title, sub);

    const meta = document.createElement("div");
    meta.className = "phone-row-time";
    meta.textContent = formatLogTime(item.timestamp);

    row.append(avatar, main, meta);
    historyList.append(row);
  }

  const remaining = allStacked.length - displayed.length;
  if (showMoreBtn) {
    if (remaining > 0) {
      showMoreBtn.hidden = false;
      showMoreBtn.textContent = `Show more decisions (${remaining} remaining)`;
    } else {
      showMoreBtn.hidden = true;
    }
  }

  text("history-status", `Showing ${displayed.length} of ${allStacked.length} activity groups. Export CSV includes full audit log.`);
}

async function loadHistory() {
  const requestId = ++historyRequest, query = historyQuery(); query.set("limit", "200");
  try {
    const data = await api("/api/logs?" + query); if (requestId !== historyRequest) return;
    const logs = data.logs || [];
    allRecentLogs = logs;

    const sig = logs.map(l => `${l.id || l.timestamp}-${l.status}-${l.action_outcome}`).join("|");
    if (sig === lastHistorySig && historyVisibleLimit === lastRenderedLimit) {
      return;
    }
    lastHistorySig = sig;
    lastRenderedLimit = historyVisibleLimit;

    renderHistory(logs);
  } catch (error) {
    if (requestId !== historyRequest) return;
    emptyHistory("History is unavailable.");
    text("history-status", error.message);
    const showMoreBtn = $("history-show-more");
    if (showMoreBtn) showMoreBtn.hidden = true;
  }
}

function emptyHistory(message) {
  const historyList = $("history-list");
  if (!historyList) return;
  const empty = document.createElement("div");
  empty.className = "phone-history-empty";
  empty.textContent = message;
  historyList.replaceChildren(empty);
}

function resetHistoryView() {
  historyVisibleLimit = 10;
  lastRenderedLimit = -1;
  loadHistory();
}

const showMoreBtn = $("history-show-more");
if (showMoreBtn) {
  showMoreBtn.addEventListener("click", () => {
    historyVisibleLimit += 10;
    renderHistory(allRecentLogs);
  });
}

$("refresh-history").addEventListener("click", resetHistoryView);
$("history-hours").addEventListener("change", resetHistoryView);
let searchTimer; $("history-name").addEventListener("input", () => { clearTimeout(searchTimer); searchTimer = setTimeout(resetHistoryView, 350); });
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
let docked = false, dockPosition = null, drag = null, dockDismissed = false;
const dockDismissBtn = $("dock-dismiss");

function setCameraDock(enabled) {
  if (document.fullscreenElement) return;
  if (enabled !== docked) {
    if (enabled) cameraSlot.style.minHeight = cameraSlot.getBoundingClientRect().height + "px";
    cameraShell.classList.toggle("is-floating", enabled);
    document.documentElement.classList.toggle("has-camera-dock", enabled);
    if (dockDismissBtn) dockDismissBtn.hidden = !enabled;
    adaptFeed();
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
  if (visible > box.height * 0.7) {
    dockDismissed = false;
  }
  const feedEl = $("feed");
  const feedAvailable = !paused && feedEl && !feedEl.hidden;
  const editingInsideEnrollment = document.activeElement && document.activeElement.matches("input, select, textarea, button") && document.activeElement.closest("#enrollment");
  const editingOnMobile = innerWidth <= 700 && document.activeElement && document.activeElement.matches("input, select, textarea");

  const shouldFloat = !dockDismissed && feedAvailable && !editingInsideEnrollment && !editingOnMobile && visible < Math.min(box.height * .5, innerHeight * .4);
  setCameraDock(shouldFloat);
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
const voiceGenderSelect = $("voice-gender");
if (voiceGenderSelect) {
  try {
    const savedGender = localStorage.getItem("face_access_voice_gender");
    if (savedGender === "male" || savedGender === "female") {
      voiceGenderSelect.value = savedGender;
      announcements.setGender(savedGender);
    }
  } catch {}
  voiceGenderSelect.addEventListener("change", e => {
    const val = e.target.value === "male" ? "male" : "female";
    announcements.setGender(val);
    try { localStorage.setItem("face_access_voice_gender", val); } catch {}
    if (announcements.enabled) {
      announcements.say(val === "male" ? "Man voice selected." : "Woman voice selected.", true);
    }
  });
}
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

if (dockDismissBtn) {
  dockDismissBtn.addEventListener("click", e => {
    e.stopPropagation();
    dockDismissed = true;
    setCameraDock(false);
  });
}
