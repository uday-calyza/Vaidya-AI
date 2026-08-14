from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.session_manager import SessionManager
from app.services.conversation_service import ConversationService
from app.services.health_context_service import HealthContextService

router = APIRouter()
session_mgr = SessionManager()
conversation_svc = ConversationService()
health_context_svc = HealthContextService()

VALID_SPECIALTIES = [
    "general_md", "cardiology", "neurology", "dermatology",
    "gastroenterology", "orthopedic", "ent", "gynecology",
    "psychiatry", "pulmonology", "urology", "general_surgery",
    "ophthalmology",
]


class RegisterPatientRequest(BaseModel):
    hospital_id: str = Field(..., min_length=1, description="Hospital/clinic identifier")
    patient_id: str = Field(..., min_length=1, description="Patient ID from hospital system")
    patient_name: str = Field(..., min_length=1, max_length=200, description="Patient's name")
    specialty: str = Field(..., description="Doctor specialty for this visit")
    city: str = Field("", max_length=100, description="Patient's city/locality")
    callback_url: str | None = Field(None, description="Hospital endpoint to POST summary to when completed")


class RegisterPatientResponse(BaseModel):
    session_id: str
    patient_name: str
    specialty: str
    city: str
    first_message: str
    status: str
    expires_in_minutes: int


@router.post("/register-patient", response_model=RegisterPatientResponse)
def register_patient(request: RegisterPatientRequest):
    """
    Hospital registers a patient. Creates a session, gathers local health context,
    and returns the AI's first message.
    """
    specialty = request.specialty.lower()
    if specialty not in VALID_SPECIALTIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid specialty '{request.specialty}'. Choose from: {VALID_SPECIALTIES}",
        )

    # Gather local health context (Tavily search — runs once at registration)
    # Graceful degradation: if this fails, session still works without context
    health_context = None
    city = request.city.strip()
    if city:
        try:
            health_context = health_context_svc.gather_context(city=city)
        except Exception:
            pass  # Context is an enhancement, not a dependency

    # Create session with city and health context
    session = session_mgr.create(
        hospital_id=request.hospital_id,
        patient_id=request.patient_id,
        patient_name=request.patient_name,
        specialty=specialty,
        city=city,
        state=health_context.state if health_context else "",
        callback_url=request.callback_url,
        health_context=health_context,
    )

    # Generate first AI message (greets patient by name, context-aware)
    try:
        result = conversation_svc.get_first_message(session)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate greeting: {type(e).__name__}: {str(e)}")

    return RegisterPatientResponse(
        session_id=session.session_id,
        patient_name=session.patient_name,
        specialty=session.specialty,
        city=session.city,
        first_message=result["first_message"],
        status=session.status,
        expires_in_minutes=30,
    )
