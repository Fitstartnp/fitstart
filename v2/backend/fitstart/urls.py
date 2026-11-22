from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

@method_decorator(ensure_csrf_cookie, name="dispatch")
class InvitationPageView(TemplateView):
    template_name = "invite/accept.html"


class HomeView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard.html"


urlpatterns = [
    path("admin/", admin.site.urls),
    path("invite/", InvitationPageView.as_view(), name="invite-accept-page"),
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path(
        "accounts/password-reset/",
        auth_views.PasswordResetView.as_view(template_name="registration/password_reset_form.html"),
        name="password_reset",
    ),
    path(
        "accounts/password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(template_name="registration/password_reset_done.html"),
        name="password_reset_done",
    ),
    path(
        "accounts/reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(template_name="registration/password_reset_confirm.html"),
        name="password_reset_confirm",
    ),
    path(
        "accounts/reset/done/",
        auth_views.PasswordResetCompleteView.as_view(template_name="registration/password_reset_complete.html"),
        name="password_reset_complete",
    ),
    path("api/v1/", include("apps.api.urls")),
    path("", HomeView.as_view(), name="home"),
]
