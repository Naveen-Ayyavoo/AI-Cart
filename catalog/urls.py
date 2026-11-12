"""URL patterns for AI Cart (formerly TrustCart) Catalog and Product Discovery."""

from django.urls import path

from catalog import views

urlpatterns = [
    path("contracts/<uuid:contract_id>/discovery/", views.contract_discovery, name="contract_discovery_uuid"),
    path("contracts/<slug:public_ref>/discovery/", views.contract_discovery, name="contract_discovery"),
    path("contracts/<slug:public_ref>/select/<str:product_id>/", views.contract_select_product, name="contract_select_product"),
]
