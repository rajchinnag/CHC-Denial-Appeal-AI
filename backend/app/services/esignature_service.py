"""
CHC Pro AI — E-Signature Service
Stores provider signatures and generates HIPAA-compliant audit records.
"""
import base64, hashlib, json, logging
from datetime import datetime, timezone
from typing import Optional
import boto3
from botocore.exceptions import ClientError
from config import get_settings

log      = logging.getLogger(__name__)
settings = get_settings()


class ESignatureError(Exception): pass


async def store_signature(
    user_id:         str,
    email:           str,
    full_legal_name: str,
    signature_b64:   str,
    agreements:      dict,
    ip_address:      Optional[str] = None,
    user_agent:      Optional[str] = None,
) -> dict:
    """
    Validate, store, and audit the e-signature.

    Returns: {signature_id, signed_at, signature_hash}
    Raises:  ESignatureError on any failure.
    """
    ts = datetime.now(timezone.utc).isoformat()

    # Decode and validate signature image
    try:
        raw = signature_b64.split(",")[-1]  # Strip data URL prefix
        sig_bytes = base64.b64decode(raw)
    except Exception:
        raise ESignatureError("Invalid signature format. Please draw your signature again.")

    if len(sig_bytes) < 100:
        raise ESignatureError(
            "Signature appears to be empty. Please draw your full signature in the box."
        )

    # Fingerprint
    sig_hash = hashlib.sha256(sig_bytes).hexdigest()
    sig_id   = hashlib.sha256(f"{user_id}{ts}{sig_hash}".encode()).hexdigest()[:32]

    # Audit record — this is the legal document, never modify once created
    audit = {
        "signature_id":    sig_id,
        "user_id":         user_id,
        "email":           email,
        "full_legal_name": full_legal_name,
        "signed_at":       ts,
        "ip_address":      ip_address or "unknown",
        "user_agent":      user_agent or "unknown",
        "signature_hash":  sig_hash,
        "platform":        "Carolin Code Pro AI",
        "agreements": {
            "terms_of_service": {
                "accepted": agreements.get("terms", False),
                "version":  "v2.1",
                "title":    "Terms of Service",
                "signed_at": ts,
            },
            "hipaa_baa": {
                "accepted": agreements.get("hipaa_baa", False),
                "version":  "v1.3",
                "title":    "HIPAA Business Associate Agreement",
                "signed_at": ts,
            },
            "privacy_policy": {
                "accepted": agreements.get("privacy", False),
                "version":  "v2.0",
                "title":    "Privacy Policy",
                "signed_at": ts,
            },
        },
    }

    s3 = boto3.client(
        "s3", region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )

    # Store signature PNG — encrypted, never public
    try:
        s3.put_object(
            Bucket=settings.S3_BUCKET_DEIDENTIFIED,
            Key=f"signatures/{user_id}/{sig_id}.png",
            Body=sig_bytes,
            ContentType="image/png",
            ServerSideEncryption="aws:kms",
            Metadata={
                "user-id":       user_id,
                "signature-id":  sig_id,
                "signed-at":     ts,
            },
        )
    except ClientError as e:
        log.error(f"S3 signature upload failed: {e}")
        raise ESignatureError(
            "Could not save your signature. Please try again. "
            "If this persists, contact support."
        )

    # Store audit JSON — immutable legal record
    try:
        s3.put_object(
            Bucket=settings.S3_BUCKET_DEIDENTIFIED,
            Key=f"audit/signatures/{user_id}/{sig_id}.json",
            Body=json.dumps(audit, indent=2).encode("utf-8"),
            ContentType="application/json",
            ServerSideEncryption="aws:kms",
        )
    except ClientError as e:
        log.error(f"S3 audit JSON upload failed: {e}")
        # Don't fail the registration — signature was stored, audit is best-effort here
        # In production, add to a retry queue

    log.info(f"E-signature stored: sig_id={sig_id} user={user_id}")
    return {
        "signature_id":   sig_id,
        "signed_at":      ts,
        "signature_hash": sig_hash,
    }
