import boto3

from app.config import settings


class BedrockService:
    """Thin wrapper over AWS Bedrock Converse API."""

    def __init__(self):
        # Use explicit credentials if provided (local dev), otherwise fall back
        # to IAM role / instance profile (ECS Fargate, EC2, etc.)
        client_kwargs = {"region_name": settings.aws_region}
        if settings.aws_access_key_id and settings.aws_secret_access_key:
            client_kwargs["aws_access_key_id"] = settings.aws_access_key_id
            client_kwargs["aws_secret_access_key"] = settings.aws_secret_access_key

        self.client = boto3.client("bedrock-runtime", **client_kwargs)
        self.model_id = settings.bedrock_model_id

    def converse(self, messages: list[dict], system_prompt: str, max_tokens: int = 300) -> dict:
        """
        Call Bedrock Converse API.

        Args:
            messages: [{"role": "user"|"assistant", "content": [{"text": "..."}]}]
            system_prompt: The system instruction text.
            max_tokens: Maximum tokens for response (300 for chat, 1024 for summaries).

        Returns:
            {"text": str, "tokens_in": int, "tokens_out": int}
        """
        response = self.client.converse(
            modelId=self.model_id,
            system=[{"text": system_prompt}],
            messages=messages,
            inferenceConfig={
                "maxTokens": max_tokens,
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
