from django.urls import path

from devices.views import DashboardLiveView, DashboardView, DeviceDetailView

urlpatterns = [
    path("", DashboardView.as_view(), name="dashboard"),
    path("dashboard/live/", DashboardLiveView.as_view(), name="dashboard-live"),
    path("devices/<str:device_uid>/", DeviceDetailView.as_view(), name="device-detail"),
]
