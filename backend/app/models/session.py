from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Session:
    """Represents a single patient intake session."""

    session_id: str
    hospital_id: str
    patient_id: str
    patient_name: str
    specialty: str
    status: str = "active"  # active | completed | emergency | expired
    messages: list[dict] = field(default_factory=list)
    turn_count: int = 0
    summary: dict | None = None
    callback_url: str | None = None
    callback_sent: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_activity_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize session for API responses."""
        return {
            "session_id": self.session_id,
            "hospital_id": self.hospital_id,
            "patient_id": self.patient_id,
            "patient_name": self.patient_name,
            "specialty": self.specialty,
            "status": self.status,
            "turn_count": self.turn_count,
            "created_at": self.created_at.isoformat(),
            "last_activity_at": self.last_activity_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
