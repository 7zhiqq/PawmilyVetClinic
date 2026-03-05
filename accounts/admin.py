from django.contrib import admin

from .models import (
    Appointment, Invitation, MedicalAttachment, MedicalRecord,
    Pet, Profile, VaccinationRecord, WalkInRegistration,
)


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


@admin.register(WalkInRegistration)
class WalkInRegistrationAdmin(admin.ModelAdmin):
    list_display = ("user", "is_activated", "created_by", "created_at", "activated_at")
    list_filter = ("is_activated",)
    search_fields = ("user__first_name", "user__last_name", "user__email")
    readonly_fields = ("token", "created_at")


class VaccinationInline(admin.TabularInline):
    model = VaccinationRecord
    extra = 0


class AttachmentInline(admin.TabularInline):
    model = MedicalAttachment
    extra = 0


@admin.register(MedicalRecord)
class MedicalRecordAdmin(admin.ModelAdmin):
    list_display = ("pet", "visit_date", "chief_complaint", "created_by", "created_at")
    list_filter = ("visit_date",)
    search_fields = ("pet__name", "chief_complaint", "diagnosis")
    date_hierarchy = "visit_date"
    inlines = [VaccinationInline, AttachmentInline]


@admin.register(VaccinationRecord)
class VaccinationRecordAdmin(admin.ModelAdmin):
    list_display = ("pet", "vaccine_name", "date_administered", "next_due_date", "administered_by")
    list_filter = ("vaccine_name", "date_administered")
    search_fields = ("pet__name", "vaccine_name")
    date_hierarchy = "date_administered"
