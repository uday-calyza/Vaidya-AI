import httpx

from app.models.session import Session


class CallbackService:
    """Sends the completed summary to the hospital's endpoint."""

    def send(self, session: Session) -> bool:
        """POST the summary to the hospital's callback URL.
        Returns True if successful, False otherwise."""
        if not session.callback_url:
            return False

        if not session.summary:
            return False

        if session.callback_sent:
            return True  # Already sent

        try:
            response = httpx.post(
                session.callback_url,
                json=session.summary,
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            if response.status_code in (200, 201, 202):
                session.callback_sent = True
                return True
            return False
        except Exception:
            return False
