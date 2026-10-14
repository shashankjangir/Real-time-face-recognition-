# Real-image evaluation and Raspberry Pi measurement

[Back to the project](../README.md)

The evaluator does not generate random identities, noisy vectors, or cartoon
frames. Both modes require the real `face_recognition` model and build an isolated
gallery from actual enrollment images. Your working database and embedding cache
are never changed. Missing data, a missing model, or unavailable hardware produces
an error, not a compliance result.

## Prepare labelled captures

Copy [the manifest example](examples/evaluation-manifest.csv) and replace its
paths and labels with your own captures. Image paths are relative to the manifest.

```csv
split,name,image,session
enroll,Alice,captures/enroll/alice.jpg,enrollment-day-1
test,Alice,captures/test/alice-01.jpg,evaluation-day-2
test,Unknown,captures/test/unenrolled-person-01.jpg,evaluation-day-2
```

Use one enrollment image per identity: the current matcher stores one active
template. Enrollment images must pass the same single-face, embedding-validity,
and quality checks as the application. Every enrolled identity needs test images;
include unenrolled people using the reserved `Unknown` label.

Capture enrollment and evaluation images in separate sessions. Repeated image
bytes are rejected, and enrollment/test session labels cannot overlap. These
checks catch accidental reuse; they cannot verify that session labels are truthful
or detect all transformed copies. Use genuinely independent captures, including
lighting, pose, distance, and glasses variation where relevant.

## Accuracy on independent images

```bash
python benchmark.py --manifest /path/to/manifest.csv --mode images --output reports/image-evaluation.json
```

Reports include overall accuracy, known-person identity accuracy, unknown-person
false acceptance, known-person false rejection, wrong-identity predictions,
invalid-capture counts, and each labelled prediction. Rates are fractions from
0 to 1. Invalid detections remain in the accuracy denominator and cannot count as
successful unknown rejection. Model/runtime failures abort the evaluation.

Processing latency covers detection, embedding generation, and matching, after
image decoding. It is not live camera latency. The report records the host and
does not claim Raspberry Pi performance when run on another computer.

The evaluator checks 50+ enrolled identities and strictly greater than 95% accuracy
for both overall and known-person classification. Exactly 95.0% fails. Calibrate
with a separate validation set and freeze `--threshold` before final evaluation;
the program does not tune thresholds on test captures.

## Pi 5 camera measurement

Run on the actual Raspberry Pi 5 with Picamera2 installed and a real face visible:

```bash
python benchmark.py --manifest /path/to/manifest.csv --mode pi --seconds 600 --output reports/pi-evaluation.json
```

This mode requires the Pi 5 device model and directly opens Picamera2, with no
USB or synthetic fallback. Stop other processes that own the camera first.

Pi mode instantiates the same `RecognitionRuntime` used by Flask: camera acquisition,
one frame producer, the configured worker pool (default four), a bounded queue
(default two), shared access/audit coordination, and one JPEG encoder. It uses a
temporary evaluation database and no physical actuator. Benchmark actions therefore
report `not_configured`; physical lock timing is not measured. It does not measure
HTTP delivery or browser rendering. No browser is needed to run the pipeline.

Each frame carries a camera ID and a monotonic timestamp recorded at software
delivery. Frames older than `MAX_FRAME_AGE_SECONDS` (default 0.5 seconds) are
rejected before inference or publication. Out-of-order completions cannot perform
an action or replace a newer result. Reports count queue drops, stale discards,
and out-of-order discards; inspect these alongside latency to identify overload.
Dropped work is not included in successful-completion latency percentiles.

Latency includes queue wait, detection, embedding, matching, serialized decision
handling and SQLite audit writes. JPEG encoding runs concurrently and competes for
CPU but is not a sequential prerequisite to a decision. Sensor exposure and
camera-driver buffering before delivery are excluded. App latency includes a
configured synchronous action callback; benchmark latency excludes physical actions.

The report separates capture FPS, unique encoded JPEG FPS, committed recognition
frames per second, and face decisions per second. The latency target uses frames
with detected faces; no face decisions means unavailable latency, not a pass.
Live accuracy remains unavailable without frame labels. Use image evaluation for
accuracy. Full-run decision timestamps are included in the Pi report; dashboard
latency statistics use the latest 10,000 committed frames and rates since startup.

Targets are 50+ loaded real identities, p95 delivery-to-decision below 300 ms,
and at least 15 unique JPEG frames per second. Record camera settings, lighting,
cooling, duration, and temperatures alongside the results for repeatability.

## Results and exit codes

- `0`: all measured targets for the selected mode passed.
- `1`: at least one target failed or is unavailable; the report is still saved.
- `2`: invalid input, missing model, or hardware/runtime error; no new report is saved.

JSON includes environment information, fixed threshold, manifest hash, and detailed
outcomes. Results under `reports/` are ignored by Git because they contain identity
labels and local image paths. Review and anonymize anything intended for sharing.

## Automated regression checks

```bash
python scripts/run_tests.py
```

Tests use controlled doubles to verify evaluation accounting, independent splits,
strict model selection, unique-frame counting, and honest failure statuses. They
are software regression tests, not empirical face-recognition measurements.

The dashboard reports measured runtime rates and latency, with unmeasured accuracy
and empty latency samples shown as unavailable. Software tests use controlled
fixtures; they do not establish Pi performance or recognition accuracy.
