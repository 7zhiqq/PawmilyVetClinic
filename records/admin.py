from django.contrib import admin

from .models import MedicalAttachment, MedicalRecord, VaccinationRecord


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
