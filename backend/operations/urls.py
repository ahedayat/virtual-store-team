from django.urls import path

from operations.views import HistoryFeedView, ReportGenerateView

urlpatterns = [
    path("history/", HistoryFeedView.as_view(), name="api-history"),
    path("reports/generate/", ReportGenerateView.as_view(), name="api-reports-generate"),
]
