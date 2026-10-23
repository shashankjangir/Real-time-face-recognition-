# Required modifications

Reviewed: 23 October 2026. This is an implementation checklist; application changes have not been made.

Keep the existing Flask/Jinja, plain CSS/JavaScript, SQLite and local GSAP stack. Implement correctness fixes before visual refinements.

## 1. Protect enrollment settings — High priority

- [ ] Require the existing administrator authentication check for `POST /api/config/quality`, before changing state.
- [ ] Remove the built-in `123456789` enrollment password; reject protected operations when no password is configured.
- [ ] Send administrator credentials from the quality-setting UI.
- [ ] Validate that the request body is an object and the threshold is a finite number within the supported range.
- [ ] Update setup instructions and configuration examples to require an explicitly configured password.

Files: `src/app.py`, `src/config.py`, `src/static/dashboard.js`, `tests/test_dashboard.py`, `tests/test_audit_regressions.py`, `.env.example`, enrollment/setup documentation.

Acceptance: missing or incorrect credentials cannot change the threshold; valid credentials can; malformed requests return a controlled error. Existing explicitly configured passwords continue working.

Evidence: an unauthenticated request changed the threshold to `0.55` and returned HTTP 200 during review. Enrollment itself already requires authentication.

## 2. Make capture readiness server-authoritative — High priority

- [ ] Stop automatically posting a saved browser threshold when the page loads.
- [ ] Read and display the server's current threshold.
- [ ] Require an explicit authenticated save and show saving, success and failure states.
- [ ] Restore the last confirmed value when saving fails.
- [ ] Use the server's quality/readiness response consistently for both the quality panel and form feedback.
- [ ] Treat a changed threshold as requiring a fresh quality check, rather than presenting an old capture as current evidence.
- [ ] Add focused browser/JavaScript tests for failed saves, stale browser settings and conflicting readiness messages.

Files: `src/static/dashboard.js` (threshold logic around line 110), `src/templates/dashboard.html`, API tests and a focused dashboard JavaScript test.

Acceptance: the interface never presents an unsaved threshold as active. Opening another browser tab cannot silently change enrollment policy. Failed saves are visible to the operator.

## 3. Preserve audit history meaning — High priority

- [ ] Prefer individual audit records; if grouping remains, only combine records with equivalent decisions, reasons and hardware action outcomes.
- [ ] Show dates as well as times for multi-day history.
- [ ] Keep unknown-person labels neutral; do not number history groups as though they represent tracked individuals.
- [ ] Label grouped counts as event counts and retain access to full details.
- [ ] Add tests with identical names/decisions but different action outcomes, records from different dates and multiple unknown events.

Files: `src/static/dashboard.js` (`stackRecentLogs` around line 198 and history rendering), dashboard JavaScript tests.

Acceptance: a successful hardware action cannot hide a failed action inside a shared row. Displayed identities, dates and outcomes faithfully represent the underlying records.

## 4. Restore readable, restrained controls — High priority

- [ ] Remove the late continuous gradient/glow/shimmer overrides on primary, outline and camera buttons.
- [ ] Reuse the earlier static control styles and existing color tokens.
- [ ] Verify normal-size button text reaches at least 4.5:1 contrast in normal, hover and focus states.
- [ ] Preserve short hover/press feedback, current modal transitions, visible focus and reduced-motion handling.
- [ ] Do not add an animation library or replace the visual identity.

Files: `src/static/dashboard.css` (overrides around line 262).

Acceptance: routine controls remain readable without perpetual animation. Review normal and reduced-motion modes. The detector reported 2.7:1 for outline-button text; verify actual rendered colors after the fix.

## 5. Keep the camera dock out of the enrollment workflow — Medium priority

- [ ] Disable automatic floating when the camera feed is unavailable.
- [ ] Provide an accessible hide/show or minimize control for the floating panel.
- [ ] Ensure the dock does not cover form fields, validation messages or quality guidance on desktop or mobile.
- [ ] Preserve the single MJPEG image/client and existing keyboard movement behavior.

Files: `src/static/dashboard.js` (`updateCameraDock` around line 369), `src/static/dashboard.css` (floating rules around line 172), `src/templates/dashboard.html`.

Acceptance: inspect enrollment with a working feed and unavailable feed, using keyboard navigation, a narrow viewport and 200% zoom. Hiding the dock must not stop recognition.

## 6. Improve history announcements and heading structure — Medium/Low priority

- [ ] Replace the whole-history live region with a concise new-events status announcement.
- [ ] Avoid rebuilding unchanged history on every poll.
- [ ] Correct the camera-status H1-to-H3 heading jump without changing its visual styling.

Files: `src/templates/dashboard.html` (camera heading around line 55 and history region around line 241), `src/static/dashboard.js`.

Acceptance: keyboard/screen-reader navigation follows a logical heading structure; unchanged polling does not repeatedly announce the history list. Screen-reader behavior still needs runtime verification.

## 7. Align documentation and evidence — Medium priority

- [ ] Correct the statement that `.env` is not loaded: the current configuration module loads it.
- [ ] Document the actual default quality threshold (`0.70`) separately from its adjustable range (`0.55–0.70`).
- [ ] Qualify or substantiate the SCRFD `60+ FPS` / `<8 ms` claims with reproducible hardware results.
- [ ] Distinguish detector latency, full recognition latency and video throughput.
- [ ] Update password setup instructions after removing the default password.
- [ ] Optionally refresh the legacy PRODUCT.md structure through Impeccable's `init` workflow, preserving confirmed requirements.

Files: `README.md`, generation READMEs, `docs/enrollment.md`, `docs/benchmarking.md`, configuration examples and optionally `PRODUCT.md`.

Acceptance: documentation matches the executable configuration and clearly distinguishes measured results from targets.

## Scope across generations

The root application, `gen-1-dlib/` and `gen-2-scrfd/` have corresponding implementations. Apply common fixes and tests to all supported launch trees; inspect differences before copying changes. Preserve detector-specific behavior and standalone launch commands. Do not introduce a shared-package refactor solely for this review.

No Convex/Supabase migration, new framework or pstack model configuration is required. The current product brief excludes cloud services. Preserve documented open dashboard access unless the owner separately chooses to change that policy; protecting enrollment-setting mutation is the immediate fix.

## Verification checklist

- [ ] Run `python scripts/run_tests.py` from each supported project directory.
- [ ] Run `node tests/test_speech.js` in each affected project.
- [ ] Run the new focused dashboard JavaScript tests and add them to CI.
- [ ] Verify unauthorized mutation, unconfigured password and malformed-request rejection.
- [ ] Verify threshold save failure, reload behavior and history outcome preservation.
- [ ] Inspect desktop/mobile, keyboard focus, 200% zoom, reduced motion and screen-reader announcements.
- [ ] Run the Impeccable detector on rendered markup with resolved stylesheet references; manually review findings.
- [ ] Verify successful enrollment and camera/relay behavior on the actual Pi before claiming hardware readiness.

Review baseline: root 89, dlib 89 and SCRFD 94 Python tests passed (272 total); root speech tests passed. Desktop offline/enrollment states were inspected with a preview whose APIs intentionally returned 503. Passing tests do not currently cover all findings above.

Not verified during review: physical camera/relay, successful live enrollment, Pi performance, recognition accuracy, mobile/zoom, screen-reader audio or 10%-speed motion inspection.
