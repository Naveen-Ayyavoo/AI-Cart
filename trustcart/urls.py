"""URL configuration for AI Cart (formerly TrustCart) project.

Phase P1, P2, P3, P4 & P5: Foundation, Contracts, Catalog, Policies & Orders.
"""

from django.contrib import admin
from django.urls import include, path

from trustcart.views import health_check

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health_check, name="health_check"),
    path("", include("contracts.urls")),
    path("", include("catalog.urls")),
    path("", include("policies.urls")),
    path("", include("orders.urls")),
    path("payments/", include("payments.urls")),
]

handler404 = "trustcart.views.custom_404_view"

