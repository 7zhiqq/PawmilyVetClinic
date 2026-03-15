from django.urls import path

from . import views

urlpatterns = [
    path("", views.landing_page, name="home"),
    path("about/", views.about_page, name="about_page"),
    path("services/<slug:service_slug>/", views.service_page, name="service_page"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("reminders/", views.reminders_view, name="reminders"),
]