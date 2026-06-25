from rest_framework.authentication import (
    BaseAuthentication,
    SessionAuthentication as DRFSessionAuthentication,
    get_authorization_header,
)
from rest_framework.exceptions import AuthenticationFailed

from accounts.service_identity import AIServiceIdentity
from accounts.service_jwt import (
    ExpiredServiceJWTError,
    InvalidServiceJWTAudienceError,
    InvalidServiceJWTError,
    ServiceJWTError,
    UnknownServiceError,
    decode_service_jwt,
)

INVALID_SERVICE_TOKEN_MESSAGE = "Invalid internal service token."
EXPIRED_SERVICE_TOKEN_MESSAGE = "Internal service token has expired."
INVALID_SERVICE_TOKEN_AUDIENCE_MESSAGE = "Invalid internal service token audience."


class SessionAuthentication(DRFSessionAuthentication):
    """Session auth that returns 401 (not 403) for unauthenticated API clients."""

    def authenticate_header(self, request):
        return "Session"


class InternalAIAuthentication(BaseAuthentication):
    """Bearer service JWT authentication for /internal/ai/* routes only."""

    keyword = "Bearer"

    def authenticate(self, request):
        auth = get_authorization_header(request).split()

        if not auth:
            raise AuthenticationFailed("Authorization header is required.")

        if auth[0].lower() != self.keyword.lower().encode():
            raise AuthenticationFailed(
                "Invalid authorization header. Expected Bearer token."
            )

        if len(auth) == 1:
            raise AuthenticationFailed(INVALID_SERVICE_TOKEN_MESSAGE)
        if len(auth) > 2:
            raise AuthenticationFailed(
                "Invalid authorization header. Token string should not contain spaces."
            )

        token = auth[1].decode()
        if not token:
            raise AuthenticationFailed(INVALID_SERVICE_TOKEN_MESSAGE)

        try:
            claims = decode_service_jwt(token)
        except ExpiredServiceJWTError as exc:
            raise AuthenticationFailed(EXPIRED_SERVICE_TOKEN_MESSAGE) from exc
        except InvalidServiceJWTAudienceError as exc:
            raise AuthenticationFailed(INVALID_SERVICE_TOKEN_AUDIENCE_MESSAGE) from exc
        except (UnknownServiceError, InvalidServiceJWTError) as exc:
            raise AuthenticationFailed(INVALID_SERVICE_TOKEN_MESSAGE) from exc
        except ServiceJWTError as exc:
            raise AuthenticationFailed(INVALID_SERVICE_TOKEN_MESSAGE) from exc

        identity = AIServiceIdentity(
            service_name=claims["sub"],
            tenant_id=str(claims["tenant_id"]),
            store_id=str(claims["store_id"]),
        )

        request.ai_service = identity
        request.service_name = identity.service_name
        request.tenant_id = identity.tenant_id
        request.store_id = identity.store_id

        return (identity, claims)

    def authenticate_header(self, request):
        return "Bearer"
