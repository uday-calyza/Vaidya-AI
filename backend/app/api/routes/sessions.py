from fastapi import APIRouter, HTTPException

from app.services.session_manager import SessionManager
from app.services.summary_service import SummaryService

router = APIRouter()
session_mgr = SessionManager()
summary_svc = SummaryService()


@router.get("/session/{session_id}/status")
def get_session_status(session_id: str):
    """Check the current status of a session."""
    session = session_mgr.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session.to_dict()


@router.get("/session/{session_id}/summary")
def get_session_summary(session_id: str):
    """Get the clinical summary for a completed session."""
    session = session_mgr.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.status == "active":
        raise HTTPException(status_code=400, detail="Session is still active. Summary available after completion.")

    # If summary doesn't exist yet (e.g., expired session), generate it now
    if not session.summary:
        try:
            summary_svc.generate(session)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Summary generation failed: {str(e)}")

    return session.summary


@router.get("/session/{session_id}/history")
def get_session_history(session_id: str):
    """Get the full conversation transcript."""
    session = session_mgr.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_id": session_id,
        "patient_name": session.patient_name,
        "specialty": session.specialty,
        "status": session.status,
        "messages": [
            {"role": m["role"], "text": m["content"][0]["text"]}
            for m in session.messages
        ],
    }
