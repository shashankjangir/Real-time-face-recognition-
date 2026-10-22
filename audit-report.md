# Codebase Audit — Real-Time Face Recognition & Access System

> [!NOTE]
> Full read of every source, template, CSS, JS, and test file completed. Findings ranked by risk. Nothing was changed.

---

## 🔴 Critical — Fix These First

### 1. `update_action_outcome` never commits
**File:** [database.py#L309-L312](file:///c:/3.%20Real-time-face-recognition-/src/database.py#L309-L312)

```python
def update_action_outcome(self, log_id, outcome, detail=None):
    with self.pool.get_connection() as conn:
        conn.execute("UPDATE access_log SET action_outcome=?, action_detail=? WHERE id=?",
                     (outcome, detail, log_id))
```

**Bug:** No `conn.commit()`. With `isolation_level=None` (autocommit), bare `conn.execute()` **does** autocommit in CPython's sqlite3 for DML — *but only if no explicit `BEGIN` was previously issued on that pooled connection*. Since `add_identity()` calls `conn.execute("BEGIN IMMEDIATE")` on pooled connections that get reused, a connection returned to the pool after a `BEGIN IMMEDIATE` + `commit()` *should* be back in autocommit, so this likely works in practice. **However**, it's inconsistent with every other write method that explicitly commits, and it would silently lose data if the pool ever recycled a connection in a bad state.

**Fix:** Add `conn.commit()` after the `execute`.

### 2. Picamera2 `RGB888` is actually RGB, not BGR
**File:** [camera.py#L66-L67](file:///c:/3.%20Real-time-face-recognition-/src/camera.py#L62-L70)

```python
# Picamera2 RGB888 already yields BGR byte order for OpenCV.
return True, self.picam2.capture_array()
```

**Bug:** The comment is wrong and the code may be wrong depending on Picamera2 version. `RGB888` format from Picamera2 produces **RGB** byte order, not BGR. If the frame is fed to OpenCV and `face_recognition` without conversion, colors will be swapped (cosmetic for the stream) **and `face_recognition.face_locations` expects RGB anyway, so detection works — but `cv2.cvtColor(frame, COLOR_BGR2RGB)` in [`recognition_engine.py#L241`](file:///c:/3.%20Real-time-face-recognition-/src/recognition_engine.py#L241) will double-swap to BGR**, which will hurt detection accuracy on a real Pi.

**Fix:** Either change the Picamera2 format to `"BGR888"` (native OpenCV order), or remove the `cvtColor` in `detect_and_extract` when the backend is Picamera2. Simplest: change format to `"BGR888"`.

---

## 🟠 High — Correctness & Data Integrity

### 3. Singleton `get_db_manager` leaks across tests
**File:** [database.py#L449-L458](file:///c:/3.%20Real-time-face-recognition-/src/database.py#L449-L458)

The global `_db_manager_instance` singleton is never reset. Tests that call `get_db_manager()` without passing `db_file` get a real on-disk DB that persists across runs. Test isolation depends on each test creating its own `DatabaseManager(":memory:")`, which they do — but any test that accidentally imports a helper that calls `get_db_manager()` internally will hit the wrong database.

**Fix:** Add a `reset_db_manager()` for tests, or use dependency injection everywhere.

### 4. `CameraManager.__init__` starts the backend immediately
**File:** [camera.py#L198-L212](file:///c:/3.%20Real-time-face-recognition-/src/camera.py#L198-L212)

`_initialize_backend()` calls `backend.start()` during `__init__`. The `OpenCVBackend.start()` opens the camera device. If `CameraManager` is instantiated but `start()` is never called (e.g., an error path), the camera device stays open with no capture thread reading from it, and `stop()` is only called on the backend if init fails. This means **the camera device is held open before the app is ready to use it**, and on Pi the CSI bus is exclusive — a stale open blocks restarts.

**Recommendation:** Move `backend.start()` into `CameraManager.start()`.

### 5. `_capture_loop` can spin at 100% CPU
**File:** [camera.py#L223-L253](file:///c:/3.%20Real-time-face-recognition-/src/camera.py#L223-L253)

When `backend.read()` returns instantly (which `Picamera2Backend.read()` can do), the loop has no sleep or backpressure. The `SyntheticBackend` self-paces with `time.sleep()`, but real backends don't.

**Fix:** Add a brief `time.sleep(0.001)` at the top or use `Event.wait` pacing.

### 6. `recognize_stream.py` and `app.py` (root) are identical
**Files:** [app.py](file:///c:/3.%20Real-time-face-recognition-/app.py) vs [recognize_stream.py](file:///c:/3.%20Real-time-face-recognition-/recognize_stream.py)

Both do `from src.app import app, initialize_pipeline` and `app.run(...)`. One of them is dead code.

**Recommendation:** Delete `recognize_stream.py` or make it a one-line import alias.

---

## 🟡 Medium — Robustness

### 7. Connection pool `get_connection` blocks forever if pool exhausted
**File:** [database.py#L165-L170](file:///c:/3.%20Real-time-face-recognition-/src/database.py#L164-L170)

`Queue.get(timeout=DB_POOL_TIMEOUT)` raises `queue.Empty` after 10 seconds, which propagates as an unhandled exception. This is fine for crash-fail, but a friendlier error message would help debugging.

### 8. `log_recognition` with duplicate `event_key` silently fails
**File:** [database.py#L288-L307](file:///c:/3.%20Real-time-face-recognition-/src/database.py#L288-L307) + [database.py#L208](file:///c:/3.%20Real-time-face-recognition-/src/database.py#L208)

The unique index on `event_key` causes `IntegrityError` on duplicate insert. `access.py` checks for duplicates before inserting, but a race between two workers on the same frame_id (shouldn't happen with `commit_lock`, but worth noting) would crash instead of gracefully deduplicating.

### 9. `RecognitionWorker` stops permanently on any exception
**File:** [recognition_engine.py#L399-L411](file:///c:/3.%20Real-time-face-recognition-/src/recognition_engine.py#L399-L411)

A single unhandled exception in `process_frame` (e.g., a corrupt frame) kills the worker thread permanently. The runtime detects this in `check_health()`, but between the crash and the next health check, throughput drops silently.

**Recommendation:** Catch, log, and continue for transient errors; stop only on repeated failures.

### 10. `AnnotationOverlay.render` reads `self.fps` outside lock
**File:** [recognition_engine.py#L174](file:///c:/3.%20Real-time-face-recognition-/src/recognition_engine.py#L174)

```python
hud_text = f"FPS: {self.fps:.1f}  |  ..."
```

`self.fps` is written by the encoder thread under `self.lock` at [runtime.py#L111](file:///c:/3.%20Real-time-face-recognition-/src/runtime.py#L111), but `render()` calls `get_active_faces()` (which locks) and then reads `self.fps` outside the lock. This is a benign data race (float reads are atomic on CPython), but it's technically a TSAN violation.

### 11. `_fps_tracker` list used across threads without a lock
**File:** [camera.py#L248-L251](file:///c:/3.%20Real-time-face-recognition-/src/camera.py#L248-L251)

The capture thread appends to and pops from `self._fps_tracker`, while `get_fps()` reads it. List operations are GIL-protected in CPython, but the compound read-modify-write sequence isn't atomic.

### 12. `face_quality_report` box coordinates assume `face_recognition` order
**File:** [enroll.py#L35](file:///c:/3.%20Real-time-face-recognition-/src/enroll.py#L35)

```python
t, r, b, l = max(0, box.top), min(w, box.right), min(h, box.bottom), max(0, box.left)
```

This clamps but never validates `top < bottom` and `left < right` *before* clamping. If the face detection returns inverted coordinates, the check `b <= t or r <= l` catches it — good.

---

## 🟢 Low / Style

### 13. Dual import pattern everywhere
Every `src/*.py` file has:
```python
try:
    from . import config
except (ImportError, ValueError):
    import config
```
This is a workaround for running files both as `python src/app.py` and as a package. It works, but it means two different module objects for `config` can exist in `sys.modules`. Not a bug today.

### 14. `LOG_CONFIDENCE_THRESHOLD` is unused
**File:** [config.py#L71](file:///c:/3.%20Real-time-face-recognition-/src/config.py#L71)

```python
LOG_CONFIDENCE_THRESHOLD = 0.50  # Legacy setting; policy uses RECOGNITION_THRESHOLD only
```

Dead config. Delete it.

### 15. `ENCODINGS_FILE` / pickle sync is a legacy liability
**File:** [enroll.py#L114-L135](file:///c:/3.%20Real-time-face-recognition-/src/enroll.py#L114-L135)

`sync_to_pickle` writes all identity embeddings to an unencrypted, unsigned pickle file after every enrollment. This is a **deserialization attack surface** if anyone can write to that path, and the file is never read by the current codebase (the engine loads from SQLite). Delete it.

### 16. No `__init__.py` in `tests/`
Tests rely on `sys.path.insert(0, ...)` instead of proper package imports. Works but fragile.

### 17. `test_speech.js` exists but no JS test runner is configured
**File:** [tests/test_speech.js](file:///c:/3.%20Real-time-face-recognition-/tests/test_speech.js)

The file exists but there's no `package.json`, no test runner, and no CI config to run it.

---

## Summary Table

| # | Severity | File | Issue |
|---|----------|------|-------|
| 1 | 🔴 Critical | `database.py` | `update_action_outcome` missing `commit()` |
| 2 | 🔴 Critical | `camera.py` | Picamera2 RGB/BGR mismatch → wrong colors on real Pi |
| 3 | 🟠 High | `database.py` | Singleton leaks across tests |
| 4 | 🟠 High | `camera.py` | Camera opened eagerly in `__init__` |
| 5 | 🟠 High | `camera.py` | Capture loop can spin at 100% CPU |
| 6 | 🟠 High | root | `recognize_stream.py` is dead code |
| 7 | 🟡 Medium | `database.py` | Pool exhaustion gives unhelpful error |
| 8 | 🟡 Medium | `database.py` / `access.py` | Duplicate `event_key` race |
| 9 | 🟡 Medium | `recognition_engine.py` | Worker dies on single exception |
| 10 | 🟡 Medium | `recognition_engine.py` | `fps` read outside lock |
| 11 | 🟡 Medium | `camera.py` | `_fps_tracker` thread safety |
| 12 | 🟡 Medium | `enroll.py` | Box coordinate edge case (handled) |
| 13 | 🟢 Low | all `src/` | Dual-import pattern |
| 14 | 🟢 Low | `config.py` | Dead `LOG_CONFIDENCE_THRESHOLD` |
| 15 | 🟢 Low | `enroll.py` | Pickle sync is unused attack surface |
| 16 | 🟢 Low | `tests/` | No `__init__.py` |
| 17 | 🟢 Low | `tests/` | `test_speech.js` has no runner |
