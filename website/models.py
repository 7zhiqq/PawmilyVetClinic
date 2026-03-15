from django.db import models
from django.conf import settings


class OwnerNotification(models.Model):
	TYPE_APPOINTMENT_REQUESTED = "appointment_requested"
	TYPE_APPOINTMENT_CONFIRMED = "appointment_confirmed"
	TYPE_APPOINTMENT_REJECTED = "appointment_rejected"
	TYPE_APPOINTMENT_COMPLETED = "appointment_completed"
	TYPE_APPOINTMENT_NO_SHOW = "appointment_no_show"
	TYPE_APPOINTMENT_REMINDER_24H = "appointment_reminder_24h"
	TYPE_QUEUE_TODAY = "queue_today"
	TYPE_BILLING_GENERATED = "billing_generated"
	TYPE_PAYMENT_SUBMITTED = "payment_submitted"
	TYPE_PAYMENT_APPROVED = "payment_approved"

	TYPE_CHOICES = [
		(TYPE_APPOINTMENT_REQUESTED, "Appointment Requested"),
		(TYPE_APPOINTMENT_CONFIRMED, "Appointment Confirmed"),
		(TYPE_APPOINTMENT_REJECTED, "Appointment Rejected"),
		(TYPE_APPOINTMENT_COMPLETED, "Appointment Completed"),
		(TYPE_APPOINTMENT_NO_SHOW, "Appointment No Show"),
		(TYPE_APPOINTMENT_REMINDER_24H, "Appointment Reminder (24h)"),
		(TYPE_QUEUE_TODAY, "Today's Queue Update"),
		(TYPE_BILLING_GENERATED, "Billing Generated"),
		(TYPE_PAYMENT_SUBMITTED, "Payment Submitted"),
		(TYPE_PAYMENT_APPROVED, "Payment Approved"),
	]

	user = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name="owner_notifications",
	)
	appointment = models.ForeignKey(
		"appointments.Appointment",
		on_delete=models.CASCADE,
		related_name="owner_notifications",
		null=True,
		blank=True,
	)
	billing_record = models.ForeignKey(
		"billing.BillingRecord",
		on_delete=models.CASCADE,
		related_name="owner_notifications",
		null=True,
		blank=True,
	)
	payment = models.ForeignKey(
		"billing.Payment",
		on_delete=models.CASCADE,
		related_name="owner_notifications",
		null=True,
		blank=True,
	)
	notification_type = models.CharField(max_length=40, choices=TYPE_CHOICES)
	title = models.CharField(max_length=200)
	message = models.TextField()
	link_url = models.CharField(max_length=255, blank=True)
	event_key = models.CharField(max_length=120, unique=True, null=True, blank=True)
	is_important = models.BooleanField(default=True)
	is_read = models.BooleanField(default=False)
	email_sent = models.BooleanField(default=False)
	email_sent_at = models.DateTimeField(null=True, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ["-created_at"]

	def __str__(self):
		return f"{self.user_id} - {self.notification_type} - {self.title}"
