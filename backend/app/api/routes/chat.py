from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.session_manager import SessionManager
from app.services.conversation_service import ConversationService
from app.services.summary_service import SummaryService
from app.services.callback_service import CallbackService

router = APIRouter()
session_mgr = SessionManager()
conversation_svc = ConversationService()
summary_svc = SummaryService()
callback_svc = CallbackService()


class ChatRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    status: str
    turn_count: int
    tokens_in: int
    tokens_out: int


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """
    Send a patient message. Returns AI response.
    When status = 'completed', summary is auto-generated and sent to hospital callback.
    """
    # Get session
    session = session_mgr.get(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found. Please register the patient first.")

    # Check session is still active
    if session.status != "active":
        raise HTTPException(
            status_code=400,
            detail=f"Session is '{session.status}'. Cannot continue chat.",
        )

    # Process the message
    try:
        result = conversation_svc.chat(session, request.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat failed: {type(e).__name__}: {str(e)}")

    # If completed or emergency, generate summary and send callback
    if result["status"] in ("completed", "emergency"):
        try:
            summary_svc.generate(session)
            callback_svc.send(session)
        except Exception:
            pass  # Summary/callback failure shouldn't block the chat response

    return ChatResponse(
        session_id=request.session_id,
        reply=result["reply"],
        status=result["status"],
        turn_count=result["turn_count"],
        tokens_in=result["tokens_in"],
        tokens_out=result["tokens_out"],
    )
