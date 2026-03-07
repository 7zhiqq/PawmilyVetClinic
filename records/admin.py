from django.contrib import admin

from .models import (
    MedicalAttachment, MedicalRecord, VaccinationRecord,
    VaccineType, VaccinationSchedule, FollowUpReminder
)


class VaccinationInline(admin.TabularInline):
    model = VaccinationRecord
    extra = 0


class AttachmentInline(admin.TabularInline):
    model = MedicalAttachment
    extra = 0


class VaccinationScheduleInline(admin.TabularInline):
    model = VaccinationSchedule
    extra = 0
    readonly_fields = ("created_at", "updated_at")


class FollowUpReminderInline(admin.TabularInline):
    model = FollowUpReminder
    extra = 0
    readonly_fields = ("created_at", "updated_at")


@admin.register(VaccineType)
class VaccineTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "species", "booster_interval_days", "is_active")
    list_filter = ("species", "is_active")
    search_fields = ("name",)


@admin.register(MedicalRecord)
class MedicalRecordAdmin(admin.ModelAdmin):
    list_display = ("pet", "visit_date", "chief_complaint", "follow_up_date", "created_by", "created_at")
    list_filter = ("visit_date", "follow_up_date")
    search_fields = ("pet__name", "chief_complaint", "diagnosis")
    date_hierarchy = "visit_date"
    inlines = [VaccinationInline, AttachmentInline, FollowUpReminderInline]


@admin.register(VaccinationRecord)
class VaccinationRecordAdmin(admin.ModelAdmin):
    list_display = ("pet", "vaccine_name", "vaccine_type", "date_administered", "next_due_date", "administered_by")
    list_filter = ("vaccine_name", "vaccine_type", "date_administered")
    search_fields = ("pet__name", "vaccine_name")
    date_hierarchy = "date_administered"
    inlines = [VaccinationScheduleInline]


@admin.register(VaccinationSchedule)
class VaccinationScheduleAdmin(admin.ModelAdmin):
    list_display = ("pet", "vaccine_type", "next_due_date", "status", "reminder_sent", "get_days_until_due")
    list_filter = ("status", "next_due_date", "reminder_sent")
    search_fields = ("pet__name", "vaccine_type__name")
    date_hierarchy = "next_due_date"
    readonly_fields = ("created_at", "updated_at")
    actions = ["mark_completed", "mark_skipped", "mark_overdue", "send_reminders"]

    def get_days_until_due(self, obj):
        """Display days until due in a readable format."""
        days = obj.days_until_due()
        if obj.status == VaccinationSchedule.STATUS_OVERDUE:
            return f"✕ {abs(days)} days overdue"
        elif obj.status == VaccinationSchedule.STATUS_DUE:
            return f"⚠ {days} days"
        else:
            return f"→ {days} days"
    get_days_until_due.short_description = "Days until due"

    def mark_completed(self, request, queryset):
        """Mark selected vaccines as completed."""
        updated = queryset.update(status=VaccinationSchedule.STATUS_COMPLETED)
        self.message_user(request, f"✓ Marked {updated} vaccination(s) as completed.")
    mark_completed.short_description = "Mark selected as completed"

    def mark_skipped(self, request, queryset):
        """Mark selected vaccines as skipped."""
        updated = queryset.update(status=VaccinationSchedule.STATUS_SKIPPED)
        self.message_user(request, f"✓ Marked {updated} vaccination(s) as skipped.")
    mark_skipped.short_description = "Mark selected as skipped"

    def mark_overdue(self, request, queryset):
        """Manually mark selected as overdue for testing/admin purposes."""
        updated = queryset.update(status=VaccinationSchedule.STATUS_OVERDUE)
        self.message_user(request, f"✓ Marked {updated} vaccination(s) as overdue.")
    mark_overdue.short_description = "Mark selected as overdue"

    def send_reminders(self, request, queryset):
        """Send reminders for selected vaccines."""
        from django.utils import timezone
        updated = queryset.exclude(reminder_sent=True).update(
            reminder_sent=True,
            reminder_sent_date=timezone.now()
        )
        self.message_user(request, f"✓ Sent reminders for {updated} vaccination(s).")
    send_reminders.short_description = "Mark reminders as sent"



@admin.register(FollowUpReminder)
class FollowUpReminderAdmin(admin.ModelAdmin):
    list_display = ("pet", "follow_up_date", "reason", "status", "reminder_sent", "get_days_until_due")
    list_filter = ("status", "follow_up_date", "reminder_sent")
    search_fields = ("pet__name", "reason")
    date_hierarchy = "follow_up_date"
    readonly_fields = ("created_at", "updated_at")
    actions = ["mark_completed", "mark_cancelled", "send_reminders"]

    def get_days_until_due(self, obj):
        """Display days until due in a readable format."""
        days = obj.days_until_due()
        if obj.status == FollowUpReminder.STATUS_OVERDUE:
            return f"✕ {abs(days)} days overdue"
        elif obj.status == FollowUpReminder.STATUS_DUE:
            return f"⚠ {days} days"
        else:
            return f"→ {days} days"
    get_days_until_due.short_description = "Days until due"

    def mark_completed(self, request, queryset):
        """Mark selected follow-ups as completed."""
        updated = queryset.update(status=FollowUpReminder.STATUS_COMPLETED)
        self.message_user(request, f"✓ Marked {updated} follow-up(s) as completed.")
    mark_completed.short_description = "Mark selected as completed"

    def mark_cancelled(self, request, queryset):
        """Mark selected follow-ups as cancelled."""
        updated = queryset.update(status=FollowUpReminder.STATUS_CANCELLED)
        self.message_user(request, f"✓ Marked {updated} follow-up(s) as cancelled.")
    mark_cancelled.short_description = "Mark selected as cancelled"

    def send_reminders(self, request, queryset):
        """Send reminders for selected follow-ups."""
        from django.utils import timezone
        updated = queryset.exclude(reminder_sent=True).update(
            reminder_sent=True,
            reminder_sent_date=timezone.now()
        )
        self.message_user(request, f"✓ Sent reminders for {updated} follow-up(s).")
    send_reminders.short_description = "Mark reminders as sent"


