from django.urls import path

from . import views

urlpatterns = [
    path("pets/search/", views.pet_records_search, name="pet_records_search"),
    path("pets/<int:pet_id>/records/", views.medical_records_list, name="medical_records_list"),
    path("pets/<int:pet_id>/records/add/", views.medical_record_add, name="medical_record_add"),
    path("pets/<int:pet_id>/records/<int:record_id>/", views.medical_record_detail, name="medical_record_detail"),
    path("pets/<int:pet_id>/records/<int:record_id>/edit/", views.medical_record_edit, name="medical_record_edit"),
    path("pets/<int:pet_id>/vaccinations/add/", views.vaccination_add, name="vaccination_add"),
    path("pets/<int:pet_id>/records/<int:record_id>/attachments/add/", views.attachment_add, name="attachment_add"),
    path("appointments/<int:appointment_id>/finalize/", views.finalize_step1, name="finalize_step1"),
    path("appointments/<int:appointment_id>/finalize/1/", views.finalize_step1, name="finalize_step1_explicit"),
    path("appointments/<int:appointment_id>/finalize/2/", views.finalize_step2, name="finalize_step2"),
    path("appointments/<int:appointment_id>/finalize/3/", views.finalize_step3, name="finalize_step3"),
    path("appointments/<int:appointment_id>/finalize/4/", views.finalize_step4, name="finalize_step4"),
]
