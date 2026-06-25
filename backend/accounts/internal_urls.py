from django.urls import path

from accounts.internal_views import InternalAIAuthCheckView

urlpatterns = [
    path(
        "auth-check/",
        InternalAIAuthCheckView.as_view(),
        name="internal-ai-auth-check",
    ),
]
