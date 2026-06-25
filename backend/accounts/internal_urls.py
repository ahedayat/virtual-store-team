from django.urls import path

from accounts.internal_views import InternalAIAuthCheckView
from catalog.internal_views import InternalSalesSummaryView

urlpatterns = [
    path(
        "auth-check/",
        InternalAIAuthCheckView.as_view(),
        name="internal-ai-auth-check",
    ),
    path(
        "stores/<uuid:store_id>/sales/summary/",
        InternalSalesSummaryView.as_view(),
        name="internal-ai-sales-summary",
    ),
]
