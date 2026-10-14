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
        self.frame_lock = threading.Lock()
        self.group = ()
        self.confirmation_session = None
        self.streak = 0
        self.last_check = None
        self.last_frame = {}
        self.confirmed_at = {}

    def apply_frame(self, faces, frame_id, session_id):
        """Confirm a whole visible group; perform at most one hardware action per frame."""
        with self.frame_lock:
            if frame_id <= self.last_frame.get(session_id, -1):
                return
            self.last_frame[session_id] = frame_id
            if self.confirmation_session != session_id:
                self.group, self.streak, self.last_check = (), 0, None
                self.confirmation_session = session_id
            now = time.monotonic()
            ids = [f.identity_id for f in faces]
            valid = bool(faces) and all(f.is_match and f.identity_id is not None for f in faces)
            valid = valid and len(set(ids)) == len(ids)
            group = tuple(sorted(ids)) if valid else ()
            if (not group or group != self.group or self.last_check is None
                    or now-self.last_check > config.CONFIRMATION_MAX_GAP_SECONDS):
                self.streak = 0
            self.group, self.last_check = group, now
            self.streak = min(config.CONFIRMATION_FRAMES, self.streak+1) if valid else 0
            confirmed = valid and self.streak >= config.CONFIRMATION_FRAMES
            remaining = max((config.LOG_COOLDOWN_SECONDS-(now-self.confirmed_at[i])
                             for i in ids if i in self.confirmed_at), default=0)
            shared = 'cooldown_suppressed' if confirmed and remaining > 0 else None
            for index, face in enumerate(faces):
                face.confirmation_count = self.streak
                face.cooldown_remaining = max(0, remaining) if confirmed else 0
                self.apply(face, frame_id, session_id, index,
                           multiple_faces=not valid and len(faces)>1,
                           confirmed=confirmed, shared_outcome=shared)
                if confirmed and index == 0:
                    shared = face.action_outcome
                    if face.decision == 'allow' and remaining <= 0:
                        for ident in ids:
                            self.confirmed_at[ident] = now
                        face.cooldown_remaining = config.LOG_COOLDOWN_SECONDS
            return faces


    def apply(self, face, frame_id, session_id, index=0, multiple_faces=False, confirmed=True, shared_outcome=None):
        key = f"{session_id}:{frame_id}:{index}"
        with self.lock:
            # Durable deduplication survives worker changes and avoids repeating an action.
            with self.db.pool.get_connection() as conn:
                prior = conn.execute("SELECT * FROM access_log WHERE event_key=?", (key,)).fetchone()
            if prior:
                face.decision, face.reason, face.action_outcome = prior['decision'], prior['reason'], prior['action_outcome']
                return face
            allow = not self.failure and self.enabled and face.is_match and face.identity_id is not None and not multiple_faces and confirmed
            face.decision = 'allow' if allow else 'deny'
            face.reason = ('pipeline_failure' if self.failure else 'simulation_disabled' if not self.enabled else 'multiple_faces' if multiple_faces
                           else 'awaiting_confirmation' if face.is_match and not confirmed else 'identity_matched' if allow else 'identity_not_matched')
            now = time.monotonic()
            last = self.last_action.get(face.identity_id)
            outcome = ('not_requested' if not allow else shared_outcome if shared_outcome is not None else 'not_configured' if self.action is None
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
