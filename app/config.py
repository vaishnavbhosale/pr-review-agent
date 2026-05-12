from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Required keys (no default values)
    GITHUB_TOKEN: str
    GITHUB_WEBHOOK_SECRET: str
    GROQ_API_KEY: str
    GEMINI_API_KEY: str
    
    # Optional config (with default values)
    DATABASE_URL: str = "sqlite:///./reviews.db"
    LOG_LEVEL: str = "INFO"
    AGENTIC_MODE: bool = False

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # This prevents Pydantic from crashing if you have extra variables in your .env

# Instantiate it exactly ONCE at the very bottom
settings = Settings()