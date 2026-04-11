from django.conf import settings
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenBlacklistView, TokenObtainPairView

from apps.api.v1.serializers import (
    APIKeyCreateSerializer,
    APIKeyListSerializer,
    ApplicationDetailSerializer,
    ApplicationListSerializer,
    ApplicationSubmitSerializer,
    AuditLogSerializer,
    DecisionSerializer,
    OverrideSerializer,
    PolicyRuleSerializer,
)
from apps.applications.models import Application, ApplicationStatus
from apps.applications.services import ApplicationService
from apps.applications.tasks import enqueue_pipeline
from apps.audits.constants import ActorType, EventType
from apps.audits.models import AuditLog
from apps.audits.services import AuditService
from apps.authentication.api_keys import extract_prefix, hash_api_key
from apps.authentication.authentication import BearerOrApiKeyAuthentication
from apps.authentication.models import APIKey, User, UserRole
from apps.authentication.permissions import (
    CanManageApiKeys,
    CanManagePolicyRules,
    CanOverrideDecision,
    CanReadAuditLogs,
    CanSubmitApplication,
    CanViewDecision,
    IsAdminOrAnalyst,
)
from apps.authentication.google_auth import user_for_google_oauth_email, verify_google_id_token
from apps.authentication.serializers import AuditedTokenObtainPairSerializer
from apps.decisions.models import Decision
from apps.decisions.services import DecisionService
from apps.policies.models import PolicyRule


class LoginView(TokenObtainPairView):
    serializer_class = AuditedTokenObtainPairSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_login"


class GoogleLoginView(APIView):
    """
    Exchange a Google Sign-In ID token (credential) for API JWTs.

    Request JSON: {"id_token": "<token from Google Identity Services>"}.
    Configure GOOGLE_OAUTH_CLIENT_ID with your OAuth 2.0 Web client ID(s).
    """

    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_login"

    def post(self, request, *args, **kwargs):
        cid = getattr(request, "correlation_id", None)
        audiences = list(settings.GOOGLE_OAUTH_CLIENT_ID)
        if not audiences:
            AuditService.record(
                actor_type=ActorType.USER,
                actor_id=None,
                target_type="auth",
                target_id="google",
                event_type=EventType.AUTH_LOGIN_FAILURE,
                correlation_id=cid,
                metadata={"reason": "not_configured"},
                request_path=request.path,
            )
            return Response(
                {"detail": "Google sign-in is not configured."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        raw = (request.data or {}).get("id_token") or (request.data or {}).get("credential")
        if not raw or not isinstance(raw, str):
            AuditService.record(
                actor_type=ActorType.USER,
                actor_id=None,
                target_type="auth",
                target_id="google",
                event_type=EventType.AUTH_LOGIN_FAILURE,
                correlation_id=cid,
                metadata={"reason": "missing_token"},
                request_path=request.path,
            )
            raise ValidationError({"id_token": "This field is required."})

        try:
            claims = verify_google_id_token(raw, audiences)
        except ValueError:
            AuditService.record(
                actor_type=ActorType.USER,
                actor_id=None,
                target_type="auth",
                target_id="google",
                event_type=EventType.AUTH_LOGIN_FAILURE,
                correlation_id=cid,
                metadata={"reason": "invalid_token"},
                request_path=request.path,
            )
            raise AuthenticationFailed("Invalid Google token.") from None

        if not claims.get("email_verified"):
            AuditService.record(
                actor_type=ActorType.USER,
                actor_id=None,
                target_type="auth",
                target_id=str(claims.get("email") or "unknown"),
                event_type=EventType.AUTH_LOGIN_FAILURE,
                correlation_id=cid,
                metadata={"reason": "email_not_verified"},
                request_path=request.path,
            )
            raise AuthenticationFailed("Google account email is not verified.")

        email = claims.get("email")
        if not email:
            AuditService.record(
                actor_type=ActorType.USER,
                actor_id=None,
                target_type="auth",
                target_id="google",
                event_type=EventType.AUTH_LOGIN_FAILURE,
                correlation_id=cid,
                metadata={"reason": "missing_email"},
                request_path=request.path,
            )
            raise AuthenticationFailed("Google token did not include an email.")

        user = user_for_google_oauth_email(email)
        if not user.is_active:
            AuditService.record(
                actor_type=ActorType.USER,
                actor_id=str(user.id),
                target_type="auth",
                target_id=str(user.id),
                event_type=EventType.AUTH_LOGIN_FAILURE,
                correlation_id=cid,
                metadata={"reason": "inactive_user"},
                request_path=request.path,
            )
            raise AuthenticationFailed("User account is disabled.")

        refresh = RefreshToken.for_user(user)
        AuditService.record(
            actor_type=ActorType.USER,
            actor_id=str(user.id),
            target_type="auth",
            target_id=str(user.id),
            event_type=EventType.AUTH_LOGIN_SUCCESS,
            correlation_id=cid,
            metadata={"email": user.email, "method": "google"},
            request_path=request.path,
        )
        return Response(
            {"refresh": str(refresh), "access": str(refresh.access_token)},
            status=status.HTTP_200_OK,
        )


class LogoutView(TokenBlacklistView):
    authentication_classes = [BearerOrApiKeyAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code in (200, 205):
            AuditService.record(
                actor_type=ActorType.USER,
                actor_id=str(request.user.id),
                target_type="auth",
                target_id=str(request.user.id),
                event_type=EventType.AUTH_LOGOUT,
                correlation_id=getattr(request, "correlation_id", None),
                request_path=request.path,
                metadata={},
            )
        return response


class ApplicationViewSet(viewsets.ModelViewSet):
    http_method_names = ["get", "post", "head", "options"]
    queryset = Application.objects.all().order_by("-created_at")

    def get_permissions(self):
        if self.action == "create":
            return [IsAuthenticated(), CanSubmitApplication()]
        if self.action in ("list", "retrieve", "decision"):
            return [IsAuthenticated(), CanViewDecision()]
        if self.action == "override":
            return [IsAuthenticated(), CanOverrideDecision()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        if self.action == "create":
            return ApplicationSubmitSerializer
        if self.action == "retrieve":
            return ApplicationDetailSerializer
        return ApplicationListSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        return ApplicationService.visible_queryset_for_request(self.request, qs)

    def create(self, request, *args, **kwargs):
        ser = ApplicationSubmitSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        idem = request.headers.get("Idempotency-Key") or request.headers.get("X-Idempotency-Key")
        cid = getattr(request, "correlation_id", "") or ""
        app, created = ApplicationService.submit(
            request=request,
            payload=ser.validated_data["payload"],
            external_reference=ser.validated_data.get("external_reference") or "",
            idempotency_key=idem,
            correlation_id=cid,
        )
        if created:
            enqueue_pipeline(app.id)
        code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(ApplicationDetailSerializer(app, context={"request": request}).data, status=code)

    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @action(detail=True, methods=["get"], url_path="decision")
    def decision(self, request, pk=None):
        app = self.get_object()
        dec = Decision.objects.filter(application=app, is_current=True).first()
        if not dec:
            return Response({"detail": "No decision yet."}, status=status.HTTP_404_NOT_FOUND)
        return Response(DecisionSerializer(dec).data)

    @action(detail=True, methods=["post"], url_path="override")
    def override(self, request, pk=None):
        app = self.get_object()
        if getattr(request.user, "role", None) == UserRole.API_CLIENT:
            raise PermissionDenied("API clients cannot override decisions.")
        ser = OverrideSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        if app.status not in (
            ApplicationStatus.MANUAL_REVIEW,
            ApplicationStatus.APPROVED,
            ApplicationStatus.DECLINED,
        ):
            raise ValidationError({"detail": "Application is not in a state that allows override."})
        if not Decision.objects.filter(application=app, is_current=True).exists():
            raise ValidationError({"detail": "No decision to override."})
        DecisionService.override_decision(
            application=app,
            user=request.user,
            new_decision_type=ser.validated_data["decision_type"],
            reason=ser.validated_data["reason"],
            correlation_id=getattr(request, "correlation_id", None),
        )
        dec = Decision.objects.filter(application=app, is_current=True).first()
        return Response(DecisionSerializer(dec).data, status=status.HTTP_200_OK)


class PolicyRuleViewSet(viewsets.ModelViewSet):
    queryset = PolicyRule.objects.all().order_by("priority", "id")
    serializer_class = PolicyRuleSerializer

    def get_permissions(self):
        if self.request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return [IsAuthenticated(), CanManagePolicyRules()]
        return [IsAuthenticated(), IsAdminOrAnalyst()]

    def perform_create(self, serializer):
        obj = serializer.save()
        AuditService.record(
            actor_type=ActorType.USER,
            actor_id=str(self.request.user.id),
            target_type="policy_rule",
            target_id=str(obj.id),
            event_type=EventType.POLICY_RULE_CREATED,
            correlation_id=getattr(self.request, "correlation_id", None),
            request_path=self.request.path,
            metadata={"name": obj.name, "priority": obj.priority},
        )

    def perform_update(self, serializer):
        obj = serializer.save()
        AuditService.record(
            actor_type=ActorType.USER,
            actor_id=str(self.request.user.id),
            target_type="policy_rule",
            target_id=str(obj.id),
            event_type=EventType.POLICY_RULE_UPDATED,
            correlation_id=getattr(self.request, "correlation_id", None),
            request_path=self.request.path,
            metadata={"name": obj.name},
        )

    def perform_destroy(self, instance):
        rid = str(instance.id)
        AuditService.record(
            actor_type=ActorType.USER,
            actor_id=str(self.request.user.id),
            target_type="policy_rule",
            target_id=rid,
            event_type=EventType.POLICY_RULE_DELETED,
            correlation_id=getattr(self.request, "correlation_id", None),
            request_path=self.request.path,
            metadata={"name": instance.name},
        )
        instance.delete()


class AuditLogViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated, CanReadAuditLogs]
    queryset = AuditLog.objects.all().order_by("-timestamp")

    def get_queryset(self):
        qs = super().get_queryset()
        et = self.request.query_params.get("event_type")
        tt = self.request.query_params.get("target_type")
        tid = self.request.query_params.get("target_id")
        cid = self.request.query_params.get("correlation_id")
        if et:
            qs = qs.filter(event_type=et)
        if tt:
            qs = qs.filter(target_type=tt)
        if tid:
            qs = qs.filter(target_id=tid)
        if cid:
            qs = qs.filter(correlation_id=cid)
        return qs


class APIKeyViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated, CanManageApiKeys]
    queryset = APIKey.objects.select_related("user").all().order_by("-created_at")

    def get_serializer_class(self):
        if self.action == "create":
            return APIKeyCreateSerializer
        return APIKeyListSerializer

    def create(self, request, *args, **kwargs):
        ser = APIKeyCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = ser.validated_data["user"]
        raw = APIKey.generate_secret()
        key = APIKey.objects.create(
            user=user,
            name=ser.validated_data["name"],
            prefix=extract_prefix(raw, 16),
            hashed_key=hash_api_key(raw),
            created_by=request.user,
        )
        AuditService.record(
            actor_type=ActorType.USER,
            actor_id=str(request.user.id),
            target_type="api_key",
            target_id=str(key.id),
            event_type=EventType.API_KEY_CREATED,
            correlation_id=getattr(request, "correlation_id", None),
            request_path=request.path,
            metadata={"name": key.name, "user_id": str(user.id)},
        )
        return Response(
            {
                "id": str(key.id),
                "name": key.name,
                "prefix": key.prefix,
                "plaintext_key": raw,
                "created_at": key.created_at,
                "revoked_at": key.revoked_at,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="revoke")
    def revoke(self, request, pk=None):
        key = self.get_object()
        if key.revoked_at:
            return Response({"detail": "Already revoked."}, status=status.HTTP_400_BAD_REQUEST)
        key.revoked_at = timezone.now()
        key.save(update_fields=["revoked_at"])
        AuditService.record(
            actor_type=ActorType.USER,
            actor_id=str(request.user.id),
            target_type="api_key",
            target_id=str(key.id),
            event_type=EventType.API_KEY_REVOKED,
            correlation_id=getattr(request, "correlation_id", None),
            request_path=request.path,
            metadata={"name": key.name},
        )
        return Response({"detail": "revoked", "id": str(key.id)}, status=status.HTTP_200_OK)
