"""
CHC Pro AI — Auth Routes
POST /api/v1/auth/login
POST /api/v1/auth/login/mfa
POST /api/v1/auth/refresh
POST /api/v1/auth/logout
POST /api/v1/auth/password/reset
POST /api/v1/auth/password/confirm
GET  /api/v1/auth/me
"""
import base64, json, logging
from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.middleware.auth_middleware import AuthenticatedUser, get_current_user
from app.schemas.auth_schemas import (
    LoginRequest, LoginResponse, MFALoginRequest,
    PasswordResetConfirmRequest, PasswordResetInitRequest,
    TokenRefreshRequest, TokenRefreshResponse, UserProfile,
)
from app.services.cognito_service import cognito, CognitoError
from app.services.otp_service import (
    blocklist_add, mfa_session_create, mfa_session_delete, mfa_session_get,
)
from config import get_settings
from datetime import datetime

log      = logging.getLogger(__name__)
settings = get_settings()

router  = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])
limiter = Limiter(key_func=get_remote_address)


# ── Login ──────────────────────────────────────────────────────────────────

@router.post("/login", response_model=LoginResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def login(request: Request, body: LoginRequest):
    try:
        result = cognito.initiate_auth(body.email, body.password)
    except CognitoError as e:
        log.error(f"MFA failed: {e.message} code={e.code}")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, e.message)

    if result.get("requires_mfa"):
        mfa_token = await mfa_session_create(body.email, result["session"])
        log.info(f"MFA session stored: {mfa_token[:10]} for {body.email}")
        log.info(f"MFA session stored: {mfa_token[:10]} for {body.email}")
        return LoginResponse(requires_2fa=True, mfa_session=mfa_token)

    attrs = cognito.get_user(body.email) or {}
    return LoginResponse(
        requires_2fa=False,
        access_token=result["access_token"],
        refresh_token=result["refresh_token"],
        expires_in=result["expires_in"],
        user=_build_profile(attrs),
    )


# ── MFA Challenge ──────────────────────────────────────────────────────────

@router.post("/login/mfa", response_model=LoginResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def login_mfa(request: Request, body: MFALoginRequest):
    session_data = await mfa_session_get(body.mfa_session)
    if not session_data:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "MFA session expired or invalid. Please log in again."
        )

    email           = session_data["email"]
    cognito_session = session_data["cognito_session"]

    try:
        tokens = cognito.respond_mfa(email, cognito_session, body.totp_code)
    except CognitoError as e:
        log.error(f"MFA failed: {e.message} code={e.code}")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, e.message)

    await mfa_session_delete(body.mfa_session)

    attrs = cognito.get_user(email) or {}
    return LoginResponse(
        requires_2fa=False,
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        expires_in=tokens["expires_in"],
        user=_build_profile(attrs),
    )


# ── Token Refresh ──────────────────────────────────────────────────────────

@router.post("/refresh", response_model=TokenRefreshResponse)
@limiter.limit("10/minute")
async def refresh(request: Request, body: TokenRefreshRequest):
    # Extract email from refresh token payload (needed for SECRET_HASH)
    try:
        parts   = body.refresh_token.split(".")
        pad     = "=" * (4 - len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + pad))
        email   = payload.get("email") or payload.get("username", "")
    except Exception:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Malformed refresh token.")

    try:
        tokens = cognito.refresh(body.refresh_token, email)
    except CognitoError as e:
        log.error(f"MFA failed: {e.message} code={e.code}")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, e.message)

    return TokenRefreshResponse(
        access_token=tokens["access_token"],
        expires_in=tokens["expires_in"],
    )


# ── Logout ─────────────────────────────────────────────────────────────────

@router.post("/logout")
async def logout(user: AuthenticatedUser = Depends(get_current_user)):
    # Add to Redis blocklist for the remaining access token lifetime
    ttl = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
    await blocklist_add(user.user_id, ttl)
    log.info(f"User logged out: {user.email}")
    return {"message": "Logged out successfully."}


# ── Password Reset ─────────────────────────────────────────────────────────

@router.post("/password/reset")
@limiter.limit("3/minute")
async def password_reset(request: Request, body: PasswordResetInitRequest):
    cognito.forgot_password(body.email)
    # Always 200 — never reveal if email exists
    return {
        "message": "If an account exists with that email address, "
                   "a password reset code has been sent."
    }


@router.post("/password/confirm")
@limiter.limit("5/minute")
async def password_confirm(request: Request, body: PasswordResetConfirmRequest):
    try:
        cognito.confirm_forgot_password(body.email, body.reset_code, body.new_password)
    except CognitoError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, e.message)
    return {
        "message": "Password updated successfully. Please log in with your new password."
    }


# ── Current User Profile ───────────────────────────────────────────────────

@router.get("/me", response_model=UserProfile)
async def get_me(user: AuthenticatedUser = Depends(get_current_user)):
    attrs = cognito.get_user(user.email) or {}
    return _build_profile(attrs)


# ── Internal helper ────────────────────────────────────────────────────────

def _build_profile(attrs: dict) -> UserProfile:
    return UserProfile(
        user_id=attrs.get("sub", ""),
        email=attrs.get("email", ""),
        first_name=attrs.get("given_name", ""),
        last_name=attrs.get("family_name", ""),
        organization=attrs.get("custom:organization"),
        specialty=attrs.get("custom:specialty", ""),
        state=attrs.get("custom:state", ""),
        npi=attrs.get("custom:npi", ""),
        pecos_enrolled=attrs.get("custom:pecos", "False") == "True",
        claim_form_preference=attrs.get("custom:claim_form"),
        created_at=datetime.now(),
        is_verified=attrs.get("email_verified", "false") == "true",
        mfa_enabled=attrs.get("custom:mfa_enabled", "false") == "true",
    )





