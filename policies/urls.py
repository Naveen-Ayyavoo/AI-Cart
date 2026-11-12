"""URL patterns for AI Cart (formerly TrustCart) Deterministic Policy Evaluation."""

from django.urls import path

from policies import views

urlpatterns = [
    path("contracts/<uuid:contract_id>/evaluation/", views.contract_evaluation, name="contract_evaluation_uuid"),
    path("contracts/<slug:public_ref>/evaluation/", views.contract_evaluation, name="contract_evaluation"),
]
