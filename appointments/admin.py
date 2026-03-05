from django.contrib import admin

from .models import Appointment


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("pet", "owner", "appointment_date", "start_time", "status", "appointment_type")
    list_filter = ("status", "appointment_type")
    search_fields = ("owner__username", "pet__name")
    date_hierarchy = "appointment_date"
