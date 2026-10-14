# Enrollment and administrator authentication

[Back to the project](../README.md)

## Configure the administrator token

Generate a strong token locally:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Set it in the same shell that launches the server. Replace the placeholder with
your generated value; never commit the token.

```powershell
$env:ADMIN_ENROLLMENT_TOKEN = "<your-generated-token>"
python app.py
```

On Linux:

```bash
export ADMIN_ENROLLMENT_TOKEN='<your-generated-token>'
python app.py
```

An unset or empty token disables HTTP enrollment. `.env.example` documents the
variables; copying it to `.env` does not load them automatically.

## Dashboard and API

Enter the token in the dashboard password field, then select **Enroll Identity**.
Keep exactly one face visible with even lighting and clear focus. The dashboard
clears the token field after a response and does not persist it in browser storage.

API clients send `POST /api/enroll`, a JSON body such as `{"name":"Jane Doe"}`,
and `Authorization: Bearer <token>`. A successful response includes the identity
ID and measured `quality_score`.

| HTTP status | Meaning |
| --- | --- |
| 200 | Identity saved and recognition gallery reloaded. |
| 400 | Invalid JSON object or name. |
| 401 | Missing or incorrect administrator token. |
| 422 | Missing frame, zero/multiple faces, invalid embedding, or poor quality. |
| 503 | Administrator token unconfigured, synthetic camera, or model unavailable. |

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
