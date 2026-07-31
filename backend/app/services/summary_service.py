import json

from app.models.session import Session
from app.services.bedrock_service import BedrockService
from app.services.prompt_service import PromptService


class SummaryService:
    """Generates structured clinical summaries from conversations."""

    def __init__(self):
        self.bedrock = BedrockService()
        self.prompt = PromptService()

    def generate(self, session: Session) -> dict:
        """Generate a structured summary from the session's conversation."""
        if not session.messages:
            return {"error": "No conversation to summarize"}

        # Build conversation text for the summary LLM call
        conversation_text = f"Patient: {session.patient_name}\nSpecialty: {session.specialty}\n\n"
        for msg in session.messages:
            label = "Patient" if msg["role"] == "user" else "AI"
            text = msg["content"][0]["text"]
            conversation_text += f"{label}: {text}\n"

        # Call Bedrock with summary prompt
        system_prompt = self.prompt.summary_prompt()
        messages = [{"role": "user", "content": [{"text": conversation_text}]}]
        result = self.bedrock.converse(messages, system_prompt)

        # Parse JSON response
        raw_text = result["text"]
        try:
            if "```json" in raw_text:
                raw_text = raw_text.split("```json")[1].split("```")[0]
            elif "```" in raw_text:
                raw_text = raw_text.split("```")[1].split("```")[0]
            summary_data = json.loads(raw_text.strip())
        except (json.JSONDecodeError, IndexError):
            summary_data = {"clinical_narrative": raw_text, "parse_error": True}

        # Build the full summary payload (what gets sent to hospital)
        summary = {
            "hospital_id": session.hospital_id,
            "patient_id": session.patient_id,
            "patient_name": session.patient_name,
            "session_id": session.session_id,
            "specialty": session.specialty,
            "status": session.status,
            "summary": summary_data,
            "conversation_turns": session.turn_count,
            "created_at": session.created_at.isoformat(),
            "completed_at": session.completed_at.isoformat() if session.completed_at else None,
        }

        # Store in session
        session.summary = summary
        return summary
