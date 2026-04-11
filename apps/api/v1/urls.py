from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.api.v1.views import (
    APIKeyViewSet,
    ApplicationViewSet,
    AuditLogViewSet,
    GoogleLoginView,
    LoginView,
    LogoutView,
    PolicyRuleViewSet,
)

router = DefaultRouter()
router.register(r"applications", ApplicationViewSet, basename="application")
router.register(r"rules", PolicyRuleViewSet, basename="policyrule")
router.register(r"audit-logs", AuditLogViewSet, basename="auditlog")
router.register(r"api-keys", APIKeyViewSet, basename="apikey")

urlpatterns = [
    path("auth/login", LoginView.as_view(), name="v1-auth-login"),
    path("auth/google", GoogleLoginView.as_view(), name="v1-auth-google"),
    path("auth/logout", LogoutView.as_view(), name="v1-auth-logout"),
    path("", include(router.urls)),
]
