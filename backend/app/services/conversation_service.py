from app.models.session import Session
from app.services.bedrock_service import BedrockService
from app.services.prompt_service import PromptService
from app.services.session_manager import SessionManager


class ConversationService:
    """Handles multi-turn chat: builds context, calls Bedrock, updates session."""

    def __init__(self):
        self.bedrock = BedrockService()
        self.prompt = PromptService()
        self.session_mgr = SessionManager()

    def get_first_message(self, session: Session) -> dict:
        """Generate the first AI message, addressing patient by name."""
        # Build prompt with health context injected
        system_prompt = self.prompt.intake_prompt(
            specialty=session.specialty,
            health_context=session.health_context,
        )

        # Tell the LLM who the patient is and to greet them
        trigger = (
            f"Patient named {session.patient_name} has joined the chat. "
            f"They are visiting the {session.specialty} department. "
            f"City: {session.city or 'not specified'}. "
            f"Greet them by name and ask your first question."
        )
        messages = [{"role": "user", "content": [{"text": trigger}]}]

        result = self.bedrock.converse(messages, system_prompt)
        first_message = result["text"]

        # Store only the assistant greeting in session history
        session.messages.append({"role": "assistant", "content": [{"text": first_message}]})

        return {
            "first_message": first_message,
            "tokens_in": result["tokens_in"],
            "tokens_out": result["tokens_out"],
        }

    def chat(self, session: Session, user_message: str) -> dict:
        """Process a patient message and return AI response."""

        # Check if session is still active
        if session.status != "active":
            return {
                "reply": "This session has ended. Please contact reception.",
                "status": session.status,
                "turn_count": session.turn_count,
                "tokens_in": 0,
                "tokens_out": 0,
            }

        # Build messages array for Bedrock (existing history + new message)
        messages = list(session.messages)
        messages.append({"role": "user", "content": [{"text": user_message}]})

        # Build prompt with health context injected
        system_prompt = self.prompt.intake_prompt(
            specialty=session.specialty,
            health_context=session.health_context,
        )

        # Question counter: inject wrap-up instruction based on message count
        assistant_count = sum(1 for m in messages if m["role"] == "assistant")
        if assistant_count >= 7:
            system_prompt += "\n\n[SYSTEM: You have sent 7+ messages. Your NEXT message MUST be your closing with Do's/Don'ts and COMPLETE. Do not ask any more questions. Wrap up NOW.]"
        elif assistant_count >= 6:
            system_prompt += "\n\n[SYSTEM: You have sent 6 messages. You have 1 message left before you MUST wrap up. Either ask your final question or close now.]"

        result = self.bedrock.converse(messages, system_prompt)
        reply_text = result["text"]

        # Detect COMPLETE / EMERGENCY signals
        status = "active"
        clean_reply = reply_text

        if "COMPLETE" in reply_text:
            status = "completed"
            clean_reply = reply_text.replace("COMPLETE", "").strip()
            if not clean_reply:
                clean_reply = (
                    f"Thank you {session.patient_name}. Your responses have been sent to the doctor. "
                    "Please wait for your consultation."
                )
        elif "EMERGENCY" in reply_text:
            status = "emergency"
            clean_reply = reply_text.replace("EMERGENCY", "").strip()
            if not clean_reply:
                clean_reply = "This needs immediate attention. Please alert the hospital staff right now."

        # Save messages to session
        session.messages.append({"role": "user", "content": [{"text": user_message}]})
        session.messages.append({"role": "assistant", "content": [{"text": clean_reply}]})
        session.turn_count = sum(1 for m in session.messages if m["role"] == "user")

        # Update session status
        if status == "completed":
            self.session_mgr.mark_completed(session.session_id)
        elif status == "emergency":
            self.session_mgr.mark_emergency(session.session_id)

        # Update activity timestamp
        self.session_mgr.update_activity(session.session_id)

        return {
            "reply": clean_reply,
            "status": status,
            "turn_count": session.turn_count,
            "tokens_in": result["tokens_in"],
            "tokens_out": result["tokens_out"],
        }
