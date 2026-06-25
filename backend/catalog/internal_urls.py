from django.urls import path

from catalog.internal_views import InternalAISalesSummaryView

urlpatterns = [
    path(
        "stores/<uuid:store_id>/sales/summary/",
        InternalAISalesSummaryView.as_view(),
        name="internal-ai-sales-summary",
    ),
]
