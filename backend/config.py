"""
CHC Denial Appeal AI — Auth configuration.

This is separate from app/config.py (which holds Gemini/PHI/ALLOWED_ORIGINS
settings for the claims pipeline). This file exists because the auth code
(copied over from CHC-Pro-Ai) imports `from config import get_settings`.
Both config files coexist and are read independently — nothing here overrides
app/config.py, and nothing there overrides this.
"""
import os
from functools import lru_cache
from dotenv import load_dotenv

load_dotenv()


class AuthSettings:
    # ── AWS / Cognito ──────────────────────────────────────────────
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
    AWS_ACCESS_KEY_ID: str = os.getenv("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")

    COGNITO_USER_POOL_ID: str = os.getenv("COGNITO_USER_POOL_ID", "")
    COGNITO_CLIENT_ID: str = os.getenv("COGNITO_CLIENT_ID", "")
    COGNITO_CLIENT_SECRET: str = os.getenv("COGNITO_CLIENT_SECRET", "")

    # ── JWT ────────────────────────────────────────────────────────
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60")
    )

    # ── OTP (email/SMS one-time codes) ────────────────────────────
    OTP_LENGTH: int = int(os.getenv("OTP_LENGTH", "6"))
    OTP_EXPIRE_SECONDS: int = int(os.getenv("OTP_EXPIRE_SECONDS", "300"))
    OTP_MAX_ATTEMPTS: int = int(os.getenv("OTP_MAX_ATTEMPTS", "5"))
    OTP_RATE_WINDOW_SECONDS: int = int(os.getenv("OTP_RATE_WINDOW_SECONDS", "900"))

    # ── TOTP (authenticator app MFA) ──────────────────────────────
    TOTP_ISSUER: str = os.getenv("TOTP_ISSUER", "CHC Denial Appeal AI")
    TOTP_INTERVAL: int = int(os.getenv("TOTP_INTERVAL", "30"))

    # ── SES (email delivery, used for OTP emails) ─────────────────
    SES_FROM_EMAIL: str = os.getenv("SES_FROM_EMAIL", "")
    SES_CONFIGURATION_SET: str = os.getenv("SES_CONFIGURATION_SET", "")

    # ── Rate limiting (slowapi) ────────────────────────────────────
    RATE_LIMIT_AUTH: str = os.getenv("RATE_LIMIT_AUTH", "10/minute")
    RATE_LIMIT_REGISTER: str = os.getenv("RATE_LIMIT_REGISTER", "5/minute")
    RATE_LIMIT_OTP: str = os.getenv("RATE_LIMIT_OTP", "5/minute")

    # ── Redis (session/OTP storage — reuse the same Upstash Redis
    #    already wired up for the claims feature) ──────────────────
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")

    # ── S3 (e-signature storage) ───────────────────────────────────
    S3_BUCKET_DEIDENTIFIED: str = os.getenv("S3_BUCKET_DEIDENTIFIED", "")

    # ── NPI / OIG / PECOS verification (provider registration) ─────
    NPPES_API_BASE: str = os.getenv("NPPES_API_BASE", "https://npiregistry.cms.hhs.gov/api/")
    NPPES_API_VERSION: str = os.getenv("NPPES_API_VERSION", "2.1")
    OIG_LEIE_API_BASE: str = os.getenv("OIG_LEIE_API_BASE", "")
    PECOS_API_BASE: str = os.getenv("PECOS_API_BASE", "")


@lru_cache
def get_settings() -> AuthSettings:
    return AuthSettings()
