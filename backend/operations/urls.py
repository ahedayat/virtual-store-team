from django.urls import path

from operations.views import HistoryFeedView

urlpatterns = [
    path("history/", HistoryFeedView.as_view(), name="api-history"),
]
