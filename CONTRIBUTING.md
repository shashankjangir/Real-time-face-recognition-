# Contributing

The active implementation is in `src/`; earlier versions are preserved in
`archive/` and are not the default development target.

## Local checks

Install the [core dependencies](requirements.txt) into a virtual environment.
The [model dependency](requirements-face-recognition.txt) is required for real
face enrollment, but tests mock real-model behavior where appropriate.

```bash
python scripts/run_tests.py
```

The runner uses temporary storage and the synthetic camera so development checks
do not change your working identities or audit reports.

## Changes

- Keep the root launch commands working.
- Add meaningful regression tests for enrollment, authentication, and logging changes.
- Update the relevant guide in `docs/` when configuration or behavior changes.
- Preserve the distinction between synthetic tests and hardware measurements.
- Do not include biometric images, embeddings, local databases, credentials, or
  generated personal reports in changes intended for publication.

Before sharing, inspect `git status --short` and the diff. Project code and
documentation use the [MIT License](LICENSE); preserve applicable third-party notices.

## Continuous integration

The [software test workflow](.github/workflows/tests.yml) runs the test runner and
syntax checks on Ubuntu and Windows with Python 3.11 and 3.12 for pushes and pull
requests. It installs core dependencies only; model and camera behavior are mocked
where needed. CI results do not establish Pi performance or face-recognition accuracy.
