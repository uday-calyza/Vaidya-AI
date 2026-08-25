import uuid
from datetime import datetime, timedelta

from app.models.session import Session
from app.config import settings

# In-memory store — will be replaced by DB later
_sessions: dict[str, Session] = {}

# Phone number → session_id mapping (for WhatsApp lookup)
_phone_to_session: dict[str, str] = {}

SESSION_TIMEOUT_MINUTES = 30


class SessionManager:
    """Manages session lifecycle: create, get, expire, list."""

    def create(
        self,
        hospital_id: str,
        patient_id: str,
        patient_name: str,
        specialty: str,
        city: str = "",
        state: str = "",
        callback_url: str | None = None,
        health_context=None,
        patient_phone: str = "",
    ) -> Session:
        """Create a new session for a patient."""
        session = Session(
            session_id=str(uuid.uuid4()),
            hospital_id=hospital_id,
            patient_id=patient_id,
            patient_name=patient_name,
            specialty=specialty,
            patient_phone=patient_phone,
            city=city,
            state=state,
            callback_url=callback_url,
            health_context=health_context,
        )
        _sessions[session.session_id] = session

        # Map phone → session for WhatsApp lookup
        if patient_phone:
            _phone_to_session[patient_phone] = session.session_id

        return session

    def get_by_phone(self, phone: str) -> Session | None:
        """Get active session by patient phone number (for WhatsApp webhook)."""
        session_id = _phone_to_session.get(phone)
        if session_id:
            session = _sessions.get(session_id)
            if session and session.status == "active":
                return session
        return None

    def get(self, session_id: str) -> Session | None:
        """Get a session by ID. Returns None if not found."""
        return _sessions.get(session_id)

    def update_activity(self, session_id: str) -> None:
        """Update last_activity_at timestamp."""
        session = _sessions.get(session_id)
        if session:
            session.last_activity_at = datetime.utcnow()

    def mark_completed(self, session_id: str) -> None:
        """Mark session as completed."""
        session = _sessions.get(session_id)
        if session:
            session.status = "completed"
            session.completed_at = datetime.utcnow()

    def mark_emergency(self, session_id: str) -> None:
        """Mark session as emergency."""
        session = _sessions.get(session_id)
        if session:
            session.status = "emergency"
            session.completed_at = datetime.utcnow()

    def mark_expired(self, session_id: str) -> None:
        """Mark session as expired (timed out)."""
        session = _sessions.get(session_id)
        if session:
            session.status = "expired"

    def list_by_hospital(self, hospital_id: str) -> list[Session]:
        """List all sessions for a hospital (today only)."""
        today = datetime.utcnow().date()
        return [
            s for s in _sessions.values()
            if s.hospital_id == hospital_id and s.created_at.date() == today
        ]

    def expire_stale_sessions(self) -> list[str]:
        """Find and expire sessions that have been idle for > 30 minutes.
        Returns list of expired session_ids."""
        cutoff = datetime.utcnow() - timedelta(minutes=SESSION_TIMEOUT_MINUTES)
        expired = []
        for session in _sessions.values():
            if session.status == "active" and session.last_activity_at < cutoff:
                session.status = "expired"
                expired.append(session.session_id)
        return expired
