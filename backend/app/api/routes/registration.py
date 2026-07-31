from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.session_manager import SessionManager
from app.services.conversation_service import ConversationService

router = APIRouter()
session_mgr = SessionManager()
conversation_svc = ConversationService()

VALID_SPECIALTIES = [
    "general_md", "cardiology", "neurology", "dermatology",
    "gastroenterology", "orthopedic", "ent", "gynecology",
]


class RegisterPatientRequest(BaseModel):
    hospital_id: str = Field(..., min_length=1, description="Hospital/clinic identifier")
    patient_id: str = Field(..., min_length=1, description="Patient ID from hospital system")
    patient_name: str = Field(..., min_length=1, max_length=200, description="Patient's name")
    specialty: str = Field(..., description="Doctor specialty for this visit")
    callback_url: str | None = Field(None, description="Hospital endpoint to POST summary to when completed")


class RegisterPatientResponse(BaseModel):
    session_id: str
    patient_name: str
    specialty: str
    first_message: str
    status: str
    expires_in_minutes: int


@router.post("/register-patient", response_model=RegisterPatientResponse)
def register_patient(request: RegisterPatientRequest):
    """
    Hospital registers a patient. Creates a session and returns the AI's first message.
    The hospital system or UI then uses the session_id for subsequent /chat calls.
    """
    specialty = request.specialty.lower()
    if specialty not in VALID_SPECIALTIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid specialty '{request.specialty}'. Choose from: {VALID_SPECIALTIES}",
        )

    # Create session
    session = session_mgr.create(
        hospital_id=request.hospital_id,
        patient_id=request.patient_id,
        patient_name=request.patient_name,
        specialty=specialty,
        callback_url=request.callback_url,
    )

    # Generate first AI message (greets patient by name)
    try:
        result = conversation_svc.get_first_message(session)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate greeting: {type(e).__name__}: {str(e)}")

    return RegisterPatientResponse(
        session_id=session.session_id,
        patient_name=session.patient_name,
        specialty=session.specialty,
        first_message=result["first_message"],
        status=session.status,
        expires_in_minutes=30,
    )
