"""URL routing for AI Cart Phase P6 Payments app."""

from django.urls import path

from payments import views

app_name = "payments"

urlpatterns = [
    path("history/", views.payment_history, name="history"),
    path(
        "checkout/initiate/<str:token>/",
        views.checkout_initiate,
        name="checkout_initiate",
    ),
    path("checkout/return/", views.checkout_return, name="checkout_return"),
    path("checkout/cancel/", views.checkout_cancel, name="checkout_cancel"),
    path("orders/<str:paypal_order_id>/", views.order_detail, name="order_detail"),
    path(
        "orders/<str:paypal_order_id>/reconcile/",
        views.order_reconcile,
        name="order_reconcile",
    ),
    path("webhooks/paypal/", views.paypal_webhook_listener, name="paypal_webhook"),
]
