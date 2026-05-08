from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    GITHUB_TOKEN: str
    GITHUB_WEBHOOK_SECRET: str
    GROQ_API_KEY: str
    DATABASE_URL: str = "sqlite:///./reviews.db"
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()