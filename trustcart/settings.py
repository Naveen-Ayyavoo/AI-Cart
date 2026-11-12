"""
Django settings for AI Cart (formerly TrustCart) project.
PayPal AI Hackathon — US Market (USD).
Architecture & Application Foundation (Phase P1).
Zero-Spend Engineering Policy (ADR-0004) strictly enforced.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env if present
load_dotenv(BASE_DIR / ".env", override=True)

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    "django-insecure-trustcart-dev-key-paypal-hackathon-2026-eval-zero-spend",
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv("DJANGO_DEBUG", "True").lower() in ("true", "1", "yes")

ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]").split(",")
if DEBUG:
    ALLOWED_HOSTS.extend([".trycloudflare.com", "testserver"])


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # AI Cart Core Domain Applications
    "contracts.apps.ContractsConfig",
    "catalog.apps.CatalogConfig",
    "policies.apps.PoliciesConfig",
    "orders.apps.OrdersConfig",
    "payments.apps.PaymentsConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "trustcart.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "trustcart.wsgi.application"


# Database
# Local SQLite only — Zero cloud database expenditure (ADR-0004)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
        "OPTIONS": {
            "timeout": 20,
        },
    }
}


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# AI Cart Architectural Constants
CURRENCY_CODE = "USD"
APPROVAL_TOKEN_TTL_SECONDS = 900  # 15 minutes

# Google Gemini Free Tier Model Configuration (ADR-0004)
GEMINI_MODEL_ROUTINE = os.getenv("GEMINI_MODEL_ROUTINE", "gemini-3.5-flash-lite")
GEMINI_MODEL_COMPLEX = os.getenv("GEMINI_MODEL_COMPLEX", "gemini-3.8-flash")

# PayPal Sandbox Configuration (ADR-0002, ADR-0004)
# Strict Sandbox only (api-m.sandbox.paypal.com). Production endpoints strictly forbidden.
PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID", "mock_sandbox_client_id").strip('"').strip("'")
PAYPAL_CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET", "mock_sandbox_client_secret").strip('"').strip("'")
PAYPAL_BASE_URL = os.getenv("PAYPAL_BASE_URL", "https://api-m.sandbox.paypal.com").strip('"').strip("'")
PAYPAL_ENVIRONMENT = os.getenv("PAYPAL_ENVIRONMENT", "sandbox").strip('"').strip("'")
PAYPAL_WEBHOOK_ID = os.getenv("PAYPAL_WEBHOOK_ID", "mock_sandbox_webhook_id").strip('"').strip("'")
PAYPAL_DEMO_MERCHANT_ID = os.getenv("PAYPAL_DEMO_MERCHANT_ID", "PU7K3F65AAQ8U").strip('"').strip("'")

# Email (Console backend for sandbox development)
MAILERS = {
    "default": {
        "BACKEND": "django.core.mail.backends.console.EmailBackend",
    },
}
