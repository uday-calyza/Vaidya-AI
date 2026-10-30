from fastapi import APIRouter

from app.services.session_manager import SessionManager

router = APIRouter()
session_mgr = SessionManager()


@router.get("/hospital/{hospital_id}/sessions")
def list_hospital_sessions(hospital_id: str):
    """List all of today's sessions for a hospital. Used by the hospital system to pull data."""
    sessions = session_mgr.list_by_hospital(hospital_id)

    return {
        "hospital_id": hospital_id,
        "count": len(sessions),
        "sessions": [
            {
                **s.to_dict(),
                "chief_complaint": s.summary["summary"].get("chief_complaint") if s.summary else None,
                "red_flags": s.summary["summary"].get("red_flags", []) if s.summary else [],
            }
            for s in sessions
        ],
    }
