"use strict";
// Speech is opt-in per browser page; use installed local voices only.
class VoiceAnnouncements {
  constructor(host, status, now = () => performance.now()) {
    this.host = host; this.status = status; this.now = now;
    this.enabled = false; this.last = new Map(); this.quietUntil = 0;
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
    const voices = synth.getVoices().filter(v => v.localService);
    const voice = voices.find(v => v.lang.startsWith("en")) || voices[0];
    if (!voice) { this.status("No local voice available yet. Install or enable a system speech voice."); return false; }
    if (!priority && (synth.speaking || synth.pending)) return false;
    if (priority) synth.cancel();
    const utterance = new this.host.SpeechSynthesisUtterance(message);
    utterance.voice = voice; utterance.lang = voice.lang;
    utterance.onerror = event => { if (!["canceled", "interrupted"].includes(event.error)) this.status("Speech failed. Check the browser voice and audio settings."); };
    try { synth.speak(utterance); this.status(message); return true; }
    catch { this.status("Speech unavailable. Check browser audio settings."); return false; }
  }
  recognitions(faces) {
    if (!this.enabled || this.now() < this.quietUntil) return;
    const now = this.now(), candidates = new Map();
    for (const face of faces || []) {
      const known = face.recognized && face.identity_id != null;
      candidates.set(known ? "id:" + face.identity_id : "unknown", known ? face.name + ", recognised." : "Unknown.");
    }
    for (const [key, stamp] of this.last) if (now - stamp >= 10000) this.last.delete(key);
    const fresh = [...candidates].filter(([key]) => !this.last.has(key));
    // Bound utterance length; remaining people can be announced on the next poll.
    const batch = fresh.slice(0, 4);
    if (batch.length && this.say(batch.map(([,message]) => message).join(" ")))
      for (const [key] of batch) this.last.set(key, now);
  }
  enrolled(name) {
    this.quietUntil = this.now() + 4000;
    this.say(name + ", enrolled.", true);
  }
}
