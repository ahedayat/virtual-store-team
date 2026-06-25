from rest_framework.authentication import (
    BaseAuthentication,
    SessionAuthentication as DRFSessionAuthentication,
    get_authorization_header,
)
from rest_framework.exceptions import AuthenticationFailed

from accounts.service_identity import AIServiceIdentity
from accounts.service_jwt import (
    InvalidServiceJWTError,
    ServiceJWTError,
    UnknownServiceError,
    decode_service_jwt,
)


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
            raise AuthenticationFailed(
                "Invalid authorization header. No credentials provided."
            )
        if len(auth) > 2:
            raise AuthenticationFailed(
                "Invalid authorization header. Token string should not contain spaces."
            )

        token = auth[1].decode()

        try:
            claims = decode_service_jwt(token)
        except UnknownServiceError as exc:
            raise AuthenticationFailed(str(exc)) from exc
        except InvalidServiceJWTError as exc:
            raise AuthenticationFailed(str(exc)) from exc
        except ServiceJWTError as exc:
            raise AuthenticationFailed("Authentication failed.") from exc

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
        return 'Bearer realm="ai-services"'
