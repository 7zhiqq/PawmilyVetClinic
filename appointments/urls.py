from django.urls import path

from . import views

urlpatterns = [
    path("appointments/book/", views.appointment_book, name="appointment_book"),
    path("appointments/calendar/", views.appointment_calendar, name="appointment_calendar"),
    path("appointments/queue/", views.appointment_queue, name="appointment_queue"),
    path("appointments/queue/data/", views.queue_data, name="queue_data"),
    path("appointments/queue/action/", views.queue_action, name="queue_action"),
    path("appointments/cancel/", views.appointment_cancel, name="appointment_cancel"),
    path("appointments/manage/", views.appointment_manage, name="appointment_manage"),
    path("appointments/schedule/", views.appointment_schedule, name="appointment_schedule"),
    path("appointments/slots/", views.get_available_slots, name="get_available_slots"),
]
