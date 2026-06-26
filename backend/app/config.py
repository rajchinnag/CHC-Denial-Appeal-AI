"""
Configuration for CHC Denial Appeal AI.

IMPORTANT — read before handling real patient data:
The standard Gemini API (GEMINI_MODE=api_key, using a Google AI Studio key) does
NOT come with a HIPAA BAA. It's fine for building and testing this app with
synthetic / de-identified test data. Before any real PHI flows through this
pipeline in production, switch GEMINI_MODE to "vertex" and complete a BAA with
Google Cloud for Vertex AI. The code path is identical either way — only the
client setup differs — so this switch is a config change, not a rewrite.
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # "api_key" -> google-generativeai SDK, fast to set up, NO BAA, test data only
    # "vertex"  -> Vertex AI SDK, requires GCP project + BAA, use for real PHI
    GEMINI_MODE: str = os.getenv("GEMINI_MODE", "api_key")

    # Used when GEMINI_MODE=api_key
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

    # Used when GEMINI_MODE=vertex
    GCP_PROJECT_ID: str = os.getenv("GCP_PROJECT_ID", "")
    GCP_LOCATION: str = os.getenv("GCP_LOCATION", "us-central1")
    # GOOGLE_APPLICATION_CREDENTIALS env var should point at the service account JSON

    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    # Token map encryption key for PHI re-identification (Fernet key, base64, 32 bytes)
    PHI_MAP_SECRET: str = os.getenv("PHI_MAP_SECRET", "")

    ALLOWED_ORIGINS: list = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")


settings = Settings()
