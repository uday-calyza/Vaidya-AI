from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class HealthAlert:
    """A single health context item from the Local Health Context Service."""

    claim: str
    source: str
    url: str
    source_type: str  # "news" | "government" | "health_authority" | "unverified"
    verification_status: str = "reported"  # Always "reported" for search results
    relevance_score: float = 0.0
    disease_keywords: list[str] = field(default_factory=list)
    region_match: str = ""  # "exact_city" | "same_state" | "nearby_state" | "national"
    published_at: str | None = None
    retrieved_at: str = ""


@dataclass
class HealthContext:
    """Structured session context gathered from Local Health Context Service."""

    city: str
    state: str
    date: str
    season: str  # "monsoon" | "winter" | "summer"
    local_alerts: list[HealthAlert] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "city": self.city,
            "state": self.state,
            "date": self.date,
            "season": self.season,
            "local_alerts": [
                {
                    "claim": a.claim,
                    "source": a.source,
                    "url": a.url,
                    "source_type": a.source_type,
                    "verification_status": a.verification_status,
                    "relevance_score": a.relevance_score,
                    "disease_keywords": a.disease_keywords,
                    "region_match": a.region_match,
                    "published_at": a.published_at,
                    "retrieved_at": a.retrieved_at,
                }
                for a in self.local_alerts
            ],
        }


@dataclass
class Session:
    """Represents a single patient intake session."""

    session_id: str
    hospital_id: str
    patient_id: str
    patient_name: str
    specialty: str
    city: str = ""
    state: str = ""
    status: str = "active"  # active | completed | emergency | expired
    messages: list[dict] = field(default_factory=list)
    turn_count: int = 0
    summary: dict | None = None
    health_context: HealthContext | None = None
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
            "city": self.city,
            "state": self.state,
            "status": self.status,
            "turn_count": self.turn_count,
            "health_context": self.health_context.to_dict() if self.health_context else None,
            "created_at": self.created_at.isoformat(),
            "last_activity_at": self.last_activity_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
