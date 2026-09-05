import os

from .base import *  # noqa: F403

DEBUG = os.getenv("DEBUG", "false").lower() in {"1", "true", "yes", "on"}

if not SECRET_KEY or SECRET_KEY == "unsafe-dev-secret-change-me":  # noqa: F405
    raise ValueError("SECRET_KEY must be set to a strong value in production.")

if not ALLOWED_HOSTS:  # noqa: F405
    raise ValueError("ALLOWED_HOSTS must be set in production.")

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "true").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
CSRF_COOKIE_SECURE = os.getenv("CSRF_COOKIE_SECURE", "true").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
