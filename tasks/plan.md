# Face / Access — implementation status

Supersedes the cloud proposal: the user explicitly excluded Supabase and Convex. All processing, enrollment, audit and dashboard access stay local.

| Delivered | Files / behavior |
|---|---|
| Camera-first dashboard | Root, gen-1-dlib and gen-2-scrfd templates/styles |
| Technical visual hierarchy | Local Space Grotesk, dark camera, light work surfaces, stable tabular numbers |
| Enrollment and history | Ordered capture guidance, filters/export preserved, named focusable scroll region |
| Interaction polish | Native dialog with selected Transitions.dev open/close; Escape and focus return |
| GSAP | Locally vendored 3.13.0; optional decorative mark entrance; reduced-motion and cleanup |
| Mobile | Responsive readouts/forms; floating camera suppressed during input editing |
| Accessibility | Global focus outlines, retained tabindex fixes, local SVG brand mark |
| Status | Last successful measurement timestamp; stale label on API failure |

## Evidence

- Root dashboard tests: 10 passed before and after changes.
- Generation 1 dashboard tests: 10 passed after changes.
- Generation 2 dashboard tests: 10 passed after changes.
- Speech JavaScript checks passed for all three launch directories.
- JavaScript syntax check passed.
- Temporary local preview uses real templates/static assets with synthetic API responses; no real enrollment or hardware action.
- Preview axe-core 4.14.0 scan: zero WCAG 2 A/AA and WCAG 2.1 AA violations in the scanned normal-page state.
- Browser: native dialog opened, search focused, Escape closed, focus returned to identity trigger.
- Browser: at 390px, focusing enrollment input removed floating dock.
- Browser: one feed image and no page-wide overflow observed at 390, 768, 1280 and 1920px.

## Remaining deployment checks

Physical MJPEG stream, actual camera/model measurements, real enrollment, Pi runtime performance and production deployment have not been exercised. Reduced-motion rules are implemented but OS preference switching and slowed-motion replay were not exercised. Open-dialog axe scan and full populated-history states remain deployment checks. Cloud integration removed from scope. No dependencies installed globally.
