from django.urls import path

from apps.authentication.browser_views import browser_login, browser_login_google

urlpatterns = [
    path("login/", browser_login, name="browser-login"),
    path("login/google/", browser_login_google, name="browser-login-google"),
]
