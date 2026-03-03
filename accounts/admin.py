from django.contrib import admin

from .models import Appointment, Invitation, Pet, Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role")
    list_filter = ("role",)
    search_fields = ("user__username", "user__email")


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("pet", "owner", "appointment_date", "start_time", "status", "appointment_type")
    list_filter = ("status", "appointment_type")
    search_fields = ("owner__username", "pet__name")
    date_hierarchy = "appointment_date"


@admin.register(Pet)
class PetAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "species", "breed", "birth_date")
    list_filter = ("species",)
    search_fields = ("name", "owner__username", "breed")


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = ("email", "role", "is_used", "created_at")
    list_filter = ("role", "is_used")
    search_fields = ("email",)
    readonly_fields = ("token", "created_at")
