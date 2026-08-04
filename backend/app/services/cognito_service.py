"""
CHC Pro AI — AWS Cognito Service
Full wrapper for Cognito user pool operations.
"""
import base64, hashlib, hmac, logging
from typing import Optional
import boto3
from botocore.exceptions import ClientError
from config import get_settings

log      = logging.getLogger(__name__)
settings = get_settings()


class CognitoError(Exception):
    def __init__(self, message: str, code: str = "AUTH_ERROR"):
        self.message = message
        self.code    = code
        super().__init__(message)


def _secret_hash(username: str) -> str:
    msg = (username + settings.COGNITO_CLIENT_ID).encode()
    dig = hmac.new(settings.COGNITO_CLIENT_SECRET.encode(), msg, hashlib.sha256).digest()
    return base64.b64encode(dig).decode()


def _client():
    return boto3.client(
        "cognito-idp", region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )


class CognitoService:

    def __init__(self):
        self.c    = _client()
        self.pool = settings.COGNITO_USER_POOL_ID
        self.cid  = settings.COGNITO_CLIENT_ID

    # ── User creation ──────────────────────────────────────────

    def create_user(self, email: str, temp_password: str, attrs: dict) -> str:
        """Create user, return Cognito sub (user_id)."""
        attr_list = [
            {"Name": "email",          "Value": email},
            {"Name": "email_verified", "Value": "true"},
        ] + [{"Name": k, "Value": str(v)} for k, v in attrs.items()]

        try:
            resp = self.c.admin_create_user(
                UserPoolId=self.pool, Username=email,
                TemporaryPassword=temp_password,
                UserAttributes=attr_list,
                MessageAction="SUPPRESS",
            )
            for a in resp["User"]["Attributes"]:
                if a["Name"] == "sub":
                    return a["Value"]
            return resp["User"]["Username"]
        except ClientError as e:
            code = e.response["Error"]["Code"]
            if code == "UsernameExistsException":
                raise CognitoError("An account with this email already exists.", "DUPLICATE_EMAIL")
            raise CognitoError(str(e), code)

    def set_permanent_password(self, email: str, password: str) -> None:
        try:
            self.c.admin_set_user_password(
                UserPoolId=self.pool, Username=email,
                Password=password, Permanent=True,
            )
        except ClientError as e:
            raise CognitoError(str(e), e.response["Error"]["Code"])

    def update_attributes(self, email: str, attrs: dict) -> None:
        try:
            self.c.admin_update_user_attributes(
                UserPoolId=self.pool, Username=email,
                UserAttributes=[{"Name": k, "Value": str(v)} for k, v in attrs.items()],
            )
        except ClientError as e:
            raise CognitoError(str(e), e.response["Error"]["Code"])

    def enable_mfa(self, email: str) -> None:
        try:
            self.c.admin_set_user_mfa_preference(
                UserPoolId=self.pool, Username=email,
                SoftwareTokenMfaSettings={"Enabled": True, "PreferredMfa": True},
            )
        except ClientError as e:
            raise CognitoError(str(e), e.response["Error"]["Code"])

    def delete_user(self, email: str) -> None:
        try:
            self.c.admin_delete_user(UserPoolId=self.pool, Username=email)
        except ClientError:
            pass  # Best-effort rollback

    # ── Authentication ─────────────────────────────────────────

    def initiate_auth(self, email: str, password: str) -> dict:
        try:
            resp = self.c.initiate_auth(
                AuthFlow="USER_PASSWORD_AUTH",
                AuthParameters={
                    "USERNAME":    email,
                    "PASSWORD":    password,
                    "SECRET_HASH": _secret_hash(email),
                },
                ClientId=self.cid,
            )
        except ClientError as e:
            code = e.response["Error"]["Code"]
            msgs = {
                "NotAuthorizedException":    "Incorrect email or password.",
                "UserNotFoundException":     "Incorrect email or password.",
                "UserNotConfirmedException": "Account not yet verified. Please contact support.",
                "TooManyRequestsException":  "Too many attempts. Please wait and try again.",
                "UserDisabledException":     "This account has been disabled. Please contact support.",
            }
            raise CognitoError(msgs.get(code, "Authentication failed. Please try again."), code)

        challenge = resp.get("ChallengeName")
        if challenge == "SOFTWARE_TOKEN_MFA":
            return {"requires_mfa": True, "session": resp["Session"]}
        if challenge == "NEW_PASSWORD_REQUIRED":
            raise CognitoError("Password change required. Please contact support.", challenge)
        if challenge:
            raise CognitoError(f"Unexpected auth challenge: {challenge}", challenge)

        return {"requires_mfa": False, **self._extract(resp["AuthenticationResult"])}

    def respond_mfa(self, email: str, session: str, code: str) -> dict:
        try:
            resp = self.c.respond_to_auth_challenge(
                ClientId=self.cid,
                ChallengeName="SOFTWARE_TOKEN_MFA",
                Session=session,
                ChallengeResponses={
                    "USERNAME":                email,
                    "SOFTWARE_TOKEN_MFA_CODE": code,
                    "SECRET_HASH":             _secret_hash(email),
                },
            )
        except ClientError as e:
            c = e.response["Error"]["Code"]
            if c in ("CodeMismatchException", "NotAuthorizedException"):
                raise CognitoError("Incorrect TOTP code. Check your authenticator app.", c)
            if c == "ExpiredCodeException":
                raise CognitoError("TOTP code expired. Please generate a new one.", c)
            raise CognitoError(str(e), c)
        return self._extract(resp["AuthenticationResult"])

    def refresh(self, refresh_token: str, email: str) -> dict:
        try:
            resp = self.c.initiate_auth(
                AuthFlow="REFRESH_TOKEN_AUTH",
                AuthParameters={
                    "REFRESH_TOKEN": refresh_token,
                    "SECRET_HASH":   _secret_hash(email),
                },
                ClientId=self.cid,
            )
        except ClientError as e:
            raise CognitoError("Session expired. Please log in again.", "INVALID_REFRESH")
        return self._extract(resp["AuthenticationResult"])

    # ── Password reset ─────────────────────────────────────────

    def forgot_password(self, email: str) -> None:
        try:
            self.c.forgot_password(
                ClientId=self.cid, Username=email,
                SecretHash=_secret_hash(email),
            )
        except ClientError as e:
            if e.response["Error"]["Code"] != "UserNotFoundException":
                raise CognitoError(str(e), e.response["Error"]["Code"])
            # Silently ignore — don't reveal if email exists

    def confirm_forgot_password(self, email: str, code: str, new_password: str) -> None:
        try:
            self.c.confirm_forgot_password(
                ClientId=self.cid, Username=email,
                ConfirmationCode=code, Password=new_password,
                SecretHash=_secret_hash(email),
            )
        except ClientError as e:
            c = e.response["Error"]["Code"]
            msgs = {
                "CodeMismatchException":    "Invalid reset code. Please check and try again.",
                "ExpiredCodeException":     "Reset code has expired. Please request a new one.",
                "InvalidPasswordException": "Password does not meet the requirements.",
                "LimitExceededException":   "Too many attempts. Please wait and try again.",
            }
            raise CognitoError(msgs.get(c, str(e)), c)

    # ── Lookup ─────────────────────────────────────────────────

    def get_user(self, email: str) -> Optional[dict]:
        try:
            resp = self.c.admin_get_user(UserPoolId=self.pool, Username=email)
            attrs = {a["Name"]: a["Value"] for a in resp["UserAttributes"]}
            attrs["_status"]  = resp["UserStatus"]
            attrs["_enabled"] = resp["Enabled"]
            return attrs
        except ClientError as e:
            if e.response["Error"]["Code"] == "UserNotFoundException":
                return None
            raise CognitoError(str(e), e.response["Error"]["Code"])

    def user_exists(self, email: str) -> bool:
        return self.get_user(email) is not None

    # ── Internal ───────────────────────────────────────────────

    @staticmethod
    def _extract(r: dict) -> dict:
        return {
            "access_token":  r.get("AccessToken"),
            "id_token":      r.get("IdToken"),
            "refresh_token": r.get("RefreshToken"),
            "token_type":    r.get("TokenType", "Bearer"),
            "expires_in":    r.get("ExpiresIn", 3600),
        }



    def setup_totp(self, email: str, password: str, totp_secret: str) -> None:
        import pyotp
        resp = self.c.initiate_auth(
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters={'USERNAME': email, 'PASSWORD': password, 'SECRET_HASH': _secret_hash(email)},
            ClientId=self.cid,
        )
        session = resp['Session']
        assoc = self.c.associate_software_token(Session=session)
        # Use the secret returned by Cognito, not our stored one
        cognito_secret = assoc.get('SecretCode', totp_secret)
        import time
        totp = pyotp.TOTP(cognito_secret)
        for offset in [0, 30, -30]:
            try:
                code = totp.at(time.time() + offset)
                self.c.verify_software_token(Session=assoc['Session'], UserCode=code, FriendlyDeviceName='CHCProAI')
                break
            except Exception:
                if offset == -30:
                    raise
        self.c.admin_set_user_mfa_preference(
            UserPoolId=self.pool, Username=email,
            SoftwareTokenMfaSettings={'Enabled': True, 'PreferredMfa': True},
        )


    def get_totp_secret(self, email: str, password: str) -> tuple:
        """
        Initiate auth, then call associate_software_token to get Cognito's
        real TOTP secret. Returns (secret, cognito_session).
        """
        resp = self.c.initiate_auth(
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={
                "USERNAME":    email,
                "PASSWORD":    password,
                "SECRET_HASH": _secret_hash(email),
            },
            ClientId=self.cid,
        )
        challenge = resp.get("ChallengeName")
        if challenge == "MFA_SETUP":
            session = resp["Session"]
        elif "AuthenticationResult" in resp:
            # No MFA yet - use access token
            access_token = resp["AuthenticationResult"]["AccessToken"]
            assoc = self.c.associate_software_token(AccessToken=access_token)
            return assoc["SecretCode"], None
        else:
            session = resp.get("Session", "")

        assoc = self.c.associate_software_token(Session=session)
        return assoc["SecretCode"], assoc["Session"]

    def verify_totp_with_cognito(self, cognito_session: str, code: str, email: str) -> None:
        """
        Verify the TOTP code with Cognito using the session from associate_software_token.
        This activates TOTP MFA for the user in Cognito.
        """
        try:
            self.c.verify_software_token(
                Session=cognito_session,
                UserCode=code,
                FriendlyDeviceName="CHCProAI"
            )
        except Exception as e:
            err = str(e)
            if "CodeMismatchException" in err or "EnableSoftwareTokenMFAException" in err:
                raise CognitoError(
                    "That code is incorrect. Check your authenticator app and try again. "
                    "Codes refresh every 30 seconds.",
                    "CodeMismatchException"
                )
            raise CognitoError(str(e), "TOTP_VERIFY_ERROR")

        # Enable MFA for this user
        self.c.admin_set_user_mfa_preference(
            UserPoolId=self.pool,
            Username=email,
            SoftwareTokenMfaSettings={"Enabled": True, "PreferredMfa": True},
        )

cognito = CognitoService()
