from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("internal/ai/", include("accounts.internal_urls")),
    path("", include("core.urls")),
]
