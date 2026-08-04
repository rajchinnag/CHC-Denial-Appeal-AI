"""
CHC Pro AI — Auth & Registration Schemas
All request/response Pydantic models for Layer 1.
"""
import re
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, EmailStr, field_validator, model_validator


# ── Controlled vocabularies ────────────────────────────────────────────────

ProviderType = Literal["individual", "organization"]
EntityType   = Literal["1", "2"]
ClaimFormType = Literal["ub04", "cms1500", "both"]

SpecialtyType = Literal[
    "internal_medicine", "family_medicine", "cardiology", "orthopedics",
    "neurology", "oncology", "radiology", "pathology", "emergency_medicine",
    "general_surgery", "psychiatry", "obstetrics_gynecology", "pediatrics",
    "urology", "gastroenterology", "pulmonology", "nephrology",
    "dermatology", "ophthalmology", "ent", "anesthesiology",
    "physical_medicine", "infectious_disease", "endocrinology",
    "rheumatology", "hematology", "geriatrics", "other",
]

VALID_STATES = {
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID",
    "IL","IN","IA","KS","KY","LA","ME","MD","MA","MI","MN","MS",
    "MO","MT","NE","NV","NH","NJ","NM","NY","NC","ND","OH","OK",
    "OR","PA","RI","SC","SD","TN","TX","UT","VT","VA","WA","WV",
    "WI","WY","DC",
}

PASSWORD_PATTERN = re.compile(
    r"^(?=.*[A-Z])(?=.*[a-z])(?=.*\d)"
    r"(?=.*[!@#$%^&*()\-_=+\[\]{};':\"\\|,.<>/?]).{12,}$"
)


# ═══════════════════════════════════════════════════════════════
# REGISTRATION SCHEMAS
# ═══════════════════════════════════════════════════════════════

class RegStep1Request(BaseModel):
    first_name:    str
    last_name:     str
    email:         EmailStr
    phone:         str
    organization:  Optional[str] = None
    provider_type: ProviderType = "individual"
    specialty:     SpecialtyType
    state:         str

    @field_validator("phone")
    @classmethod
    def v_phone(cls, v):
        d = re.sub(r"\D", "", v)
        if len(d) != 10:
            raise ValueError("Phone must be a 10-digit US number (digits only)")
        return d

    @field_validator("state")
    @classmethod
    def v_state(cls, v):
        u = v.upper()
        if u not in VALID_STATES:
            raise ValueError(f"'{v}' is not a valid 2-letter US state code")
        return u

    @field_validator("first_name", "last_name")
    @classmethod
    def v_name(cls, v):
        if len(v.strip()) < 1:
            raise ValueError("Name cannot be empty")
        if len(v) > 100:
            raise ValueError("Name too long (max 100 characters)")
        return v.strip()


class RegStep1Response(BaseModel):
    session_token: str
    message:       str
    expires_in:    int = 1800  # 30 minutes


class NPIDetail(BaseModel):
    npi:              str
    provider_name:    str
    entity_type:      str
    status:           str
    taxonomy_codes:   list[str]
    practice_address: dict
    enumeration_date: Optional[str] = None
    last_updated:     Optional[str] = None


class RegStep2Request(BaseModel):
    session_token: str
    npi:           str
    tax_id:        str
    entity_type:   EntityType = "1"

    @field_validator("npi")
    @classmethod
    def v_npi(cls, v):
        d = re.sub(r"\D", "", v)
        if len(d) != 10:
            raise ValueError("NPI must be exactly 10 digits")
        return d

    @field_validator("tax_id")
    @classmethod
    def v_tax(cls, v):
        d = re.sub(r"\D", "", v)
        if len(d) != 9:
            raise ValueError("Tax ID (EIN or SSN) must be exactly 9 digits")
        return d


class RegStep2Response(BaseModel):
    session_token:  str
    npi_verified:   bool
    oig_clear:      bool
    pecos_enrolled: bool
    npi_detail:     NPIDetail
    message:        str


class SendOTPRequest(BaseModel):
    session_token: str
    channel:       Literal["email", "sms"] = "email"


class SendOTPResponse(BaseModel):
    message:    str
    expires_in: int
    channel:    str


class VerifyOTPRequest(BaseModel):
    session_token: str
    otp_code:      str

    @field_validator("otp_code")
    @classmethod
    def v_otp(cls, v):
        if not re.match(r"^\d{6}$", v):
            raise ValueError("OTP must be exactly 6 digits")
        return v


class VerifyOTPResponse(BaseModel):
    session_token: str
    verified:      bool
    message:       str


class SetPasswordRequest(BaseModel):
    session_token:    str
    password:         str
    confirm_password: str

    @field_validator("password")
    @classmethod
    def v_pwd(cls, v):
        if not PASSWORD_PATTERN.match(v):
            raise ValueError(
                "Password must be at least 12 characters and contain: "
                "uppercase letter, lowercase letter, digit, and special character"
            )
        return v

    @model_validator(mode="after")
    def match(self):
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class Setup2FAResponse(BaseModel):
    totp_secret: str
    qr_code_url: str  # data:image/png;base64,...
    manual_key:  str
    message:     str


class Verify2FARequest(BaseModel):
    session_token: str
    totp_code:     str

    @field_validator("totp_code")
    @classmethod
    def v_totp(cls, v):
        if not re.match(r"^\d{6}$", v):
            raise ValueError("TOTP code must be exactly 6 digits")
        return v


class ESignatureRequest(BaseModel):
    session_token:       str
    full_legal_name:     str
    agreed_to_terms:     bool
    agreed_to_hipaa_baa: bool
    agreed_to_privacy:   bool
    signature_data:      str  # base64 PNG from canvas

    @field_validator("full_legal_name")
    @classmethod
    def v_name(cls, v):
        if len(v.strip()) < 2:
            raise ValueError("Full legal name required")
        return v.strip()

    @model_validator(mode="after")
    def all_agreed(self):
        missing = []
        if not self.agreed_to_terms:     missing.append("Terms of Service")
        if not self.agreed_to_hipaa_baa: missing.append("HIPAA BAA")
        if not self.agreed_to_privacy:   missing.append("Privacy Policy")
        if missing:
            raise ValueError(f"You must agree to: {', '.join(missing)}")
        return self


class ESignatureResponse(BaseModel):
    user_id:               str
    registration_complete: bool
    message:               str


# ═══════════════════════════════════════════════════════════════
# AUTH SCHEMAS
# ═══════════════════════════════════════════════════════════════

class LoginRequest(BaseModel):
    email:    EmailStr
    password: str


class UserProfile(BaseModel):
    user_id:               str
    email:                 str
    first_name:            str
    last_name:             str
    organization:          Optional[str] = None
    specialty:             str
    state:                 str
    npi:                   str
    pecos_enrolled:        bool = False
    claim_form_preference: Optional[ClaimFormType] = None
    created_at:            datetime
    is_verified:           bool
    mfa_enabled:           bool


class LoginResponse(BaseModel):
    requires_2fa:  bool
    mfa_session:   Optional[str] = None
    access_token:  Optional[str] = None
    refresh_token: Optional[str] = None
    token_type:    str = "bearer"
    expires_in:    int = 3600
    user:          Optional[UserProfile] = None


class MFALoginRequest(BaseModel):
    mfa_session: str
    totp_code:   str

    @field_validator("totp_code")
    @classmethod
    def v_totp(cls, v):
        if not re.match(r"^\d{6}$", v):
            raise ValueError("TOTP code must be 6 digits")
        return v


class TokenRefreshRequest(BaseModel):
    refresh_token: str


class TokenRefreshResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    expires_in:   int = 3600


class PasswordResetInitRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirmRequest(BaseModel):
    email:            EmailStr
    reset_code:       str
    new_password:     str
    confirm_password: str

    @field_validator("new_password")
    @classmethod
    def v_pwd(cls, v):
        if not PASSWORD_PATTERN.match(v):
            raise ValueError(
                "Password must be at least 12 characters with uppercase, "
                "lowercase, digit, and special character"
            )
        return v

    @model_validator(mode="after")
    def match(self):
        if self.new_password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self
