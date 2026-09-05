import os

from .base import *  # noqa: F403

DEBUG = os.getenv("DEBUG", "true").lower() in {"1", "true", "yes", "on"}

REST_FRAMEWORK = {
    **REST_FRAMEWORK,  # noqa: F405
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
}
