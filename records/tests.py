import json
from decimal import Decimal
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import Pet
from records.forms import VaccinationRecordForm
from records.models import VaccinationRecord, VaccinationSchedule, VaccineType


User = get_user_model()


class VaccinationScheduleLogicTests(TestCase):
	def setUp(self):
		self.owner = User.objects.create_user(
			username="owner1",
			email="owner1@example.com",
			password="pass1234",
		)
		self.staff = User.objects.create_user(
			username="staff1",
			email="staff1@example.com",
			password="pass1234",
		)

	def test_dog_5in1_primary_series_uses_birth_date_milestones(self):
		dog = Pet.objects.create(
			owner=self.owner,
			name="Buddy",
			species="dog",
			birth_date=date(2025, 1, 1),
		)
		vaccine_type = VaccineType.objects.create(
			name="5-in-1 Vaccine",
			species="dog",
			booster_interval_days=365,
			is_active=True,
		)

		dose_1 = VaccinationRecord.objects.create(
			pet=dog,
			vaccine_name="5-in-1 Vaccine",
			vaccine_type=vaccine_type,
			date_administered=date(2025, 2, 12),  # 6 weeks
			administered_by=self.staff,
		)
		self.assertEqual(dose_1.next_due_date, date(2025, 2, 26))  # 8 weeks

		dose_2 = VaccinationRecord.objects.create(
			pet=dog,
			vaccine_name="5-in-1 Vaccine",
			vaccine_type=vaccine_type,
			date_administered=date(2025, 2, 26),  # 8 weeks
			administered_by=self.staff,
		)
		self.assertEqual(dose_2.next_due_date, date(2025, 3, 12))  # 10 weeks

		dose_5 = VaccinationRecord.objects.create(
			pet=dog,
			vaccine_name="5-in-1 Vaccine",
			vaccine_type=vaccine_type,
			date_administered=date(2025, 4, 23),  # 16 weeks
			administered_by=self.staff,
		)
		self.assertEqual(dose_5.next_due_date, date(2026, 4, 23))  # annual booster

	def test_cat_felv_primary_then_annual(self):
		cat = Pet.objects.create(
			owner=self.owner,
			name="Mimi",
			species="cat",
			birth_date=date(2025, 1, 1),
		)
		vaccine_type = VaccineType.objects.create(
			name="Feline Leukemia (FeLV)",
			species="cat",
			booster_interval_days=365,
			is_active=True,
		)

		first_dose = VaccinationRecord.objects.create(
			pet=cat,
			vaccine_name="FeLV",
			vaccine_type=vaccine_type,
			date_administered=date(2025, 2, 26),  # 8 weeks
			administered_by=self.staff,
		)
		self.assertEqual(first_dose.next_due_date, date(2025, 3, 26))  # 12 weeks

		second_dose = VaccinationRecord.objects.create(
			pet=cat,
			vaccine_name="Feline Leukemia (FeLV)",
			vaccine_type=vaccine_type,
			date_administered=date(2025, 3, 26),
			administered_by=self.staff,
		)
		self.assertEqual(second_dose.next_due_date, date(2026, 3, 26))

	def test_deworming_without_birth_date_switches_to_maintenance(self):
		dog = Pet.objects.create(
			owner=self.owner,
			name="Rex",
			species="dog",
			birth_date=None,
		)
		vaccine_type = VaccineType.objects.create(
			name="Deworming",
			species="dog",
			booster_interval_days=90,
			is_active=True,
		)

		first_date = date(2025, 1, 1)
		last_record = None
		for index in range(6):
			administered = first_date + timedelta(days=index * 14)
			last_record = VaccinationRecord.objects.create(
				pet=dog,
				vaccine_name="Deworming",
				vaccine_type=vaccine_type,
				date_administered=administered,
				administered_by=self.staff,
			)

		self.assertIsNotNone(last_record)
		self.assertEqual(last_record.next_due_date, date(2025, 6, 12))

	def test_creating_vaccination_updates_schedule_record(self):
		dog = Pet.objects.create(
			owner=self.owner,
			name="Scout",
			species="dog",
			birth_date=date(2025, 1, 1),
		)
		vaccine_type = VaccineType.objects.create(
			name="Rabies Vaccine",
			species="dog",
			booster_interval_days=365,
			is_active=True,
		)

		record = VaccinationRecord.objects.create(
			pet=dog,
			vaccine_name="Rabies Vaccine",
			vaccine_type=vaccine_type,
			date_administered=date(2025, 3, 26),
			administered_by=self.staff,
		)

		schedule = VaccinationSchedule.objects.get(vaccination_record=record)
		self.assertEqual(schedule.next_due_date, record.next_due_date)
		self.assertEqual(schedule.pet, dog)

	def test_vaccination_form_assigns_predefined_price_and_shot_count(self):
		dog = Pet.objects.create(
			owner=self.owner,
			name="Aki",
			species="dog",
			birth_date=date(2025, 1, 1),
		)

		form = VaccinationRecordForm(
			data={
				"administered_vaccine": "Rabies Vaccine",
				"date_administered": "2025-03-26",
				"shots_administered": 2,
			},
			pet=dog,
		)

		self.assertTrue(form.is_valid(), form.errors)
		self.assertGreater(form.cleaned_data["vaccine_price"], 0)
		self.assertEqual(form.cleaned_data["vaccine_price"], form.cleaned_data["vaccine_type"].unit_price)
		self.assertEqual(form.cleaned_data["shots_administered"], 2)

	def test_vaccination_form_prefers_managed_catalog_price_and_schedule(self):
		dog = Pet.objects.create(
			owner=self.owner,
			name="Mochi",
			species="dog",
			birth_date=date(2025, 1, 1),
		)
		VaccineType.objects.create(
			name="Rabies Vaccine",
			species="dog",
			booster_interval_days=365,
			unit_price=Decimal("525.00"),
			description="Clinic protocol: first dose at 12 weeks, then yearly booster.",
			is_active=True,
		)

		form = VaccinationRecordForm(
			data={
				"administered_vaccine": "Rabies Vaccine",
				"date_administered": "2025-03-26",
				"shots_administered": 1,
			},
			pet=dog,
		)

		self.assertTrue(form.is_valid(), form.errors)
		self.assertEqual(form.cleaned_data["vaccine_price"], Decimal("525.00"))
		self.assertEqual(form.cleaned_data["vaccine_type"].unit_price, Decimal("525.00"))

		price_map = json.loads(form.fields["administered_vaccine"].widget.attrs["data-price-map"])
		schedule_map = json.loads(form.fields["administered_vaccine"].widget.attrs["data-schedule-map"])
		self.assertEqual(price_map["Rabies Vaccine"], "525.00")
		self.assertEqual(
			schedule_map["Rabies Vaccine"],
			"Clinic protocol: first dose at 12 weeks, then yearly booster.",
		)
