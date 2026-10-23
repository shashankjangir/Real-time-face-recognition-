# Facial Recognition Web Station — Complete Requirements Specification

This document consolidates all user-directed requirements, UI/UX changes, functional behaviors, animations, architectural decisions, and backend fixes requested across all sessions.

---

## 1. Authentication & Security Policy
- **Open Dashboard & Public Live Feed**:
  - Remove mandatory login/token authentication previously required to access the web dashboard, stream, telemetry, and decision logs.
  - Anyone accessing the station URL can view the live camera feed, real-time metrics, system health, and recognition decisions.
- **Protected Face Enrollment**:
  - Enrolling a new face into the database remains strictly protected by an administrator password (`ENROLLMENT_PASSWORD` / `ADMIN_ENROLLMENT_TOKEN`, default `123456789`).
  - Face enrollment requests (`POST /api/enroll`) and manual quality checks (`POST /api/enrollment/quality`) require password authorization; unauthorized requests receive HTTP 401.

---

## 2. Camera Stream & Live Display
- **Dynamic Aspect Ratio Adaptation**:
  - The live camera viewport (`.camera-stage`) dynamically adapts its aspect ratio to match the camera input stream (e.g., 4:3, 16:9, or custom sensor resolution) rather than being fixed.
- **Scroll-Linked Stream Gliding & Relocation**:
  - The **camera stream box** (`.camera-shell`) is the active element that smoothly moves on scroll.
  - When scrolling from the top station view down toward the face-enrollment section, the stream box glides diagonally and docks into the dedicated slot (`.enrollment-camera-slot`) to the right of the enrollment form.
  - **Enlarged Enrollment Stream**: In the enrollment slot, the camera stream expands up to `min(500px, 100%)` for easy viewing during enrollment.
  - **Fluid Continuous Motion**: Movement uses continuous cosine easing (`translate3d`) without snapping or abrupt layout jumps; scrolling upward reverses the animation smoothly.
- **Continuous Proximity Repulsion**:
  - As the camera stream glides across and approaches adjacent elements (such as the enrollment card), nearby elements continuously and smoothly shift outward (repel) to avoid visual overlapping, easing back once docked.

---

## 3. Capture Quality Heuristic & Threshold Controls
- **Sidebar Placement**:
  - The **Capture Quality** card is stationary in the specifications sidebar (`<aside class="specifications">`), positioned directly under **Station Readout** and beneath the **Voice Controls**.
  - Sized compactly with a clean, modern card container.
- **Adjustable Quality Threshold**:
  - Interactive knob/slider on the website allowing real-time adjustment of required capture quality between `0.55` and `0.70` (default `0.70`).
  - Synced to the backend (`POST /api/config/quality`) and persisted locally (`localStorage`) so threshold changes persist across reloads.
- **Continuous Live Feedback**:
  - Live indicators for **Overall Quality Score**, **Sharpness** (Laplacian variance), **Brightness** (mean luminance), and **Face Size** update in real time while the camera is active.
  - Status transitions between `READY TO CAPTURE`, `ADJUST CAPTURE`, `NO FACE`, and `MULTIPLE FACES`.
  - Driven by low-overhead real-time metrics from the active face overlay with exponential moving average (EMA) smoothing to prevent visual flickering.

---

## 4. Decision History (Phone-App Style)
- **Compact Phone-App Presentation**:
  - Decision audit stream modeled after a mobile application feed (avatar status icon, bold identity title, badges, relative timestamps).
- **Recent 10 Limit & Consecutive Stacking**:
  - The view displays the most recent 10 unique events by default with a "Show more" button for pagination.
  - Consecutive events for the same individual with identical decision and action outcome stack together, displaying the count in brackets (e.g., `Shashank Jangir (5 events)`).
- **Single vs. Multiple Unknown Serialization**:
  - If a single unknown person is in view: labelled simply as `Unknown`.
  - If multiple unknown people appear simultaneously in the frame: ordered from left to right and labelled sequentially as `Unknown 1`, `Unknown 2`, etc.
  - The stream overlay and decision history reflect whether the person was recognized or unknown.
- **Multiple People Access Policy**:
  - If multiple faces appear in a frame, access is held in observation mode (`multiple_faces_display_only`), preventing unintended door unlocks while maintaining full visual telemetry.

---

## 5. Voice Announcer Station
- **Decoupled Architecture**:
  - Voice announcements run independently in the browser using the SpeechSynthesis API without blocking or coupling to the MJPEG video stream.
- **Dual Voice Selection (Man / Woman)**:
  - Toggle and dropdown selector to choose between male and female voices.
  - Voice preference is saved in `localStorage` and remembered on subsequent visits.
- **Immediate Change Speech**:
  - Speaks identity names immediately upon transition/change of persons in view.
  - Mute/Enable toggle button to silence audio when desired.
- **Card Placement**:
  - Styled as an elegant card positioned directly beneath Station Readout in the specifications column.

---

## 6. Interactive Visual Styling & Micro-interactions
- **Cosmic Energy Button Animations**:
  - Interactive buttons feature flowing cosmic energy gradient animations that match the specific color themes of each button (emerald green, sapphire blue, neutral slate).
  - High contrast and WCAG AA accessibility maintained for all text labels.
- **Preserved Design Integrity**:
  - Reverted experimental full-site overhauls (Heron AI design) to protect and retain the clean, established dark camera frame aesthetic.

---

## 7. Author Information & Credits
- **Footer Presentation**:
  - Dedicated author attribution panel at the bottom of the page featuring:
    - **Name**: Shashank Jangir
    - **Institution**: Indian Institute of Technology Delhi (IIT Delhi)
    - **Department**: Department of Electrical Engineering
    - Links to academic profile, project repository, and contact details.

---

## 8. Backend Performance & Streaming Stability
- **HD Resolution & Sharp Video**:
  - Camera capture default set to HD (`1280x720` on PC / USB webcams), eliminating blurriness when displayed across desktop screens.
  - Fast 2× HOG detection downsampling on HD inputs with full-resolution embedding extraction keeps latency under 90ms.
  - MJPEG quality set to `88` to eliminate compression softness.
  - Removed browser GPU texture caching blur (`will-change: transform, width`).
- **Connection Resilience**:
  - `CameraManager` capture loop tolerates up to 10 consecutive dropped frames from the USB bus without terminating the camera thread.
  - `RecognitionWorker` treats frame extraction errors as non-fatal warnings, preventing single noisy frames from crashing the station.
  - Clean client disconnect handling in `runtime.stream()` prevents broken pipe errors and hanging socket threads.
- **Cross-Generation Parity**:
  - All website features, backend optimizations, and test suites maintained in parity across:
    1. Root modular pipeline (`src/`)
    2. Generation 1 DLIB (`gen-1-dlib/`)
    3. Generation 2 SCRFD (`gen-2-scrfd/`)
