from django.test import TestCase
from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
from django.test import override_settings

from accounts.models import Pet, Profile
from appointments.models import Appointment

from .models import OwnerNotification
from .notifications import (
	notify_appointment_requested,
	notify_same_day_queue_update,
)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class OwnerNotificationTests(TestCase):
	def setUp(self):
		user_model = get_user_model()
		self.owner = user_model.objects.create_user(
			username="owner_notify",
			email="owner.notify@example.com",
			password="pass1234",
		)
		Profile.objects.create(user=self.owner, role=Profile.ROLE_PET_OWNER)
		self.pet = Pet.objects.create(owner=self.owner, name="Buddy", species=Pet.SPECIES_DOG)
		self.appointment = Appointment.objects.create(
			owner=self.owner,
			pet=self.pet,
			appointment_date=date.today() + timedelta(days=1),
			start_time=time(10, 0),
			end_time=time(10, 30),
			status=Appointment.STATUS_PENDING,
			appointment_type=Appointment.TYPE_SCHEDULED,
			reason="Vaccination",
			slot_number=1,
		)

	def test_notify_appointment_requested_creates_notification(self):
		notify_appointment_requested(self.appointment)

		notif = OwnerNotification.objects.get(user=self.owner, appointment=self.appointment)
		self.assertEqual(notif.notification_type, OwnerNotification.TYPE_APPOINTMENT_REQUESTED)
		self.assertIn("successfully submitted", notif.message)
		self.assertTrue(notif.email_sent)

	def test_same_day_queue_notification_is_updated_not_duplicated(self):
		self.appointment.appointment_date = date.today()
		self.appointment.status = Appointment.STATUS_CONFIRMED
		self.appointment.save(update_fields=["appointment_date", "status", "updated_at"])

		notify_same_day_queue_update(
			self.appointment,
			queue_position=7,
			current_serving_number=4,
		)
		notify_same_day_queue_update(
			self.appointment,
			queue_position=5,
			current_serving_number=4,
		)

		notifications = OwnerNotification.objects.filter(
			notification_type=OwnerNotification.TYPE_QUEUE_TODAY,
			appointment=self.appointment,
		)
		self.assertEqual(notifications.count(), 1)
		self.assertIn("#5", notifications.first().message)
