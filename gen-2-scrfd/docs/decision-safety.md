# Decision and failure behavior

Recognition requires the installed pretrained `face_recognition`/dlib model.
After installation, inference and enrollment work offline. Enrollment stores a
128D embedding; it does not retrain the neural network. Empty scenes return no
detections, no access action and no fabricated authentication record.

Missing models, detection/extraction failures and camera read failures are explicit
errors. Authenticated `/health` requests return HTTP 503 when the pipeline is unavailable. A runtime
failure stops submissions and requires resolving the fault and restarting the
service. Simulation is opt-in and cannot authorize access or web enrollment.

All workers share a DecisionCoordinator. A single matched face with an enrolled
identity is allowed; unknown identities and multiple faces are denied. The match
score is not a probability and is never a second logging threshold. The overlay,
policy and access audit use the same decision. Each processed rejected face is
logged, including near-threshold mismatches. Empty frames are not access attempts.

Each event has a unique session/frame/face key. Reprocessing that event reuses its
record and never repeats its action. Cooldown is shared across workers and limits
actuation, not visibility of rejected decisions. Recognition runs without a browser;
opening extra streams does not create extra inference submissions.

## Connecting the existing actuator

Before `initialize_pipeline()`, set `src.app.app.config['ACCESS_ACTION']` to a
callable accepting one RecognizedFace. It must return only when its bounded action
completes; raise an exception or return False on failure. It should implement its
own hardware timeout and safe release. The callback is serialized across workers.
Wire this to the existing indicator/relay driver using its actual pins and polarity.
No GPIO wiring is guessed by this software change.

An allow decision is a policy result, not proof that a door opened. Outcomes are:
`not_configured`, `not_requested`, `pending`, `succeeded`, `failed`, or
`cooldown_suppressed`. The system writes intent before invoking the callback and
then stores its outcome. If the first audit write fails, no action runs. A `pending`
record after interruption has an uncertain physical outcome and is not retried
for the same event. SQLite and external hardware cannot share an atomic transaction.
A callback's success is not a physical door sensor confirmation.

## Database integrity

Every pooled connection enables foreign keys. Identity upsert, actual ID lookup
and enrollment-history insertion commit or roll back together. Startup adds audit
columns and an event-key index to existing databases without removing records.
Old records have null decision/outcome fields; those results cannot be reconstructed.
Existing historical foreign-key violations are not retroactively repaired.
Run `PRAGMA foreign_key_check` on a backup during deployment review.

## Validation order

1. Run software regression tests: `python scripts/run_tests.py`.
2. On the Pi, install the real model and verify camera, enrollment, decisions,
   actuator callback and explicit failure paths.
3. Only after functionality is stable, collect independent labelled captures and
   run the real-image and Pi benchmarks in `benchmarking.md`.

Unit fixtures are not accuracy or performance evidence. The dashboard reports
accuracy as unmeasured until there is an independent evaluation. Current changes
do not certify 50+ identities, >95% accuracy, <300 ms latency or 15-20 inference FPS.
