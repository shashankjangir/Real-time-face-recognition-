# Enrollment and authentication

[Back to the project](../README.md)

## Enrollment password

Face enrollment requires a password to prevent unauthorized identity registration.

Set it in your shell or `.env` file before launching:

```powershell
$env:ENROLLMENT_PASSWORD = "your-password"
python app.py
```

On Linux:

```bash
export ENROLLMENT_PASSWORD='your-password'
python app.py
```

If unset, `ENROLLMENT_PASSWORD` defaults to `123456789`. You can also use `ADMIN_ENROLLMENT_TOKEN` as an alias.

## Dashboard and live stream

The dashboard, live MJPEG camera stream, access logs, metrics, dynamic CSV reports, and health checks are accessible without login credentials.

Only **Capture & enroll** (`POST /api/enroll`) and **Check face quality** (`POST /api/enrollment/quality`) require the enrollment password.

Enter the password in the dashboard's **Enrollment password** field, then select **Capture & enroll**.

API clients send `POST /api/enroll` with JSON `{"name": "Jane Doe"}` and either:
- Header: `Authorization: Bearer <password>`
- Or body: `{"name": "Jane Doe", "password": "<password>"}`

| HTTP status | Meaning |
| --- | --- |
| 200 | Identity saved and recognition gallery reloaded. |
| 400 | Invalid JSON object or name. |
| 401 | Missing or incorrect enrollment password. |
| 422 | Missing frame, zero/multiple faces, invalid embedding, or poor quality. |
| 503 | Enrollment password unconfigured, synthetic camera, or model unavailable. |

Quality combines crop sharpness, brightness, and face size. Scores below
`ENROLLMENT_MIN_QUALITY` (currently `0.70`) are rejected. This is a heuristic
image-quality score, not an identity probability or liveness measurement.

Real enrollment requires `face_recognition`; its missing-model error is expected
on installations using only the core requirements. Synthetic cameras and
random-projection embeddings are not accepted for HTTP enrollment.

Use HTTPS for network deployment because bearer tokens grant enrollment access.
Rotate the token by changing the environment value and restarting the service.

## Local image enrollment

```bash
python enroll.py --name "Jane Doe" --image /path/to/portrait.jpg
```

The same single-face and quality checks apply. Local CLI access is protected by
the operating system account rather than the HTTP token. Re-enrolling an
existing name replaces its current embedding and records enrollment history.
Restart an already-running service after CLI enrollment so its gallery reloads.

`python enroll.py --synthetic 50` generates test vectors in the working database;
use it only with disposable development data. It does not enroll real people.


## Diagnose a low quality score

The dashboard's **Check face quality** control requires the administrator token
but does not enroll or save a face. It examines one current frame and reports
sharpness (40% weight), brightness (30%) and face size (30%), using the same
heuristic as enrollment. The threshold remains 0.70. The score is not recognition
accuracy and is not a calibrated probability.

For example, a well-lit face at least 100 pixels across scores only 0.60 if its
sharpness component is zero. Adding more light will not necessarily fix blur,
and direct phone flash can reduce the brightness component through overexposure.
Use the component readings to distinguish blur, lighting and a small face crop.
A quality check describes one frame; enrollment validates a fresh frame again.

Camera Module 3 now explicitly uses continuous autofocus when the camera exposes
`AfMode`. The dashboard reports whether this mode was enabled, not whether the
lens has actually achieved focus. Keep your face near the centre, hold still,
use steady diffuse light, clean the lens and avoid being too close. If sharpness
stays low, compare a native `rpicam-hello` preview on the Pi with the web preview
before changing thresholds. Continuous autofocus is documented in the
[official Picamera2 manual](https://datasheets.raspberrypi.com/camera/picamera2-manual.pdf).

Quality-check requests use `POST /api/enrollment/quality` with the same Bearer
administrator authentication as enrollment. Missing/multiple faces are reported
without a readiness score; camera/model failures remain explicit errors.


### Unknown faces and identity assignment

The matcher now uses a conservative starting cosine-distance ceiling of 0.08
and requires a 0.02 gap from the next closest identity. Near-ties, duplicate
embeddings, invalid vectors, and candidates outside the ceiling are rejected as
Unknown with no identity ID. These settings are not calibrated accuracy claims;
validate them with separate captures of enrolled and unenrolled people on the Pi.
The former 0.48 cosine ceiling was overly permissive. Dlib's raw Euclidean
thresholds cannot be copied to this normalized cosine pipeline.
Existing enrollments remain compatible. If a name was enrolled with the wrong
person, re-enroll that name with the correct person; software cannot infer who
an incorrectly labelled stored face really belongs to. Historical logs are not
rewritten by this fix.

An ALLOW decision followed by `not_configured` means the application's
`ACCESS_ACTION` callback is absent. It is not confirmation of a physical unlock.
The dashboard now displays this as "No hardware action configured" while audit
codes remain unchanged.

Move the floating camera using its top header (mouse or touch). With that header
focused, arrow keys move it and Home returns it to the bottom center. Its position
is kept during scrolling within the page and clamped when resizing the window.


### Field testing: glasses, lighting, and lookalikes

For one visible person, access is evaluated immediately on each fresh recognition
result. There is no three-match confirmation requirement or timed access cooldown.
A configured hardware action may run on every new matched frame; duplicate and
out-of-order frame protection still prevents replaying the same event.

For multiple visible people, the system only displays individual recognition:
enrolled matches are green with their names, and unknown faces are red. There is
no group access decision, confirmation count, cooldown calculation, hardware action,
or access-log entry for these display-only frames. Recognition still runs to
identify each face. Spoken recognition announcements remain available. Enrollment
still requires exactly one face. A return to one face resumes immediate access evaluation.

Glasses: the current database stores one active embedding per person. Capturing
the same name again replaces that active embedding; it does not currently add a
second glasses/no-glasses template. For immediate testing, enroll with the glasses
normally worn, in ordinary diffuse illumination, avoiding reflections over the
eyes. Retain separate labelled evaluation captures with and without glasses.
A future multi-sample enrollment change must explicitly support several validated
templates per identity, compare distinct identities (not individual templates)
for the runner-up margin, and test whether the extra templates increase false
acceptances. Do not loosen the threshold just to fix glasses failures.

Lighting: supported Picamera2 auto exposure and auto white balance controls are
explicitly enabled. Use the quality check's brightness and sharpness values in
normal room lighting, then under steady frontal diffuse light. A phone flash can
create glasses reflections and does not test normal operating conditions. At a
fixed frame rate, exposure time is limited; brightening a dark noisy image in
software cannot restore missing facial detail. Check camera exposure/gain on the
Pi before changing the capture frame rate or tuning exposure compensation.

Lookalikes: the runner-up margin only compares enrolled identities. It cannot
reject an unseen lookalike merely because the real person is not enrolled.
Three consistent wrong matches are still wrong. Collect separate labelled known
and unknown captures, including the observed lookalike pairs, to select and
validate the threshold. Measure false acceptance and false rejection separately,
with glasses and lighting conditions recorded. If the two distance distributions
overlap, require another credential for access rather than claiming face-only
recognition can distinguish these people reliably.

Attention checks reject closed eyes and unavailable landmarks. They measure eye openness only; they are not liveness or photo-spoof protection.
