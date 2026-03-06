from django.urls import path

from . import views

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("register/", views.register_pet_owner, name="register_pet_owner"),
    path("register/link/", views.register_pet_owner_link, name="register_pet_owner_link"),
    path("invite/<str:token>/", views.register_with_invite, name="register_with_invite"),
    path("invitations/", views.manage_invitations, name="manage_invitations"),
    path("profile/", views.profile_edit, name="profile_edit"),
    path("pets/", views.pet_list, name="pet_list"),
    path("pets/add/", views.pet_add, name="pet_add"),
    path("pets/<int:pk>/edit/", views.pet_edit, name="pet_edit"),
    # Walk-in client registration (2-step)
    path("walkin/register/", views.walkin_step1, name="walkin_register"),
    path("walkin/register/1/", views.walkin_step1, name="walkin_step1"),
    path("walkin/register/2/", views.walkin_step2, name="walkin_step2"),
    path("walkin/activate/<str:token>/", views.walkin_activate, name="walkin_activate"),
    path("walkin/qr/<str:token>/", views.walkin_qr_image, name="walkin_qr_image"),
    path("walkin/print/<str:token>/", views.walkin_print_card, name="walkin_print_card"),
]