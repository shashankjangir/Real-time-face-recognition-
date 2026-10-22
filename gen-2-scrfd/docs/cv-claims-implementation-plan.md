# Implementation status and validation roadmap

[Back to the project](../README.md)

This roadmap separates implemented software from results that require real data
and Raspberry Pi hardware. Target metrics are not verified performance claims.

## Implemented software

- Pretrained 128D face embeddings, vectorized cosine matching and explicit model errors.
- Real camera backends with correct Picamera2 colour handling; simulation is opt-in.
- Administrator-protected web enrollment with single-face and image-quality checks.
- Atomic identity/history updates and foreign keys on every SQLite connection.
- Shared policy, action cooldown, event deduplication and audit reasons/outcomes.
- Browser-independent frame submission with unique IDs and monotonic timestamps.
- Bounded queues, stale-frame rejection and ordered decision publication.
- One JPEG encoder shared across viewers, with measured runtime telemetry.
- A shared application/Pi benchmark runtime and independent labelled-image evaluation.
- Indexed history queries, CSV export and software regression tests.

## 1. Finish deployment-specific integration

Record the actual parts and connections using the [hardware guide](../hardware/README.md).
Connect the existing display/actuator driver through the documented
[action interface](decision-safety.md). The current callback handles allowed actions;
an OLED feed for all denied/fault events needs its own integration. Verify boot,
shutdown, release, power-loss and driver-failure behavior. A successful callback
does not prove that the physical door opened.

Review the deployment database for historical foreign-key violations. Plan any
repair from a backup rather than deleting history. Standardize audit timestamps
with explicit timezone handling before combining logs from multiple devices;
current persisted audit timestamps use local time without a timezone offset.

Verify the installed spoof-resistance mechanism and access to history/admin APIs
for the intended deployment. Hardware ownership or software tests alone do not
establish these behaviors. Follow the [bring-up checklist](../hardware/bring-up.md).

## 2. Establish accuracy with independent captures

After functional integration is complete:

1. Enroll at least 50 real people with measured-quality reference images.
2. Collect separate calibration and final-test sessions. Do not reuse enrollment
   images or adjacent frames as independent final trials.
3. Select a cosine-distance threshold using calibration data, then freeze it.
4. Include every enrolled identity and unknown people in the held-out test set.
5. Report sample counts, known-person and overall accuracy, false accepts, false
   rejects, wrong identities and detection failures. Define an acceptable false
   acceptance target before evaluation.

Suggested dataset sizes are 20 final probes per enrolled person and 200 unknown
probes across at least 20 people. These are proposals, not existing evidence.
If one template per identity is insufficient, evaluate multiple templates as a
separate change and use a fresh held-out test set.

Acceptance: actual 50+ identity gallery, accuracy strictly greater than 95% if that
claim is retained, and a published metric definition with error breakdown.

## 3. Measure and optimize on the Pi 5

Follow [the benchmark protocol](benchmarking.md). Record software/model versions,
camera settings, gallery size, face count, power, cooling and test duration.

- Profile detection, embeddings, matching, queue wait, JPEG encoding and audit work.
- Compare one, two and four workers; additional threads may increase contention.
- Tune only measured bottlenecks, then repeat accuracy checks after preprocessing changes.
- Run representative workloads for at least 10-15 minutes and report drops and
  stale/out-of-order discards alongside median, p95 and maximum latency.
- Separate capture FPS, unique JPEG FPS, completed recognition FPS and client display FPS.
- Measure browser/network delivery separately if claiming client-visible throughput.

The shared Pi benchmark includes inference and audit work but uses no physical
actuator. Its timing starts at software frame delivery and excludes exposure and
prior camera-driver buffering. Do not label it capture-to-door latency.
At 30 captured FPS with every-third-frame submission, recognition is at most
10 FPS even if video throughput is 15-20 FPS.

Acceptance: measured latency under the stated statistic (prefer p95 <300 ms) and
sustained video throughput under representative recognition load. Dropped frames
must remain visible in the report, not disappear from the performance assessment.

## 4. Verify reporting and assemble evidence

- Exercise known, unknown, revoked, repeated and fault scenarios supported by the deployment.
- Compare filtered CSV rows against SQLite queries, including names with commas,
  quotes and Unicode. Confirm nullable IDs preserve historical audit entries.
- Check query plans and response times at representative log volumes; index
  presence alone does not prove a specific response-time claim.
- Save anonymized accuracy/performance summaries, configuration, query-plan examples
  and a hardware demonstration tied to the exact software revision.

Keep raw faces, embeddings, credentials, databases and identifying reports private.
Use `identification` for the current 1:N search; use `verification` for a claimed
identity compared 1:1 or explicitly describe verification after identification.
Describe the model as pretrained unless training was actually performed. Replace
CV targets with measured results and dates that reflect when the work was completed.
