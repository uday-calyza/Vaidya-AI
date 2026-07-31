import boto3

from app.config import settings


class BedrockService:
    """Thin wrapper over AWS Bedrock Converse API."""

    def __init__(self):
        self.client = boto3.client(
            "bedrock-runtime",
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )
        self.model_id = settings.bedrock_model_id

    def converse(self, messages: list[dict], system_prompt: str) -> dict:
        """
        Call Bedrock Converse API.

        Args:
            messages: [{"role": "user"|"assistant", "content": [{"text": "..."}]}]
            system_prompt: The system instruction text.

        Returns:
            {"text": str, "tokens_in": int, "tokens_out": int}
        """
        response = self.client.converse(
            modelId=self.model_id,
            system=[{"text": system_prompt}],
            messages=messages,
            inferenceConfig={
                "maxTokens": 300,
                "temperature": 0.3,
            },
        )

        output_message = response["output"]["message"]
        usage = response["usage"]

        return {
            "text": output_message["content"][0]["text"],
            "tokens_in": usage["inputTokens"],
            "tokens_out": usage["outputTokens"],
        }
