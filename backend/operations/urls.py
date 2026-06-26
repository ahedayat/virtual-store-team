from django.urls import path

from operations.views import (
    ActionApproveView,
    ActionDetailView,
    ActionListView,
    ActionRejectView,
    HistoryFeedView,
    ReportDetailView,
    ReportGenerateView,
    ReportListView,
)

urlpatterns = [
    path("history/", HistoryFeedView.as_view(), name="api-history"),
    path("reports/generate/", ReportGenerateView.as_view(), name="api-reports-generate"),
    path("reports/", ReportListView.as_view(), name="api-reports-list"),
    path("reports/<uuid:report_run_id>/", ReportDetailView.as_view(), name="api-reports-detail"),
    path("actions/", ActionListView.as_view(), name="api-actions-list"),
    path("actions/<uuid:action_id>/", ActionDetailView.as_view(), name="api-actions-detail"),
    path(
        "actions/<uuid:action_id>/approve/",
        ActionApproveView.as_view(),
        name="api-actions-approve",
    ),
    path(
        "actions/<uuid:action_id>/reject/",
        ActionRejectView.as_view(),
        name="api-actions-reject",
    ),
]
