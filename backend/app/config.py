from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # AWS Bedrock
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "ap-south-1"
    bedrock_model_id: str = "global.anthropic.claude-haiku-4-5-20251001-v1:0"

    # App
    app_env: str = "development"

    # CORS — comma-separated list of allowed origins
    # In production, set to your CloudFront URL e.g. "https://d1234abcdef.cloudfront.net"
    cors_origins: str = "http://localhost:5173,http://localhost:3000,http://localhost:8080,http://127.0.0.1:8080"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
