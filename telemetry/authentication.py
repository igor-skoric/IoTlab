from rest_framework import authentication, exceptions
from rest_framework.permissions import BasePermission

from devices.models import Device


class DeviceAPIKeyAuthentication(authentication.BaseAuthentication):
    header_name = "X-API-Key"

    def authenticate(self, request):
        api_key = request.headers.get(self.header_name)
        if not api_key:
            raise exceptions.AuthenticationFailed("Missing X-API-Key header.")
        try:
            device = Device.objects.get(api_key=api_key)
        except Device.DoesNotExist as exc:
            raise exceptions.AuthenticationFailed("Invalid API key.") from exc
        return (device, api_key)

    def authenticate_header(self, request):
        # Required so DRF returns 401 instead of 403 for failed API-key auth.
        return self.header_name


class IsActiveDevice(BasePermission):
    message = "Device is inactive."

    def has_permission(self, request, view):
        device = request.user
        return isinstance(device, Device) and device.is_active
