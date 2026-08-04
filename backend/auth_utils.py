"""Authentication utilities: bcrypt password hashing, JWT tokens, TOTP MFA."""
import os
import secrets
import base64
from datetime import datetime, timezone, timedelta
from io import BytesIO

import bcrypt
import jwt
import pyotp
import qrcode

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_MINUTES = 15
REFRESH_TOKEN_DAYS = 7
MFA_PENDING_MINUTES = 10


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def _secret() -> str:
    return os.environ["JWT_SECRET"]


def create_access_token(user_id: str, email: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_MINUTES),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, _secret(), algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "type": "refresh",
        "exp": datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_DAYS),
    }
    return jwt.encode(payload, _secret(), algorithm=JWT_ALGORITHM)


def create_mfa_challenge_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "type": "mfa_challenge",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=MFA_PENDING_MINUTES),
    }
    return jwt.encode(payload, _secret(), algorithm=JWT_ALGORITHM)


def create_registration_token(user_id: str, stage: str) -> str:
    """Short-lived token used during the registration multi-step flow."""
    payload = {
        "sub": user_id,
        "type": "registration",
        "stage": stage,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
    }
    return jwt.encode(payload, _secret(), algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, _secret(), algorithms=[JWT_ALGORITHM])


# ----- TOTP (RFC 6238) -----

def new_totp_secret() -> str:
    return pyotp.random_base32()


def totp_provisioning_uri(secret: str, account_email: str, issuer: str = "CHC Pro AI") -> str:
    return pyotp.totp.TOTP(secret).provisioning_uri(name=account_email, issuer_name=issuer)


def verify_totp(secret: str, code: str) -> bool:
    if not secret or not code:
        return False
    try:
        return pyotp.TOTP(secret).verify(str(code).strip(), valid_window=1)
    except Exception:
        return False


def qr_png_base64(data: str) -> str:
    qr = qrcode.QRCode(box_size=6, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#003F87", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def generate_otp(digits: int = 6) -> str:
    return "".join(str(secrets.randbelow(10)) for _ in range(digits))


# ----- Validators -----

def valid_password(pw: str) -> tuple[bool, str]:
    if not pw or len(pw) < 12:
        return False, "Password must be at least 12 characters."
    if not any(c.isupper() for c in pw):
        return False, "Password must include an uppercase letter."
    if not any(c.islower() for c in pw):
        return False, "Password must include a lowercase letter."
    if not any(c.isdigit() for c in pw):
        return False, "Password must include a number."
    if not any(c in "!@#$%^&*()_-+=[]{}|;:,.<>?/~`" for c in pw):
        return False, "Password must include a special character."
    return True, ""


def valid_npi(npi: str) -> bool:
    return bool(npi) and npi.isdigit() and len(npi) == 10


def valid_ein(ein: str) -> bool:
    cleaned = (ein or "").replace("-", "")
    return cleaned.isdigit() and len(cleaned) == 9
