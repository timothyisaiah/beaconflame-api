import json
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import authenticate, login
from django.http import HttpResponseBadRequest, HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_http_methods, require_POST

from apps.audits.constants import ActorType, EventType
from apps.audits.services import AuditService
from apps.authentication.google_auth import user_for_google_oauth_email, verify_google_id_token


def _safe_next(raw: str | None) -> str:
    if not raw or not isinstance(raw, str):
        return "/"
    if not raw.startswith("/") or raw.startswith("//"):
        return "/"
    return raw


def _login_redirect_with_error(next_url: str, error: str) -> HttpResponseRedirect:
    q = urlencode({"error": error, "next": next_url})
    return HttpResponseRedirect(f"{reverse('browser-login')}?{q}")


@ensure_csrf_cookie
@require_http_methods(["GET", "POST"])
def browser_login(request):
    next_url = _safe_next(request.GET.get("next") or request.POST.get("next"))

    if request.method == "GET":
        if request.user.is_authenticated:
            return HttpResponseRedirect(next_url)
        ids = getattr(settings, "GOOGLE_OAUTH_CLIENT_ID", [])
        err = request.GET.get("error")
        return render(
            request,
            "authentication/login.html",
            {
                "next_url": next_url,
                "google_client_id": ids[0] if ids else "",
                "google_configured": bool(ids),
                "login_error": err,
            },
        )

    email = (request.POST.get("email") or "").strip()
    password = request.POST.get("password") or ""
    cid = getattr(request, "correlation_id", None)

    user = authenticate(request, email=email, password=password)
    if user is None:
        AuditService.record(
            actor_type=ActorType.USER,
            actor_id=None,
            target_type="auth",
            target_id=email or "unknown",
            event_type=EventType.AUTH_LOGIN_FAILURE,
            correlation_id=cid,
            metadata={"method": "browser_session"},
            request_path=request.path,
        )
        return _login_redirect_with_error(next_url, "invalid")

    if not user.is_active:
        AuditService.record(
            actor_type=ActorType.USER,
            actor_id=str(user.id),
            target_type="auth",
            target_id=str(user.id),
            event_type=EventType.AUTH_LOGIN_FAILURE,
            correlation_id=cid,
            metadata={"method": "browser_session", "reason": "inactive_user"},
            request_path=request.path,
        )
        return _login_redirect_with_error(next_url, "disabled")

    login(request, user)
    AuditService.record(
        actor_type=ActorType.USER,
        actor_id=str(user.id),
        target_type="auth",
        target_id=str(user.id),
        event_type=EventType.AUTH_LOGIN_SUCCESS,
        correlation_id=cid,
        metadata={"email": user.email, "method": "browser_session"},
        request_path=request.path,
    )
    return HttpResponseRedirect(next_url)


@csrf_protect
@require_POST
def browser_login_google(request):
    cid = getattr(request, "correlation_id", None)
    audiences = list(getattr(settings, "GOOGLE_OAUTH_CLIENT_ID", []))
    if not audiences:
        return JsonResponse({"ok": False, "error": "Google sign-in is not configured."}, status=503)

    ct = (request.content_type or "").lower()
    if "application/json" not in ct:
        return HttpResponseBadRequest("Expected application/json")

    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON")

    raw = body.get("credential") or body.get("id_token")
    next_url = _safe_next(body.get("next"))
    if not raw or not isinstance(raw, str):
        return JsonResponse({"ok": False, "error": "Missing credential."}, status=400)

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
            metadata={"method": "browser_session", "reason": "invalid_token"},
            request_path=request.path,
        )
        return JsonResponse({"ok": False, "error": "Invalid Google token."}, status=401)

    if not claims.get("email_verified"):
        return JsonResponse({"ok": False, "error": "Google account email is not verified."}, status=401)

    email = claims.get("email")
    if not email:
        return JsonResponse({"ok": False, "error": "Google token did not include an email."}, status=401)

    user = user_for_google_oauth_email(email)
    if not user.is_active:
        AuditService.record(
            actor_type=ActorType.USER,
            actor_id=str(user.id),
            target_type="auth",
            target_id=str(user.id),
            event_type=EventType.AUTH_LOGIN_FAILURE,
            correlation_id=cid,
            metadata={"method": "browser_session", "reason": "inactive_user"},
            request_path=request.path,
        )
        return JsonResponse({"ok": False, "error": "User account is disabled."}, status=401)

    login(request, user)
    AuditService.record(
        actor_type=ActorType.USER,
        actor_id=str(user.id),
        target_type="auth",
        target_id=str(user.id),
        event_type=EventType.AUTH_LOGIN_SUCCESS,
        correlation_id=cid,
        metadata={"email": user.email, "method": "browser_session_google"},
        request_path=request.path,
    )
    return JsonResponse({"ok": True, "redirect": next_url})
