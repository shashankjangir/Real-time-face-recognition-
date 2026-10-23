# Face / Access

Authenticated local operators view camera state, inspect recognition/access decisions, enroll identities with measured capture quality, and search/export history. The Pi performs recognition and policy coordination; a match and a hardware action outcome are distinct.

Stack: Flask/Jinja, plain CSS/JavaScript, local SQLite; root and two generation launch directories. Local fonts and assets. Camera-independent rendering is supported, but actual enrollment requires real hardware and administrator authentication.

Cloud services excluded by user instruction. Preserve keyboard access, reduced motion and a single MJPEG image per page. Actual deployment generation and physical performance remain to be checked on the user's Pi.
