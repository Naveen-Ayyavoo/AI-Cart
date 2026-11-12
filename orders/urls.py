"""URL patterns for AI Cart (formerly TrustCart) Orders and Purchase Approvals."""

from django.urls import path

from orders import views

urlpatterns = [
    path("orders/proposals/create/<uuid:report_id>/", views.proposal_create_from_evaluation, name="proposal_create_from_evaluation"),
    # Backward-compatible UUID aliases MUST precede <slug:public_ref>
    path("orders/proposals/<uuid:proposal_id>/", views.proposal_detail, name="proposal_detail_uuid"),
    path("orders/approvals/<uuid:approval_id>/", views.approval_detail, name="approval_detail_uuid"),
    # Canonical readable public_ref routes
    path("orders/proposals/<slug:public_ref>/", views.proposal_detail, name="proposal_detail"),
    path("orders/approvals/<slug:public_ref>/", views.approval_detail, name="approval_detail"),
]
