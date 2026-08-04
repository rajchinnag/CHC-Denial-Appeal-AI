"""
CHC Pro AI — JWT Auth Middleware
Validates Cognito JWT Bearer tokens.
Injects AuthenticatedUser into every protected route.
"""
import base64, json, logging, time
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.services.otp_service import blocklist_check
from config import get_settings

log      = logging.getLogger(__name__)
settings = get_settings()
bearer   = HTTPBearer()


class AuthenticatedUser:
    """Hydrated from JWT payload. Attached to request state."""
    def __init__(self, payload: dict):
        self.user_id     = payload.get("sub", "")
        self.email       = payload.get("email") or payload.get("username", "")
        self.npi         = payload.get("custom:npi", "")
        self.specialty   = payload.get("custom:specialty", "")
        self.state       = payload.get("custom:state", "")
        self.is_verified = payload.get("email_verified") == "true"
        self.mfa_enabled = payload.get("custom:mfa_enabled") == "true"
        self._payload    = payload


def _decode_payload(token: str) -> dict:
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Malformed JWT")
    pad     = "=" * (4 - len(parts[1]) % 4)
    payload = base64.urlsafe_b64decode(parts[1] + pad)
    return json.loads(payload)


async def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer),
) -> AuthenticatedUser:
    """FastAPI dependency — use as: user = Depends(get_current_user)"""

    unauth = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token. Please log in again.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = _decode_payload(creds.credentials)
    except Exception:
        raise unauth

    # Check expiry
    if payload.get("exp", 0) < time.time():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your session has expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Validate Cognito issuer
    expected_iss = (
        f"https://cognito-idp.{settings.AWS_REGION}.amazonaws.com/"
        f"{settings.COGNITO_USER_POOL_ID}"
    )
    if payload.get("iss") != expected_iss:
        raise unauth

    # Validate audience
    if payload.get("client_id") != settings.COGNITO_CLIENT_ID:
        raise unauth

    # Check logout blocklist
    user_id = payload.get("sub", "")
    if await blocklist_check(user_id):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="You have been logged out. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return AuthenticatedUser(payload)


async def require_verified(
    user: AuthenticatedUser = Depends(get_current_user),
) -> AuthenticatedUser:
    """Extra dependency — requires email_verified=true."""
    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email address not verified. Please complete verification.",
        )
    return user
