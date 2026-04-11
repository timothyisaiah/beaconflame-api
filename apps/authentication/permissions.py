from rest_framework.permissions import BasePermission

from apps.authentication.models import UserRole


def _role(user):
    return getattr(user, "role", None)


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and _role(u) == UserRole.ADMIN)


class IsAdminOrAnalyst(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        if not u or not u.is_authenticated:
            return False
        return _role(u) in (UserRole.ADMIN, UserRole.ANALYST)


class IsNotApiClient(BasePermission):
    """Dashboard-only: JWT users that are not external api_client role."""

    def has_permission(self, request, view):
        u = request.user
        if not u or not u.is_authenticated:
            return False
        return _role(u) != UserRole.API_CLIENT


class CanSubmitApplication(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        if not u or not u.is_authenticated:
            return False
        return _role(u) in (UserRole.ADMIN, UserRole.ANALYST, UserRole.API_CLIENT)


class CanViewDecision(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated)


class CanManagePolicyRules(BasePermission):
    def has_permission(self, request, view):
        return IsAdmin().has_permission(request, view)


class CanOverrideDecision(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        if not u or not u.is_authenticated:
            return False
        return _role(u) in (UserRole.ADMIN, UserRole.ANALYST)


class CanReadAuditLogs(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        if not u or not u.is_authenticated:
            return False
        return _role(u) in (UserRole.ADMIN, UserRole.ANALYST)


class CanManageApiKeys(BasePermission):
    def has_permission(self, request, view):
        return IsAdmin().has_permission(request, view)
