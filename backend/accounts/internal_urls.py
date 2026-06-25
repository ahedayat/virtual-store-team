from django.urls import path

from accounts.internal_views import InternalAIAuthCheckView
from catalog.internal_views import (
    InternalLowStockInventoryView,
    InternalRecentMessagesView,
    InternalSalesSummaryView,
)

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
    path(
        "stores/<uuid:store_id>/inventory/low-stock/",
        InternalLowStockInventoryView.as_view(),
        name="internal-ai-low-stock-inventory",
    ),
    path(
        "stores/<uuid:store_id>/messages/recent/",
        InternalRecentMessagesView.as_view(),
        name="internal-ai-recent-messages",
    ),
]
