from decimal import Decimal
from datetime import date, time

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.test import TestCase

from accounts.models import Pet
from appointments.models import Appointment
from billing.models import BillingLineItem, Payment
from billing.views import add_vaccination_to_billing, create_billing_for_appointment


User = get_user_model()


class VaccinationBillingTests(TestCase):
	def setUp(self):
		self.owner = User.objects.create_user(
			username="owner_billing",
			email="owner.billing@example.com",
			password="pass1234",
		)
		self.pet = Pet.objects.create(
			owner=self.owner,
			name="Poppy",
			species="dog",
			birth_date=date(2024, 1, 1),
		)
		self.appointment = Appointment.objects.create(
			owner=self.owner,
			pet=self.pet,
			appointment_date=date.today(),
			start_time=time(9, 0),
			end_time=time(9, 30),
			reason="Vaccination update",
			status=Appointment.STATUS_COMPLETED,
		)

	def test_vaccination_charge_creates_billing_record_if_missing(self):
		add_vaccination_to_billing(
			self.appointment,
			vaccine_name="Rabies Vaccine",
			unit_price=Decimal("450.00"),
			quantity=1,
		)

		self.appointment.refresh_from_db()
		billing_record = self.appointment.billing_record
		self.assertIsNotNone(billing_record)
		vaccination_line = billing_record.line_items.filter(
			description="Vaccination – Rabies Vaccine"
		).first()
		self.assertIsNotNone(vaccination_line)
		self.assertEqual(vaccination_line.quantity, 1)
		self.assertEqual(vaccination_line.unit_price, Decimal("450.00"))

	def test_vaccination_charge_uses_quantity_for_multiple_shots(self):
		billing_record = create_billing_for_appointment(self.appointment)

		add_vaccination_to_billing(
			self.appointment,
			vaccine_name="5-in-1 Vaccine",
			unit_price=Decimal("850.00"),
			quantity=3,
		)

		vaccination_line = BillingLineItem.objects.get(
			billing_record=billing_record,
			description="Vaccination – 5-in-1 Vaccine",
		)
		self.assertEqual(vaccination_line.quantity, 3)
		self.assertEqual(vaccination_line.line_total, Decimal("2550.00"))

		billing_record.refresh_from_db()
		self.assertEqual(billing_record.total_amount, Decimal("2850.00"))


class PaymentVerificationWorkflowTests(TestCase):
	def setUp(self):
		self.owner = User.objects.create_user(
			username="owner_payment",
			email="owner.payment@example.com",
			password="pass1234",
		)
		self.staff = User.objects.create_user(
			username="staff_payment",
			email="staff.payment@example.com",
			password="pass1234",
			role="staff",
		)
		self.pet = Pet.objects.create(
			owner=self.owner,
			name="Milo",
			species="dog",
			birth_date=date(2023, 5, 10),
		)
		self.appointment = Appointment.objects.create(
			owner=self.owner,
			pet=self.pet,
			appointment_date=date.today(),
			start_time=time(10, 0),
			end_time=time(10, 30),
			reason="General consultation",
			status=Appointment.STATUS_COMPLETED,
		)
		self.billing_record = create_billing_for_appointment(self.appointment, created_by=self.staff)

	def test_owner_payment_submission_is_pending_and_not_applied_until_verified(self):
		self.client.login(username="owner_payment", password="pass1234")

		response = self.client.post(
			reverse("billing_submit_payment", args=[self.billing_record.pk]),
			{
				"amount": "300.00",
				"method": Payment.METHOD_GCASH,
				"reference": "GCASH-123456",
			},
		)
		self.assertEqual(response.status_code, 302)

		payment = Payment.objects.get(billing_record=self.billing_record)
		self.assertEqual(payment.verification_status, Payment.VERIFICATION_STATUS_PENDING)
		self.assertEqual(payment.submitted_by, self.owner)

		self.billing_record.refresh_from_db()
		self.assertEqual(self.billing_record.amount_paid, Decimal("0.00"))
		self.assertEqual(self.billing_record.payment_status, self.billing_record.PAYMENT_STATUS_UNPAID)

	def test_staff_approval_marks_billing_as_paid_when_balance_is_cleared(self):
		pending_payment = Payment.objects.create(
			billing_record=self.billing_record,
			amount=Decimal("300.00"),
			method=Payment.METHOD_MAYA,
			reference="MAYA-998877",
			submitted_by=self.owner,
			verification_status=Payment.VERIFICATION_STATUS_PENDING,
		)

		self.client.login(username="staff_payment", password="pass1234")
		response = self.client.post(
			reverse("billing_verify_payment", args=[self.billing_record.pk, pending_payment.pk]),
			{"action": "approve"},
		)
		self.assertEqual(response.status_code, 302)

		pending_payment.refresh_from_db()
		self.assertEqual(pending_payment.verification_status, Payment.VERIFICATION_STATUS_APPROVED)
		self.assertEqual(pending_payment.verified_by, self.staff)
		self.assertIsNotNone(pending_payment.verified_at)

		self.billing_record.refresh_from_db()
		self.assertEqual(self.billing_record.amount_paid, Decimal("300.00"))
		self.assertEqual(self.billing_record.payment_status, self.billing_record.PAYMENT_STATUS_PAID)
