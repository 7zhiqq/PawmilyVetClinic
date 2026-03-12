from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from accounts.models import Pet, Profile
from billing.models import BillingRecord

from .forms import AppointmentBookingForm, AppointmentStaffForm
from .models import Appointment
from .views import _calendar_context


class AppointmentBookingFormReasonTests(TestCase):
	def setUp(self):
		user_model = get_user_model()
		self.owner = user_model.objects.create_user(username="owner1", password="testpass123")
		self.pet = Pet.objects.create(owner=self.owner, name="Buddy", species=Pet.SPECIES_DOG)
		self.base_data = {
			"pet": self.pet.pk,
			"appointment_date": (date.today() + timedelta(days=1)).isoformat(),
			"start_time": "09:00",
		}

	def test_predefined_reason_is_saved_directly(self):
		form = AppointmentBookingForm(
			data={**self.base_data, "reason": "Vaccination"},
			owner=self.owner,
		)

		self.assertTrue(form.is_valid())
		self.assertEqual(form.cleaned_data["reason"], "Vaccination")

	def test_other_reason_requires_custom_value(self):
		form = AppointmentBookingForm(
			data={**self.base_data, "reason": "Other", "reason_other": ""},
			owner=self.owner,
		)

		self.assertFalse(form.is_valid())
		self.assertIn("reason_other", form.errors)

	def test_other_reason_uses_custom_value_as_reason(self):
		form = AppointmentBookingForm(
			data={**self.base_data, "reason": "Other", "reason_other": "Follow-up for limping"},
			owner=self.owner,
		)

		self.assertTrue(form.is_valid())
		self.assertEqual(form.cleaned_data["reason"], "Follow-up for limping")


class AppointmentStaffFormReasonTests(TestCase):
	def setUp(self):
		user_model = get_user_model()
		self.owner = user_model.objects.create_user(username="owner2", password="testpass123")
		Profile.objects.create(user=self.owner, role=Profile.ROLE_PET_OWNER)
		self.pet = Pet.objects.create(owner=self.owner, name="Milo", species=Pet.SPECIES_CAT)
		self.base_data = {
			"owner": self.owner.pk,
			"pet": self.pet.pk,
			"appointment_date": (date.today() + timedelta(days=1)).isoformat(),
			"start_time": "10:00",
			"end_time": "11:00",
			"appointment_type": "walk_in",
			"notes": "",
			"status": "confirmed",
		}

	def test_other_reason_requires_custom_value(self):
		form = AppointmentStaffForm(
			data={**self.base_data, "reason": "Other", "reason_other": ""},
		)

		self.assertFalse(form.is_valid())
		self.assertIn("reason_other", form.errors)

	def test_other_reason_uses_custom_value(self):
		form = AppointmentStaffForm(
			data={**self.base_data, "reason": "Other", "reason_other": "Emergency wound cleaning"},
		)

		self.assertTrue(form.is_valid())
		self.assertEqual(form.cleaned_data["reason"], "Emergency wound cleaning")


class AppointmentCalendarBillingVisibilityTests(TestCase):
	def setUp(self):
		user_model = get_user_model()
		self.factory = RequestFactory()
		self.owner = user_model.objects.create_user(username="calendar-owner", password="testpass123")
		Profile.objects.create(user=self.owner, role=Profile.ROLE_PET_OWNER)
		self.pet = Pet.objects.create(owner=self.owner, name="Choco", species=Pet.SPECIES_DOG)
		self.target_date = date.today().replace(day=1)

	def _create_appointment(self, slot_number):
		return Appointment.objects.create(
			owner=self.owner,
			pet=self.pet,
			appointment_date=self.target_date,
			start_time=time(9 + slot_number, 0),
			end_time=time(10 + slot_number, 0),
			slot_number=slot_number,
			status=Appointment.STATUS_COMPLETED,
			appointment_type=Appointment.TYPE_SCHEDULED,
			reason="Check-up",
		)

	def test_paid_billing_records_are_hidden_from_calendar(self):
		paid_appointment = self._create_appointment(1)
		partial_appointment = self._create_appointment(2)

		BillingRecord.objects.create(
			appointment=paid_appointment,
			owner=self.owner,
			pet=self.pet,
			payment_status=BillingRecord.PAYMENT_STATUS_PAID,
			total_amount=Decimal("500.00"),
			amount_paid=Decimal("500.00"),
		)
		BillingRecord.objects.create(
			appointment=partial_appointment,
			owner=self.owner,
			pet=self.pet,
			payment_status=BillingRecord.PAYMENT_STATUS_PARTIAL,
			total_amount=Decimal("500.00"),
			amount_paid=Decimal("250.00"),
		)

		request = self.factory.get(
			"/accounts/appointments/calendar/",
			{"year": self.target_date.year, "month": self.target_date.month},
		)
		request.user = self.owner

		context = _calendar_context(request)
		appointments_for_day = []
		for week in context["calendar_weeks"]:
			for day_date, day_appointments in week:
				if day_date == self.target_date:
					appointments_for_day = day_appointments
					break

		self.assertIn(partial_appointment, appointments_for_day)
		self.assertNotIn(paid_appointment, appointments_for_day)
