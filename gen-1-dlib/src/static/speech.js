"use strict";
// Speech is opt-in per browser page; use installed local voices only.
class VoiceAnnouncements {
  constructor(host, status, now = () => performance.now()) {
    this.host = host; this.status = status; this.now = now;
    this.enabled = false; this.gender = "female"; this.last = new Map(); this.quietUntil = 0;
  }
  setGender(gender) {
    this.gender = gender === "male" ? "male" : "female";
  }
  getVoice() {
    const synth = this.host.speechSynthesis;
    if (!synth || !synth.getVoices) return null;
    const localVoices = (synth.getVoices() || []).filter(v => v.localService);
    if (!localVoices.length) return null;
    const enVoices = localVoices.filter(v => v.lang && v.lang.startsWith("en"));
    const pool = enVoices.length ? enVoices : localVoices;

    const isMale = this.gender === "male";
    const maleRegex = /male|man|david|mark|george|guy|ravi|richard|james|alex|fred/i;
    const femaleRegex = /female|woman|zira|susan|jenny|samantha|victoria|karen|kendra|heera|hazel|aria/i;
    const targetRegex = isMale ? maleRegex : femaleRegex;

    return pool.find(v => targetRegex.test(v.name)) || pool[0];
  }
  cancel() { if (this.host.speechSynthesis) this.host.speechSynthesis.cancel(); }
  toggle() {
    if (this.enabled) { this.enabled = false; this.cancel(); this.status("Voice is off."); return; }
    if (!this.host.speechSynthesis || !this.host.SpeechSynthesisUtterance) {
      this.status("Speech is unavailable in this browser."); return;
    }
    this.enabled = true; this.last.clear(); this.say("Voice announcements enabled.", true);
  }
  say(message, priority = false) {
    if (!this.enabled) return false;
    const synth = this.host.speechSynthesis;
    const voice = this.getVoice();
    if (!voice) { this.status("No local voice available yet. Install or enable a system speech voice."); return false; }
    if (!priority && (synth.speaking || synth.pending)) return false;
    if (priority) synth.cancel();
    const utterance = new this.host.SpeechSynthesisUtterance(message);
    utterance.voice = voice; utterance.lang = voice.lang || "en-US";
    if (this.gender === "male") {
      utterance.pitch = 0.85;
      utterance.rate = 0.95;
    } else {
      utterance.pitch = 1.15;
      utterance.rate = 1.0;
    }
    utterance.onerror = event => { if (!["canceled", "interrupted"].includes(event.error)) this.status("Speech failed. Check the browser voice and audio settings."); };
    try { synth.speak(utterance); this.status(message); return true; }
    catch { this.status("Speech unavailable. Check browser audio settings."); return false; }
  }
  recognitions(faces) {
    if (!this.enabled || this.now() < this.quietUntil) return;
    const now = this.now(), candidates = new Map();
    for (const face of faces || []) {
      const known = face.recognized && face.identity_id != null;
      const key = known ? "id:" + face.identity_id : (face.name ? "name:" + face.name : "unknown");
      const msg = known ? face.name + ", recognised." : (face.name || "Unknown") + ".";
      candidates.set(key, msg);
    }
    // Change of persons: clear absent persons so re-entry announces immediately
    for (const key of [...this.last.keys()]) {
      if (!candidates.has(key)) this.last.delete(key);
    }
    // Re-announce after 10 seconds if continuously present
    for (const [key, stamp] of this.last) {
      if (now - stamp >= 10000) this.last.delete(key);
    }
    const fresh = [...candidates].filter(([key]) => !this.last.has(key));
    const batch = fresh.slice(0, 4);
    if (batch.length && this.say(batch.map(([,message]) => message).join(" ")))
      for (const [key] of batch) this.last.set(key, now);
  }
  enrolled(name) {
    this.quietUntil = this.now() + 4000;
    this.say(name + ", enrolled.", true);
  }
}
