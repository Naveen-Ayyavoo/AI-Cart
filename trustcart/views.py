"""
Core system views for AI Cart (formerly TrustCart).
Architecture & Application Foundation (Phase P1).
"""

import logging

from django.conf import settings
from django.db import DatabaseError, OperationalError, connection
from django.http import JsonResponse
from django.shortcuts import render

logger = logging.getLogger(__name__)


def health_check(request):
    """
    Operational health check endpoint for monitoring system status and database connectivity.
    Returns HTTP 200 when healthy, or HTTP 503 if database check fails.
    """
    db_status = "connected"
    http_status = 200

    try:
        connection.ensure_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            row = cursor.fetchone()
            if not row or row[0] != 1:
                db_status = "unresponsive"
                http_status = 503
    except (DatabaseError, OperationalError, Exception) as exc:  # noqa: BLE001
        logger.error(f"Health check database failure: {exc}")
        db_status = f"error: {exc!s}"
        http_status = 503

    payload = {
        "status": "ok" if http_status == 200 else "degraded",
        "app": "trustcart",
        "database": db_status,
        "environment": "sandbox",
        "currency": getattr(settings, "CURRENCY_CODE", "USD"),
    }
    return JsonResponse(payload, status=http_status)


def custom_404_view(request, exception=None):
    """
    Custom 404 handler rendering branded 404.html with status 404.
    Preserves security by never exposing stack traces, exceptions, IDs, or paths.
    """
    return render(request, "404.html", status=404)

