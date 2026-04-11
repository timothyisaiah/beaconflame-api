from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.audits.constants import ActorType, EventType
from apps.audits.services import AuditService
from apps.authentication.models import User


class AuditedTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Records successful and failed login attempts."""

    username_field = User.USERNAME_FIELD

    def validate(self, attrs):
        request = self.context.get("request")
        cid = getattr(request, "correlation_id", None) if request else None
        email = attrs.get("email") or attrs.get(self.username_field) or "unknown"
        try:
            data = super().validate(attrs)
        except AuthenticationFailed as exc:
            AuditService.record(
                actor_type=ActorType.USER,
                actor_id=None,
                target_type="auth",
                target_id=str(email),
                event_type=EventType.AUTH_LOGIN_FAILURE,
                correlation_id=cid,
                metadata={},
                request_path=getattr(request, "path", None) if request else None,
            )
            raise exc
        user = self.user
        AuditService.record(
            actor_type=ActorType.USER,
            actor_id=str(user.id),
            target_type="auth",
            target_id=str(user.id),
            event_type=EventType.AUTH_LOGIN_SUCCESS,
            correlation_id=cid,
            metadata={"email": user.email},
            request_path=getattr(request, "path", None) if request else None,
        )
        return data
