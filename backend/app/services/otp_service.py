"""
CHC Pro AI — OTP + TOTP + Registration Session Service
"""
import base64, io, json, logging, secrets
from typing import Optional
import boto3, pyotp, qrcode
from botocore.exceptions import ClientError
import redis.asyncio as aioredis
from config import get_settings

log      = logging.getLogger(__name__)
settings = get_settings()

_redis: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = await aioredis.from_url(
            settings.REDIS_URL, encoding="utf-8", decode_responses=True, socket_timeout=5, socket_connect_timeout=5
        )
    return _redis


# ── Custom exceptions ──────────────────────────────────────────────────────

class OTPRateLimitError(Exception): pass
class OTPExpiredError(Exception):   pass
class OTPInvalidError(Exception):   pass
class OTPDeliveryError(Exception):  pass
class SessionExpiredError(Exception): pass


# ═══════════════════════════════════════════════════════════════
# OTP — generate, store, verify
# ═══════════════════════════════════════════════════════════════

async def generate_otp(email: str) -> str:
    """
    Generate a cryptographically secure 6-digit OTP.
    Rate limit: max OTP_MAX_ATTEMPTS sends per OTP_RATE_WINDOW_SECONDS.
    """
    r = await get_redis()
    attempts_key = f"chc:otp:attempts:{email}"
    attempts = await r.get(attempts_key)

    if attempts and int(attempts) >= settings.OTP_MAX_ATTEMPTS:
        window_min = settings.OTP_RATE_WINDOW_SECONDS // 60
        raise OTPRateLimitError(
            f"Too many verification code requests. "
            f"Please wait {window_min} minutes before requesting another code."
        )

    otp = "".join(str(secrets.randbelow(10)) for _ in range(settings.OTP_LENGTH))

    pipe = r.pipeline()
    pipe.setex(f"chc:otp:{email}", settings.OTP_EXPIRE_SECONDS, otp)
    pipe.incr(attempts_key)
    pipe.expire(attempts_key, settings.OTP_RATE_WINDOW_SECONDS)
    await pipe.execute()

    return otp


async def verify_otp(email: str, provided: str) -> bool:
    """
    Verify OTP using constant-time comparison.
    Deletes OTP on success (single-use).
    """
    r      = await get_redis()
    stored = await r.get(f"chc:otp:{email}")

    if stored is None:
        raise OTPExpiredError(
            "Verification code has expired or was not issued. "
            "Please request a new code."
        )
    if not secrets.compare_digest(stored, provided):
        raise OTPInvalidError("Incorrect verification code. Please check and try again.")

    await r.delete(f"chc:otp:{email}")
    return True


async def send_otp_email(email: str, first_name: str, otp: str) -> None:
    """Send OTP via AWS SES."""
    ses = boto3.client(
        "ses", region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )
    expire_min = settings.OTP_EXPIRE_SECONDS // 60
    html = f"""<!DOCTYPE html>
<html><body style="font-family:'IBM Plex Sans',Arial,sans-serif;max-width:520px;margin:40px auto;color:#0F172A;background:#fff">
<div style="background:#003F87;padding:24px 32px;border-radius:8px 8px 0 0">
  <p style="color:#fff;font-size:20px;font-weight:600;margin:0">Carolin Code Pro AI</p>
</div>
<div style="padding:32px;border:1px solid #E2E8F0;border-top:none;border-radius:0 0 8px 8px">
  <h2 style="color:#003F87;margin-top:0">Verify your email address</h2>
  <p>Hi {first_name},</p>
  <p>Use the code below to complete your registration. It expires in <strong>{expire_min} minutes</strong>.</p>
  <div style="background:#DBEAFE;border-radius:8px;padding:24px;text-align:center;margin:28px 0">
    <span style="font-family:'IBM Plex Mono',monospace;font-size:38px;font-weight:700;
                 letter-spacing:14px;color:#003F87;display:block">{otp}</span>
  </div>
  <p style="color:#64748B;font-size:13px">
    If you did not request this code, you can safely ignore this email.<br>
    Never share this code with anyone.
  </p>
  <hr style="border:none;border-top:1px solid #E2E8F0;margin:24px 0">
  <p style="color:#94A3B8;font-size:12px;margin:0">
    Carolin Code Pro AI · HIPAA-compliant medical coding platform<br>
    Do not reply to this email.
  </p>
</div>
</body></html>"""

    text = (
        f"Hi {first_name},\n\n"
        f"Your Carolin Code Pro AI verification code is: {otp}\n\n"
        f"This code expires in {expire_min} minutes.\n\n"
        f"If you did not request this, please ignore this email."
    )
    try:
        ses.send_email(
            Source=settings.SES_FROM_EMAIL,
            Destination={"ToAddresses": [email]},
            Message={
                "Subject": {"Data": "Your Carolin Code Pro AI verification code"},
                "Body": {
                    "Text": {"Data": text},
                    "Html": {"Data": html},
                },
            },
            ConfigurationSetName=settings.SES_CONFIGURATION_SET,
        )
        log.info(f"OTP email sent to {email}")
    except ClientError as e:
        log.error(f"SES failed for {email}: {e}")
        raise OTPDeliveryError(
            "Could not send verification email. Please try again or contact support."
        )


async def send_otp_sms(phone: str, otp: str) -> None:
    """Send OTP via AWS SNS SMS."""
    sns = boto3.client(
        "sns", region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )
    try:
        sns.publish(
            PhoneNumber=f"+1{phone}",
            Message=f"Carolin Code Pro AI: Your code is {otp}. Expires in 5 min. Do not share.",
            MessageAttributes={
                "AWS.SNS.SMS.SMSType": {
                    "DataType": "String", "StringValue": "Transactional"
                }
            },
        )
        log.info(f"OTP SMS sent to +1{phone}")
    except ClientError as e:
        log.error(f"SNS SMS failed: {e}")
        raise OTPDeliveryError("Could not send SMS. Please use email verification instead.")


# ═══════════════════════════════════════════════════════════════
# TOTP 2FA
# ═══════════════════════════════════════════════════════════════

def new_totp_secret() -> str:
    return pyotp.random_base32()


def totp_qr_base64(email: str, secret: str) -> str:
    """Generate QR code PNG as base64 data URL for display in browser."""
    uri = pyotp.TOTP(secret, interval=settings.TOTP_INTERVAL).provisioning_uri(
        name=email, issuer_name=settings.TOTP_ISSUER
    )
    qr = qrcode.QRCode(version=1, box_size=8, border=2,
                       error_correction=qrcode.constants.ERROR_CORRECT_L)
    qr.add_data(uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#003F87", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def verify_totp(secret: str, code: str) -> bool:
    """Verify TOTP with ±30s clock drift tolerance (window=1)."""
    return pyotp.TOTP(secret, interval=settings.TOTP_INTERVAL).verify(code, valid_window=1)


# ═══════════════════════════════════════════════════════════════
# Registration session (Redis-backed multi-step state)
# ═══════════════════════════════════════════════════════════════

async def session_create(email: str, data: dict) -> str:
    r     = await get_redis()
    token = secrets.token_urlsafe(32)
    data["email"] = email
    await r.setex(f"chc:reg:{token}", 1800, json.dumps(data))
    return token


async def session_get(token: str) -> Optional[dict]:
    r   = await get_redis()
    raw = await r.get(f"chc:reg:{token}")
    return json.loads(raw) if raw else None


async def session_update(token: str, updates: dict) -> None:
    r   = await get_redis()
    raw = await r.get(f"chc:reg:{token}")
    if raw is None:
        raise SessionExpiredError("Registration session expired. Please start again from step 1.")
    data = json.loads(raw)
    data.update(updates)
    ttl  = await r.ttl(f"chc:reg:{token}")
    await r.setex(f"chc:reg:{token}", max(ttl, 60), json.dumps(data))


async def session_delete(token: str) -> None:
    r = await get_redis()
    await r.delete(f"chc:reg:{token}")


async def mfa_session_create(email: str, cognito_session: str) -> str:
    r     = await get_redis()
    token = secrets.token_urlsafe(32)
    await r.setex(
        f"chc:mfa:{token}", 300,
        json.dumps({"email": email, "cognito_session": cognito_session})
    )
    return token


async def mfa_session_get(token: str) -> Optional[dict]:
    r   = await get_redis()
    raw = await r.get(f"chc:mfa:{token}")
    return json.loads(raw) if raw else None


async def mfa_session_delete(token: str) -> None:
    r = await get_redis()
    await r.delete(f"chc:mfa:{token}")


async def blocklist_add(user_id: str, ttl_seconds: int) -> None:
    r = await get_redis()
    await r.setex(f"chc:blocklist:{user_id}", ttl_seconds, "1")


async def blocklist_check(user_id: str) -> bool:
    r = await get_redis()
    return bool(await r.get(f"chc:blocklist:{user_id}"))



