from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv
import os

load_dotenv()

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    anyapi_api_key: str = os.getenv("ANYAPI_API_KEY", "")
    results_dir: str = "results"

settings = Settings()
