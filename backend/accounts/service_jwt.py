from datetime import datetime, timedelta, timezone

import jwt
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from accounts.constants import ALLOWED_AI_SERVICES

REQUIRED_CLAIMS = ("sub", "tenant_id", "store_id", "iat", "exp", "aud")


class ServiceJWTError(Exception):
    """Base error for service JWT validation failures."""


class ExpiredServiceJWTError(ServiceJWTError):
    """Raised when the token exp claim is in the past."""


class InvalidServiceJWTAudienceError(ServiceJWTError):
    """Raised when the token aud claim does not match the expected audience."""


class InvalidServiceJWTError(ServiceJWTError):
    """Raised when a token is malformed, wrongly signed, or missing required claims."""


class UnknownServiceError(ServiceJWTError):
    """Raised when the token subject is not a registered AI service."""


def _require_service_secret() -> str:
    secret = settings.JWT_SERVICE_SECRET
    if not secret:
        raise ImproperlyConfigured(
            "JWT_SERVICE_SECRET is not configured. "
            "Set the environment variable or use override_settings in tests."
        )
    return secret


def decode_service_jwt(token: str) -> dict:
    """Decode and validate a service JWT. Raises ServiceJWTError subclasses on failure."""
    secret = _require_service_secret()
    audience = settings.JWT_SERVICE_AUDIENCE
    algorithm = settings.JWT_SERVICE_ALGORITHM

    try:
        claims = jwt.decode(
            token,
            secret,
            algorithms=[algorithm],
            audience=audience,
            options={"require": list(REQUIRED_CLAIMS)},
        )
    except jwt.ExpiredSignatureError as exc:
        raise ExpiredServiceJWTError from exc
    except jwt.InvalidAudienceError as exc:
        raise InvalidServiceJWTAudienceError from exc
    except jwt.InvalidTokenError as exc:
        raise InvalidServiceJWTError from exc

    service_name = claims.get("sub")
    if service_name not in ALLOWED_AI_SERVICES:
        raise UnknownServiceError

    return claims


def mint_service_jwt(
    *,
    service_name: str,
    tenant_id: str,
    store_id: str,
    report_run_id: str | None = None,
    lifetime_minutes: int | None = None,
) -> str:
    """Mint a short-lived service JWT. Intended for tests and future Celery issuance."""
    if service_name not in ALLOWED_AI_SERVICES:
        raise UnknownServiceError

    secret = _require_service_secret()
    algorithm = settings.JWT_SERVICE_ALGORITHM
    audience = settings.JWT_SERVICE_AUDIENCE
    lifetime = lifetime_minutes or settings.JWT_SERVICE_TOKEN_LIFETIME_MINUTES

    now = datetime.now(timezone.utc)
    payload = {
        "sub": service_name,
        "tenant_id": str(tenant_id),
        "store_id": str(store_id),
        "iat": now,
        "exp": now + timedelta(minutes=lifetime),
        "aud": audience,
    }
    if report_run_id is not None:
        payload["report_run_id"] = str(report_run_id)

    return jwt.encode(payload, secret, algorithm=algorithm)
