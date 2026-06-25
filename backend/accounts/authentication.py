from rest_framework.authentication import SessionAuthentication as DRFSessionAuthentication


class SessionAuthentication(DRFSessionAuthentication):
    """Session auth that returns 401 (not 403) for unauthenticated API clients."""

    def authenticate_header(self, request):
        return "Session"
