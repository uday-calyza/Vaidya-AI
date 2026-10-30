import httpx
import logging

from app.config import settings

logger = logging.getLogger(__name__)


class WhatsAppService:
    """Handles all communication with Meta WhatsApp Cloud API."""

    def __init__(self):
        self.api_url = settings.whatsapp_api_url
        self.phone_number_id = settings.whatsapp_phone_number_id
        self.access_token = settings.whatsapp_access_token
        self.base_url = f"{self.api_url}/{self.phone_number_id}/messages"
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    def send_template_message(
        self,
        to_phone: str,
        template_name: str = "preconsultation_start",
        language_code: str = "en",
        parameters: list[str] | None = None,
    ) -> dict:
        """
        Send a template message (required for initiating conversation).

        Args:
            to_phone: Patient phone with country code, no '+' (e.g., "919876543210")
            template_name: Approved template name from Meta dashboard
            language_code: Template language
            parameters: List of variable values for the template (e.g., [patient_name])

        Returns:
            Meta API response dict or error dict
        """
        payload = {
            "messaging_product": "whatsapp",
            "to": to_phone,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
            },
        }

        # Add template parameters if provided
        if parameters:
            payload["template"]["components"] = [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": param} for param in parameters
                    ],
                }
            ]

        return self._send_request(payload)

    def send_text_message(self, to_phone: str, message: str) -> dict:
        """
        Send a plain text message to a patient.
        Only works within 24-hour window after patient replies.

        Args:
            to_phone: Patient phone with country code, no '+' (e.g., "919876543210")
            message: Text message to send

        Returns:
            Meta API response dict or error dict
        """
        payload = {
            "messaging_product": "whatsapp",
            "to": to_phone,
            "type": "text",
            "text": {"body": message},
        }

        return self._send_request(payload)

    def parse_incoming_message(self, payload: dict) -> dict | None:
        """
        Parse the incoming webhook payload from Meta.

        Returns:
            {
                "from_phone": "919876543210",
                "message_text": "hello",
                "message_id": "wamid.xxx",
                "timestamp": "1234567890"
            }
            or None if not a valid text message
        """
        try:
            entry = payload.get("entry", [])
            if not entry:
                return None

            changes = entry[0].get("changes", [])
            if not changes:
                return None

            value = changes[0].get("value", {})
            messages = value.get("messages", [])
            if not messages:
                return None

            message = messages[0]

            # Only handle text messages for now
            if message.get("type") != "text":
                return None

            return {
                "from_phone": message["from"],
                "message_text": message["text"]["body"],
                "message_id": message["id"],
                "timestamp": message.get("timestamp", ""),
            }

        except (KeyError, IndexError) as e:
            logger.error(f"Failed to parse WhatsApp webhook payload: {e}")
            return None

    def verify_webhook(self, mode: str, token: str, challenge: str) -> str | None:
        """
        Verify webhook during Meta setup.
        Meta sends a GET request with hub.mode, hub.verify_token, hub.challenge.

        Returns:
            The challenge string if verification passes, None otherwise.
        """
        if mode == "subscribe" and token == settings.whatsapp_verify_token:
            logger.info("WhatsApp webhook verified successfully")
            return challenge
        logger.warning(f"WhatsApp webhook verification failed. Mode: {mode}")
        return None

    def _send_request(self, payload: dict) -> dict:
        """Send request to Meta WhatsApp API."""
        try:
            response = httpx.post(
                self.base_url,
                headers=self.headers,
                json=payload,
                timeout=30,
            )

            if response.status_code == 200:
                logger.info(f"WhatsApp message sent successfully to {payload.get('to')}")
                return response.json()
            else:
                error_data = response.json()
                logger.error(f"WhatsApp API error: {response.status_code} - {error_data}")
                return {"error": True, "status_code": response.status_code, "details": error_data}

        except Exception as e:
            logger.error(f"WhatsApp API request failed: {type(e).__name__}: {e}")
            return {"error": True, "details": str(e)}
