from django.contrib import admin

from .models import OwnerNotification


@admin.register(OwnerNotification)
class OwnerNotificationAdmin(admin.ModelAdmin):
	list_display = (
		"user",
		"notification_type",
		"title",
		"is_read",
		"email_sent",
		"created_at",
	)
	list_filter = ("notification_type", "is_read", "email_sent", "created_at")
	search_fields = ("user__username", "user__email", "title", "message", "event_key")
	readonly_fields = ("created_at", "updated_at", "email_sent_at")
