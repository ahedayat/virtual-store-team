from django.urls import path

from accounts.internal_views import InternalAIAuthCheckView
from catalog.internal_views import (
    InternalAIContextView,
    InternalLowStockInventoryView,
    InternalRecentMessagesView,
    InternalSalesSummaryView,
)
from operations.internal_views import (
    InternalActionCreateView,
    InternalAgentOutputCreateView,
    InternalReportRunCompleteView,
)

urlpatterns = [
    path(
        "auth-check/",
        InternalAIAuthCheckView.as_view(),
        name="internal-ai-auth-check",
    ),
    path(
        "actions/",
        InternalActionCreateView.as_view(),
        name="internal-ai-actions-create",
    ),
    path(
        "agent-outputs/",
        InternalAgentOutputCreateView.as_view(),
        name="internal-ai-agent-outputs-create",
    ),
    path(
        "report-runs/<uuid:report_run_id>/complete/",
        InternalReportRunCompleteView.as_view(),
        name="internal-ai-report-runs-complete",
    ),
    path(
        "context/<uuid:report_run_id>/",
        InternalAIContextView.as_view(),
        name="internal-ai-context",
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
