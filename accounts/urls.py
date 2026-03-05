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
    # Staff pet lookup
    path("pets/search/", views.pet_records_search, name="pet_records_search"),
    # Walk-in client registration
    path("walkin/register/", views.walkin_register, name="walkin_register"),
    path("walkin/activate/<str:token>/", views.walkin_activate, name="walkin_activate"),
    path("walkin/qr/<str:token>/", views.walkin_qr_image, name="walkin_qr_image"),
    path("walkin/print/<str:token>/", views.walkin_print_card, name="walkin_print_card"),
    # Appointments
    path("appointments/book/", views.appointment_book, name="appointment_book"),
    path("appointments/calendar/", views.appointment_calendar, name="appointment_calendar"),
    path("appointments/queue/", views.appointment_queue, name="appointment_queue"),
    path("appointments/queue/data/", views.queue_data, name="queue_data"),
    path("appointments/queue/action/", views.queue_action, name="queue_action"),
    path("appointments/cancel/", views.appointment_cancel, name="appointment_cancel"),
    path("appointments/manage/", views.appointment_manage, name="appointment_manage"),
    path("appointments/schedule/", views.appointment_schedule, name="appointment_schedule"),
    # Medical records
    path("pets/<int:pet_id>/records/", views.medical_records_list, name="medical_records_list"),
    path("pets/<int:pet_id>/records/add/", views.medical_record_add, name="medical_record_add"),
    path("pets/<int:pet_id>/records/<int:record_id>/", views.medical_record_detail, name="medical_record_detail"),
    path("pets/<int:pet_id>/records/<int:record_id>/edit/", views.medical_record_edit, name="medical_record_edit"),
    path("pets/<int:pet_id>/vaccinations/add/", views.vaccination_add, name="vaccination_add"),
    path("pets/<int:pet_id>/records/<int:record_id>/attachments/add/", views.attachment_add, name="attachment_add"),
    # AJAX
    path("appointments/slots/", views.get_available_slots, name="get_available_slots"),
]