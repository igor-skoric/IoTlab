from django.contrib import admin
from django.urls import include, path

from iot_lab.health import health

admin.site.site_header = "IoT Lab"
admin.site.site_title = "IoT Lab"
admin.site.index_title = "Device laboratory"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health, name="health"),
    path("api/v1/", include("telemetry.api_urls")),
    path("", include("devices.urls")),
]
