"""Shared policy, audit and actuator coordination for all recognition workers."""
import threading
from . import config


class DecisionCoordinator:
    def __init__(self, db, action=None, enabled=True, engine=None):
        self.db = db
        self.action = action  # Callable(face); raises on failure. None never claims actuation.
        self.enabled = enabled
        self.engine = engine
        self.lock = threading.Lock()
        self.failure = None
        self.frame_lock = threading.Lock()
        self.last_frame = {}

    def apply_frame(self, faces, frame_id, session_id):
        """Evaluate a single person immediately; multiple faces are display only."""
        with self.frame_lock:
            if frame_id <= self.last_frame.get(session_id, -1):
                return
            self.last_frame[session_id] = frame_id
            if len(faces) > 1:
                for face in faces:
                    face.decision = 'observe'
                    face.reason = 'multiple_faces_display_only'
                    face.action_outcome = 'not_requested'
                return faces
            for index, face in enumerate(faces):
                self.apply(face, frame_id, session_id, index)
            return faces

    def apply(self, face, frame_id, session_id, index=0, multiple_faces=False):
        key = f"{session_id}:{frame_id}:{index}"
        with self.lock:
            # Durable deduplication survives worker changes and avoids repeating an action.
            with self.db.pool.get_connection() as conn:
                prior = conn.execute("SELECT * FROM access_log WHERE event_key=?", (key,)).fetchone()
            if prior:
                face.decision, face.reason, face.action_outcome = prior['decision'], prior['reason'], prior['action_outcome']
                return face
            attentive = getattr(face, 'is_attentive', True)
            allow = not self.failure and self.enabled and face.is_match and face.identity_id is not None and not multiple_faces and attentive
            face.decision = 'allow' if allow else 'deny'
            face.reason = ('pipeline_failure' if self.failure else 'simulation_disabled' if not self.enabled else 'multiple_faces' if multiple_faces
                           else 'attention_required' if not attentive else 'identity_matched' if allow else 'identity_not_matched')
            outcome = ('not_requested' if not allow else 'not_configured' if self.action is None
                       else 'pending')
            log_id = self.db.log_recognition(face.identity_id, face.name, face.confidence,
                face.match_distance, 'verified' if allow else 'rejected', frame_id, session_id,
                config.FACE_DETECTION_MODEL, decision=face.decision, reason=face.reason,
                action_outcome=outcome, event_key=key)

            # Apple continuous template adaptation on high-confidence match
            if allow and face.match_distance <= config.RECOGNITION_THRESHOLD / 2.0:
                if hasattr(self.db, 'adapt_identity_template'):
                    try:
                        updated = self.db.adapt_identity_template(face.identity_id, face.encoding)
                        if updated and self.engine:
                            self.engine.reload_identities()
                    except Exception:
                        pass
            if outcome == 'pending':
                # Persist intent before invoking hardware.
                detail = None
                try:
                    if self.action(face) is False:
                        raise RuntimeError('Actuator reported failure')
                    outcome = 'succeeded'
                except Exception as exc:
                    outcome, detail = 'failed', str(exc)
                self.db.update_action_outcome(log_id, outcome, detail)
            face.action_outcome = outcome
            return face

    def fault(self, frame_id, session_id, detail):
        with self.lock:
            self.failure = detail
            self.db.log_recognition(None, 'System', 0, status='rejected', frame_id=frame_id,
                session_id=session_id, decision='deny', reason='pipeline_failure',
                action_outcome='not_requested', action_detail=detail)
