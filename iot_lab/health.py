from django.db import connection
from django.http import JsonResponse


def health(request):
    """Lightweight liveness/readiness probe for Docker and Nginx."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        db_ok = True
    except Exception:
        db_ok = False

    payload = {
        "status": "ok" if db_ok else "error",
        "database": "ok" if db_ok else "error",
    }
    return JsonResponse(payload, status=200 if db_ok else 503)
