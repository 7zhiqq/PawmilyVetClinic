from django.urls import path

from . import views

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("register/", views.register_pet_owner, name="register_pet_owner"),
    path("invite/<str:token>/", views.register_with_invite, name="register_with_invite"),
    path("invitations/", views.manage_invitations, name="manage_invitations"),
    path("profile/", views.profile_edit, name="profile_edit"),
    path("pets/", views.pet_list, name="pet_list"),
    path("pets/add/", views.pet_add, name="pet_add"),
    path("pets/<int:pk>/edit/", views.pet_edit, name="pet_edit"),
    # Appointments
    path("appointments/book/", views.appointment_book, name="appointment_book"),
    path("appointments/calendar/", views.appointment_calendar, name="appointment_calendar"),
    path("appointments/queue/", views.appointment_queue, name="appointment_queue"),
    path("appointments/queue/data/", views.queue_data, name="queue_data"),
    path("appointments/queue/action/", views.queue_action, name="queue_action"),
    path("appointments/cancel/", views.appointment_cancel, name="appointment_cancel"),
    path("appointments/manage/", views.appointment_manage, name="appointment_manage"),
    path("appointments/schedule/", views.appointment_schedule, name="appointment_schedule"),
    # AJAX
    path("appointments/slots/", views.get_available_slots, name="get_available_slots"),
]