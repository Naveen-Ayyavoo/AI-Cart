"""
URL patterns for Purchase Contract intent intake, review, and confirmation.
Phase P2: Purchase Contract Creation & Confirmation.
"""

from django.urls import path

from contracts import views

urlpatterns = [
    path("", views.home_view, name="home"),
    path("contracts/create/", views.contract_create, name="contract_create"),
    # Backward-compatible UUID aliases MUST precede <slug:public_ref> because UUIDs also match slug
    path("contracts/<uuid:contract_id>/review/", views.contract_review, name="contract_review_uuid"),
    path("contracts/<uuid:contract_id>/update/", views.contract_update, name="contract_update_uuid"),
    path("contracts/<uuid:contract_id>/clarify/", views.contract_clarify, name="contract_clarify_uuid"),
    path("contracts/<uuid:contract_id>/revise-budget/", views.contract_revise_budget, name="contract_revise_budget_uuid"),
    path("contracts/<uuid:contract_id>/confirm/", views.contract_confirm, name="contract_confirm_uuid"),
    # Canonical readable public_ref routes
    path("contracts/<slug:public_ref>/review/", views.contract_review, name="contract_review"),
    path("contracts/<slug:public_ref>/retry-parse/", views.contract_retry_parse, name="contract_retry_parse"),
    path("contracts/<slug:public_ref>/update/", views.contract_update, name="contract_update"),
    path("contracts/<slug:public_ref>/clarify/", views.contract_clarify, name="contract_clarify"),
    path("contracts/<slug:public_ref>/revise-budget/", views.contract_revise_budget, name="contract_revise_budget"),
    path("contracts/<slug:public_ref>/confirm/", views.contract_confirm, name="contract_confirm"),
    path("contracts/<slug:public_ref>/buy-anyway/<str:product_id>/", views.contract_buy_anyway, name="contract_buy_anyway"),
]
