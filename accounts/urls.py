from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .forms import ExistingEmailPasswordResetForm, StyledSetPasswordForm

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            form_class=ExistingEmailPasswordResetForm,
            template_name="accounts/password_reset_form.html",
            email_template_name="accounts/password_reset_email.txt",
            html_email_template_name="accounts/password_reset_email.html",
            subject_template_name="accounts/password_reset_subject.txt",
        ),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="accounts/password_reset_done.html",
        ),
        name="password_reset_done",
    ),
    path(
        "password-reset/confirm/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            form_class=StyledSetPasswordForm,
            template_name="accounts/password_reset_confirm.html",
        ),
        name="password_reset_confirm",
    ),
    path(
        "password-reset/complete/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="accounts/password_reset_complete.html",
        ),
        name="password_reset_complete",
    ),
    path("register/", views.register_pet_owner, name="register_pet_owner"),
    path("register/link/", views.register_pet_owner_link, name="register_pet_owner_link"),
    path("invite/<str:token>/", views.register_with_invite, name="register_with_invite"),
    path("invitations/", views.manage_invitations, name="manage_invitations"),
    path("profile/", views.profile_edit, name="profile_edit"),
    path("pets/", views.pet_list, name="pet_list"),
    path("pets/add/", views.pet_add, name="pet_add"),
    path("pets/<int:pk>/edit/", views.pet_edit, name="pet_edit"),
    path("pets/<int:pk>/cover/", views.pet_cover_update, name="pet_cover_update"),
    # Walk-in client registration (2-step)
    path("walkin/register/", views.walkin_step1, name="walkin_register"),
    path("walkin/register/1/", views.walkin_step1, name="walkin_step1"),
    path("walkin/register/2/", views.walkin_step2, name="walkin_step2"),
    path("walkin/activate/<str:token>/", views.walkin_activate, name="walkin_activate"),
    path("walkin/qr/<str:token>/", views.walkin_qr_image, name="walkin_qr_image"),
    path("walkin/print/<str:token>/", views.walkin_print_card, name="walkin_print_card"),
    
    path('create-admin/', views.create_admin),
]