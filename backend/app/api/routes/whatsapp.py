import logging

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from app.services.whatsapp_service import WhatsAppService
from app.services.session_manager import SessionManager
from app.services.conversation_service import ConversationService
from app.services.summary_service import SummaryService
from app.services.callback_service import CallbackService

logger = logging.getLogger(__name__)

router = APIRouter()
whatsapp_svc = WhatsAppService()
session_mgr = SessionManager()
conversation_svc = ConversationService()
summary_svc = SummaryService()
callback_svc = CallbackService()

VALID_SPECIALTIES = [
    "general_md", "cardiology", "neurology", "dermatology",
    "gastroenterology", "orthopedic", "ent", "gynecology",
    "psychiatry", "pulmonology", "urology", "general_surgery",
    "ophthalmology",
]


# ─────────────────────────────────────────────────────────────────────
# 1. INITIATE CONVERSATION — Admin dashboard calls this to start a chat
# ─────────────────────────────────────────────────────────────────────


class InitiateRequest(BaseModel):
    patient_phone: str = Field(..., min_length=10, description="Phone with country code, no '+' (e.g., 919876543210)")
    patient_name: str = Field(..., min_length=1, max_length=200, description="Patient name")
    specialty: str = Field(..., description="Doctor specialty")
    hospital_id: str = Field(default="default_hospital", description="Hospital identifier")


class InitiateResponse(BaseModel):
    success: bool
    session_id: str
    message: str


@router.post("/whatsapp/initiate", response_model=InitiateResponse)
def initiate_whatsapp_chat(request: InitiateRequest):
    """
    Start a pre-consultation chat with a patient via WhatsApp.
    Creates a session and sends the first template message.
    """
    # Validate specialty
    specialty = request.specialty.lower()
    if specialty not in VALID_SPECIALTIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid specialty '{request.specialty}'. Choose from: {VALID_SPECIALTIES}",
        )

    # Clean phone number (remove +, spaces, dashes)
    phone = request.patient_phone.replace("+", "").replace(" ", "").replace("-", "")

    # Check if patient already has an active session
    existing = session_mgr.get_by_phone(phone)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Patient already has an active session: {existing.session_id}",
        )

    # Create session
    session = session_mgr.create(
        hospital_id=request.hospital_id,
        patient_id=phone,  # Use phone as patient_id for WhatsApp flow
        patient_name=request.patient_name,
        specialty=specialty,
        patient_phone=phone,
    )

    # Send template message to patient
    result = whatsapp_svc.send_template_message(
        to_phone=phone,
        template_name="preconsultation_start",
        parameters=[request.patient_name],
    )

    if result.get("error"):
        logger.error(f"Failed to send WhatsApp template to {phone}: {result}")
        return InitiateResponse(
            success=False,
            session_id=session.session_id,
            message=f"Session created but WhatsApp message failed: {result.get('details', 'Unknown error')}",
        )

    logger.info(f"WhatsApp session initiated for {request.patient_name} ({phone})")
    return InitiateResponse(
        success=True,
        session_id=session.session_id,
        message=f"Template message sent to {phone}. Waiting for patient reply.",
    )


# ─────────────────────────────────────────────────────────────────────
# 2. WEBHOOK — Meta calls this when patient sends a message
# ─────────────────────────────────────────────────────────────────────


@router.get("/webhook/whatsapp")
def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    """
    Webhook verification — Meta sends a GET request once during setup.
    You provide a verify_token in Meta dashboard, Meta sends it here to confirm.
    """
    if not hub_mode or not hub_verify_token or not hub_challenge:
        raise HTTPException(status_code=400, detail="Missing verification parameters")

    challenge = whatsapp_svc.verify_webhook(hub_mode, hub_verify_token, hub_challenge)
    if challenge:
        return PlainTextResponse(content=challenge)

    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/webhook/whatsapp")
async def receive_whatsapp_message(request: Request):
    """
    Receive incoming messages from WhatsApp.
    Meta POSTs here every time a patient sends a message.
    """
    # Always respond 200 quickly (Meta expects fast response, retries otherwise)
    try:
        payload = await request.json()
    except Exception:
        return {"status": "ok"}

    # Parse the incoming message
    parsed = whatsapp_svc.parse_incoming_message(payload)
    if not parsed:
        # Not a text message or status update — ignore silently
        return {"status": "ok"}

    phone = parsed["from_phone"]
    message_text = parsed["message_text"]

    logger.info(f"WhatsApp message from {phone}: {message_text[:50]}...")

    # Find the active session for this phone number
    session = session_mgr.get_by_phone(phone)
    if not session:
        # No active session — patient messaged without being initiated
        whatsapp_svc.send_text_message(
            to_phone=phone,
            message="Hello! I don't have an active consultation for you right now. "
                    "Please contact your hospital reception to start a pre-consultation.",
        )
        return {"status": "ok"}

    # Check if this is the first reply (patient said "Yes" or anything to start)
    if session.turn_count == 0 and len(session.messages) == 0:
        # Generate AI first message (greeting + first question)
        try:
            result = conversation_svc.get_first_message(session)
            whatsapp_svc.send_text_message(
                to_phone=phone,
                message=result["first_message"],
            )
        except Exception as e:
            logger.error(f"Failed to generate first message for {phone}: {e}")
            whatsapp_svc.send_text_message(
                to_phone=phone,
                message="Sorry, I'm having trouble right now. Please try again in a moment.",
            )
        return {"status": "ok"}

    # Normal conversation flow — process patient message
    try:
        result = conversation_svc.chat(session, message_text)
    except Exception as e:
        logger.error(f"Chat failed for {phone}: {e}")
        whatsapp_svc.send_text_message(
            to_phone=phone,
            message="Sorry, something went wrong. Please try again.",
        )
        return {"status": "ok"}

    # Send AI reply back to patient via WhatsApp
    whatsapp_svc.send_text_message(
        to_phone=phone,
        message=result["reply"],
    )

    # If completed or emergency, generate summary and send callback
    if result["status"] in ("completed", "emergency"):
        try:
            summary_svc.generate(session)
            callback_svc.send(session)
            logger.info(f"Session completed for {phone}. Summary generated.")
        except Exception as e:
            logger.error(f"Summary/callback failed for {phone}: {e}")

    return {"status": "ok"}
