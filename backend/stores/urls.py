from django.urls import path

from stores.views import StoreDetailView

urlpatterns = [
    path("stores/<uuid:store_id>/", StoreDetailView.as_view(), name="api-store-detail"),
]
