"""Shared policy, audit and actuator coordination for all recognition workers."""
import threading
import time
from . import config


class DecisionCoordinator:
    def __init__(self, db, action=None, enabled=True):
        self.db = db
        self.action = action  # Callable(face); raises on failure. None never claims actuation.
        self.enabled = enabled
        self.lock = threading.Lock()
        self.last_action = {}
        self.failure = None

    def apply(self, face, frame_id, session_id, index=0, multiple_faces=False):
        key = f"{session_id}:{frame_id}:{index}"
        with self.lock:
            # Durable deduplication survives worker changes and avoids repeating an action.
            with self.db.pool.get_connection() as conn:
                prior = conn.execute("SELECT * FROM access_log WHERE event_key=?", (key,)).fetchone()
            if prior:
                face.decision, face.reason, face.action_outcome = prior['decision'], prior['reason'], prior['action_outcome']
                return face
            allow = not self.failure and self.enabled and face.is_match and face.identity_id is not None and not multiple_faces
            face.decision = 'allow' if allow else 'deny'
            face.reason = ('pipeline_failure' if self.failure else 'simulation_disabled' if not self.enabled else 'multiple_faces' if multiple_faces
                           else 'identity_matched' if allow else 'identity_not_matched')
            now = time.monotonic()
            last = self.last_action.get(face.identity_id)
            outcome = ('not_requested' if not allow else 'not_configured' if self.action is None
                       else 'cooldown_suppressed' if last is not None and now-last < config.LOG_COOLDOWN_SECONDS
                       else 'pending')
            log_id = self.db.log_recognition(face.identity_id, face.name, face.confidence,
                face.match_distance, 'verified' if allow else 'rejected', frame_id, session_id,
                config.FACE_DETECTION_MODEL, decision=face.decision, reason=face.reason,
                action_outcome=outcome, event_key=key)
            if outcome == 'pending':
                # Persist intent before invoking hardware; failures also consume cooldown.
                self.last_action[face.identity_id] = now
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
