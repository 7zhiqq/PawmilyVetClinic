"""
Django management command to seed the database with realistic test data using Faker.

Usage:
    python manage.py seed_data [--clear]

Options:
    --clear: Clear existing data before seeding
"""

import random
from datetime import datetime, time, timedelta
from decimal import Decimal


def _random_ph_phone():
    """Return a random valid Philippine mobile number in +639XXXXXXXXX format."""
    suffix = ''.join(str(random.randint(0, 9)) for _ in range(9))
    return f'+639{suffix}'

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from faker import Faker

from accounts.models import Pet, Profile
from appointments.models import Appointment
from billing.models import BillingLineItem, BillingRecord, Payment
from records.models import (
    MedicalRecord,
    VaccinationRecord,
    VaccineType,
)

User = get_user_model()
fake = Faker()


class Command(BaseCommand):
    help = "Seed the database with realistic test data using Faker"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing data before seeding",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            self.stdout.write(self.style.WARNING("Clearing existing data..."))
            self._clear_data()

        self.stdout.write(self.style.SUCCESS("Starting data seeding..."))

        with transaction.atomic():
            # Create staff/manager users
            self.stdout.write("Creating staff and manager users...")
            staff_users = self._create_staff_users()

            # Create vaccine types
            self.stdout.write("Creating vaccine types...")
            vaccine_types = self._create_vaccine_types()

            # Create pet owners (furparents)
            self.stdout.write("Creating pet owners...")
            pet_owners = self._create_pet_owners(30, 50)

            # Create pets
            self.stdout.write("Creating pets...")
            pets = self._create_pets(pet_owners)

            # Create appointments
            self.stdout.write("Creating appointments...")
            appointments = self._create_appointments(pets, staff_users)

            # Create medical records for completed appointments
            self.stdout.write("Creating medical records...")
            medical_records = self._create_medical_records(appointments, staff_users)

            # Create vaccination records
            self.stdout.write("Creating vaccination records...")
            self._create_vaccination_records(
                medical_records, vaccine_types, staff_users
            )

            # Create billing records and payments
            self.stdout.write("Creating billing records and payments...")
            self._create_billing_records(appointments, staff_users)

        self._print_summary(pet_owners, pets, appointments)

    def _clear_data(self):
        """Clear existing test data."""
        Payment.objects.all().delete()
        BillingLineItem.objects.all().delete()
        BillingRecord.objects.all().delete()
        VaccinationRecord.objects.all().delete()
        MedicalRecord.objects.all().delete()
        Appointment.objects.all().delete()
        Pet.objects.all().delete()
        VaccineType.objects.all().delete()
        # Only delete pet owners, not staff/managers
        User.objects.filter(profile__role=Profile.ROLE_PET_OWNER).delete()

    def _create_staff_users(self):
        """Create staff and manager users."""
        staff_users = []

        # Create 1 manager
        manager = User.objects.create_user(
            username="manager",
            email="manager@pawmily.vet",
            password="password123",
            first_name="Dr. Maria",
            last_name="Santos",
        )
        Profile.objects.create(
            user=manager,
            role=Profile.ROLE_MANAGER,
            phone=_random_ph_phone(),
            address=fake.address(),
            is_profile_completed=True,
        )
        staff_users.append(manager)

        # Create 3 staff members
        for i in range(3):
            staff = User.objects.create_user(
                username=f"staff{i+1}",
                email=f"staff{i+1}@pawmily.vet",
                password="password123",
                first_name=fake.first_name(),
                last_name=fake.last_name(),
            )
            Profile.objects.create(
                user=staff,
                role=Profile.ROLE_STAFF,
                phone=_random_ph_phone(),
                address=fake.address(),
                is_profile_completed=True,
            )
            staff_users.append(staff)

        return staff_users

    def _create_vaccine_types(self):
        """Create vaccine types if they don't exist."""
        vaccine_data = [
            # Dog vaccines and preventive treatments
            ("5-in-1 Vaccine", "dog", 365, Decimal("850.00"), "Distemper, Adenovirus/Hepatitis, Parvovirus, Parainfluenza, Leptospirosis"),
            ("Rabies Vaccine", "dog", 365, Decimal("450.00"), "First dose at 12 weeks, then annual booster"),
            ("Kennel Cough (Bordetella)", "dog", 365, Decimal("650.00"), "First dose at 8 to 12 weeks, then annual booster"),
            ("Coronavirus", "dog", 365, Decimal("600.00"), "Optional schedule with primary doses and annual booster"),
            ("Deworming", "dog", 90, Decimal("250.00"), "2, 4, 6, 8, 10, 12 weeks then every 3 months"),
            ("Tick & Flea Prevention", "dog", 30, Decimal("300.00"), "Start at 6 to 8 weeks, monthly treatment"),
            # Cat vaccines and preventive treatments
            ("FVRCP Vaccine", "cat", 365, Decimal("800.00"), "6 to 8, 10 to 12, 14 to 16 weeks then annual booster"),
            ("Rabies Vaccine", "cat", 365, Decimal("450.00"), "First dose at 12 weeks, then annual booster"),
            ("Feline Leukemia (FeLV)", "cat", 365, Decimal("900.00"), "8 to 12 weeks, second dose after 3 to 4 weeks, then annual booster"),
            ("Deworming", "cat", 90, Decimal("250.00"), "2, 4, 6, 8, 10, 12 weeks then every 3 months"),
            ("Tick & Flea Prevention", "cat", 30, Decimal("300.00"), "Start at 6 to 8 weeks, monthly treatment"),
        ]

        vaccine_types = []
        for name, species, interval, unit_price, description in vaccine_data:
            vaccine, created = VaccineType.objects.get_or_create(
                name=name,
                species=species,
                defaults={
                    "booster_interval_days": interval,
                    "unit_price": unit_price,
                    "description": description,
                    "is_active": True,
                },
            )
            vaccine_types.append(vaccine)

        return vaccine_types

    def _create_pet_owners(self, min_count, max_count):
        """Create pet owner users with profiles."""
        pet_owners = []
        count = random.randint(min_count, max_count)

        for i in range(count):
            # Generate unique username
            first_name = fake.first_name()
            last_name = fake.last_name()
            username = f"{first_name.lower()}.{last_name.lower()}{i}"

            owner = User.objects.create_user(
                username=username,
                email=fake.email(),
                password="password123",
                first_name=first_name,
                last_name=last_name,
            )

            Profile.objects.create(
                user=owner,
                role=Profile.ROLE_PET_OWNER,
                phone=_random_ph_phone(),
                address=fake.address(),
                is_profile_completed=True,
                date_created=fake.date_time_between(
                    start_date="-2y", end_date="now", tzinfo=timezone.get_current_timezone()
                ),
            )

            pet_owners.append(owner)

        return pet_owners

    def _create_pets(self, pet_owners):
        """Create 1-3 pets for each pet owner."""
        pets = []

        dog_breeds = [
            "Golden Retriever", "Labrador Retriever", "German Shepherd",
            "Poodle", "Bulldog", "Beagle", "Siberian Husky", "Dachshund",
            "Pomeranian", "Shih Tzu", "Chihuahua", "Aspin (Asong Pinoy)",
        ]

        cat_breeds = [
            "Persian", "Siamese", "Maine Coon", "British Shorthair",
            "Ragdoll", "Bengal", "Scottish Fold", "Puspin (Pusang Pinoy)",
            "Sphynx", "Birman",
        ]

        pet_colors = [
            "Brown", "Black", "White", "Golden", "Grey", "Orange",
            "Tan", "Spotted", "Tricolor", "Black and White",
        ]

        dog_names = [
            "Max", "Bella", "Charlie", "Luna", "Rocky", "Daisy",
            "Buddy", "Lucy", "Cooper", "Sadie", "Duke", "Molly",
            "Bear", "Lola", "Zeus", "Coco", "Brownie", "Bantay",
        ]

        cat_names = [
            "Oliver", "Luna", "Milo", "Bella", "Simba", "Lucy",
            "Leo", "Nala", "Jasper", "Chloe", "Felix", "Whiskers",
            "Shadow", "Mittens", "Tiger", "Ming Ming", "Garfield",
        ]

        for owner in pet_owners:
            num_pets = random.randint(1, 3)
            used_names = set()  # Track used names for this owner

            for i in range(num_pets):
                species = random.choice([Pet.SPECIES_DOG, Pet.SPECIES_CAT])

                if species == Pet.SPECIES_DOG:
                    available_names = [n for n in dog_names if n not in used_names]
                    if not available_names:
                        # If all names are used, generate a unique one
                        name = f"{random.choice(dog_names)}{i+1}"
                    else:
                        name = random.choice(available_names)
                    breed = random.choice(dog_breeds)
                else:
                    available_names = [n for n in cat_names if n not in used_names]
                    if not available_names:
                        # If all names are used, generate a unique one
                        name = f"{random.choice(cat_names)}{i+1}"
                    else:
                        name = random.choice(available_names)
                    breed = random.choice(cat_breeds)

                used_names.add(name)

                # Random birth date (1 month to 15 years old)
                age_days = random.randint(30, 5475)  # 1 month to 15 years
                birth_date = timezone.now().date() - timedelta(days=age_days)

                pet = Pet.objects.create(
                    owner=owner,
                    name=name,
                    species=species,
                    breed=breed,
                    birth_date=birth_date,
                    weight_kg=Decimal(str(random.uniform(2.0, 40.0))).quantize(
                        Decimal("0.01")
                    ),
                    gender=random.choice([Pet.GENDER_MALE, Pet.GENDER_FEMALE]),
                    color=random.choice(pet_colors),
                    is_active=True,
                    notes=fake.sentence() if random.random() > 0.7 else "",
                )

                pets.append(pet)

        return pets

    def _create_appointments(self, pets, staff_users):
        """Create 100+ appointments with mixed types and statuses."""
        appointments = []
        num_appointments = random.randint(100, 150)

        # Generate appointments over the past 60 days and next 30 days
        start_date = timezone.now().date() - timedelta(days=60)
        end_date = timezone.now().date() + timedelta(days=30)

        appointment_times = [
            time(9, 0),
            time(10, 0),
            time(11, 0),
            time(13, 0),
            time(14, 0),
            time(15, 0),
            time(16, 0),
        ]

        reasons = [
            "Routine checkup",
            "Vaccination",
            "Follow-up visit",
            "Skin issues",
            "Vomiting and diarrhea",
            "Loss of appetite",
            "Wound check",
            "Dental cleaning",
            "Ear infection",
            "Limping",
            "Behavior concerns",
            "Senior wellness exam",
        ]

        attempts = 0
        max_attempts = num_appointments * 3  # Allow more attempts for conflicts

        while len(appointments) < num_appointments and attempts < max_attempts:
            attempts += 1
            
            pet = random.choice(pets)
            appointment_date = fake.date_between(start_date=start_date, end_date=end_date)
            start_time = random.choice(appointment_times)

            # Determine appointment type
            appointment_type = random.choice(
                [Appointment.TYPE_SCHEDULED] * 7 + [Appointment.TYPE_WALK_IN] * 3
            )

            # Determine status based on date
            if appointment_date < timezone.now().date():
                # Past appointments
                status = random.choice(
                    [Appointment.STATUS_COMPLETED] * 7
                    + [Appointment.STATUS_NO_SHOW] * 2
                    + [Appointment.STATUS_CANCELLED] * 1
                )
            elif appointment_date == timezone.now().date():
                # Today's appointments
                status = random.choice(
                    [Appointment.STATUS_CONFIRMED] * 4
                    + [Appointment.STATUS_COMPLETED] * 2
                )
            else:
                # Future appointments
                status = random.choice(
                    [Appointment.STATUS_CONFIRMED] * 6
                    + [Appointment.STATUS_PENDING] * 3
                    + [Appointment.STATUS_CANCELLED] * 1
                )

            # Slot number (only for non-cancelled/rejected)
            slot_number = None if status in [
                Appointment.STATUS_CANCELLED,
                Appointment.STATUS_REJECTED,
            ] else random.randint(1, 2)

            try:
                from django.db import transaction
                with transaction.atomic():
                    appointment = Appointment.objects.create(
                        owner=pet.owner,
                        pet=pet,
                        staff=random.choice(staff_users) if appointment_type == Appointment.TYPE_WALK_IN else None,
                        appointment_date=appointment_date,
                        start_time=start_time,
                        end_time=(
                            datetime.combine(appointment_date, start_time)
                            + timedelta(minutes=30)
                        ).time(),
                        slot_number=slot_number,
                        status=status,
                        appointment_type=appointment_type,
                        reason=random.choice(reasons),
                        notes=fake.sentence() if random.random() > 0.6 else "",
                    )
                    appointments.append(appointment)
            except Exception as e:
                # Skip if unique constraint is violated (duplicate slot)
                continue

        return appointments

    def _create_medical_records(self, appointments, staff_users):
        """Create medical records for completed appointments."""
        medical_records = []

        completed_appointments = [
            apt for apt in appointments if apt.status == Appointment.STATUS_COMPLETED
        ]

        diagnoses = [
            "Healthy - routine checkup",
            "Skin dermatitis",
            "Gastroenteritis",
            "Ear infection (Otitis externa)",
            "Upper respiratory infection",
            "Dental disease",
            "Arthritis",
            "Obesity",
            "Allergic reaction",
            "Minor wound - cleaned and dressed",
            "Parasitic infection",
            "Healthy - vaccination only",
        ]

        treatments = [
            "Prescribed antibiotics (Amoxicillin 250mg, 2x daily for 7 days)",
            "Prescribed anti-inflammatory medication",
            "Topical ointment applied",
            "Advised special diet and monitor for 1 week",
            "Ear cleaning performed, prescribed ear drops",
            "Dental scaling performed",
            "Pain management medication prescribed",
            "Weight management plan discussed",
            "Antihistamine prescribed",
            "Wound cleaned and bandaged, recheck in 3 days",
            "Deworming medication administered",
            "Vaccination administered",
        ]

        for appointment in completed_appointments:
            # 80% of completed appointments get medical records
            if random.random() < 0.8:
                diagnosis = random.choice(diagnoses)
                treatment = random.choice(treatments)

                # Some appointments may have follow-up
                follow_up_date = None
                follow_up_reason = ""
                if random.random() < 0.3:  # 30% need follow-up
                    follow_up_date = appointment.appointment_date + timedelta(
                        days=random.randint(7, 30)
                    )
                    follow_up_reason = "Monitor treatment progress"

                medical_record = MedicalRecord.objects.create(
                    pet=appointment.pet,
                    appointment=appointment,
                    created_by=random.choice(staff_users),
                    visit_date=appointment.appointment_date,
                    chief_complaint=appointment.reason,
                    consultation_notes=fake.paragraph(nb_sentences=3),
                    diagnosis=diagnosis,
                    treatment=treatment,
                    prescription=treatment if "prescribed" in treatment.lower() else "",
                    follow_up_date=follow_up_date,
                    follow_up_reason=follow_up_reason,
                )

                medical_records.append(medical_record)

        return medical_records

    def _create_vaccination_records(self, medical_records, vaccine_types, staff_users):
        """Create vaccination records for some medical records."""
        vaccination_records = []

        for medical_record in medical_records:
            # 40% of medical records include vaccinations
            if random.random() < 0.4:
                # Get appropriate vaccines for the pet's species
                species_vaccines = [
                    v for v in vaccine_types if v.species == medical_record.pet.species
                ]

                if species_vaccines:
                    # Choose 1-2 vaccines
                    num_vaccines = random.randint(1, min(2, len(species_vaccines)))
                    vaccines_to_give = random.sample(species_vaccines, num_vaccines)

                    for vaccine_type in vaccines_to_give:
                        vaccination = VaccinationRecord.objects.create(
                            pet=medical_record.pet,
                            medical_record=medical_record,
                            vaccine_name=vaccine_type.name,
                            vaccine_type=vaccine_type,
                            date_administered=medical_record.visit_date,
                            batch_number=f"BATCH-{fake.bothify(text='???-####')}",
                            administered_by=random.choice(staff_users),
                            notes="Administered without complications",
                        )
                        vaccination_records.append(vaccination)

        return vaccination_records

    def _create_billing_records(self, appointments, staff_users):
        """Create billing records and payments for completed appointments."""
        billing_records = []

        completed_appointments = [
            apt for apt in appointments if apt.status == Appointment.STATUS_COMPLETED
        ]

        for appointment in completed_appointments:
            # Create billing record
            billing_record = BillingRecord.objects.create(
                appointment=appointment,
                owner=appointment.owner,
                pet=appointment.pet,
                created_by=random.choice(staff_users),
            )

            # Add checkup fee
            BillingLineItem.objects.create(
                billing_record=billing_record,
                description="Consultation/Checkup Fee",
                quantity=1,
                unit_price=Decimal("300.00"),
            )

            # Add vaccination charges if pet has vaccinations on this date
            vaccinations = VaccinationRecord.objects.filter(
                pet=appointment.pet, date_administered=appointment.appointment_date
            )

            for vaccination in vaccinations:
                vaccine_price = Decimal(str(random.uniform(500.0, 1200.0))).quantize(
                    Decimal("0.01")
                )
                BillingLineItem.objects.create(
                    billing_record=billing_record,
                    description=f"Vaccination - {vaccination.vaccine_name}",
                    quantity=1,
                    unit_price=vaccine_price,
                )

            # Recalculate totals
            billing_record.recalculate()

            # Create payments with mixed statuses
            payment_scenario = random.choices(
                ["paid", "partial", "unpaid"],
                weights=[7, 2, 1],  # 70% paid, 20% partial, 10% unpaid
            )[0]

            if payment_scenario == "paid":
                # Full payment
                Payment.objects.create(
                    billing_record=billing_record,
                    amount=billing_record.total_amount,
                    method=random.choice([Payment.METHOD_CASH, Payment.METHOD_EWALLET]),
                    reference=fake.bothify(text="REF-###-??????") if random.random() > 0.5 else "",
                    recorded_by=random.choice(staff_users),
                )
            elif payment_scenario == "partial":
                # Partial payment (50-90% of total)
                partial_amount = billing_record.total_amount * Decimal(
                    str(random.uniform(0.5, 0.9))
                )
                partial_amount = partial_amount.quantize(Decimal("0.01"))

                Payment.objects.create(
                    billing_record=billing_record,
                    amount=partial_amount,
                    method=random.choice([Payment.METHOD_CASH, Payment.METHOD_EWALLET]),
                    reference=fake.bothify(text="REF-###-??????") if random.random() > 0.5 else "",
                    recorded_by=random.choice(staff_users),
                )
            # else: unpaid - no payment records

            # Recalculate after adding payments
            billing_record.recalculate()
            billing_records.append(billing_record)

        return billing_records

    def _print_summary(self, pet_owners, pets, appointments):
        """Print summary of seeded data."""
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS("Database seeding completed successfully!"))
        self.stdout.write("=" * 60)
        self.stdout.write(f"Pet Owners (Clients): {len(pet_owners)}")
        self.stdout.write(f"Pets: {len(pets)}")
        self.stdout.write(f"Appointments: {len(appointments)}")
        self.stdout.write(
            f"  - Completed: {len([a for a in appointments if a.status == Appointment.STATUS_COMPLETED])}"
        )
        self.stdout.write(
            f"  - Confirmed: {len([a for a in appointments if a.status == Appointment.STATUS_CONFIRMED])}"
        )
        self.stdout.write(
            f"  - Pending: {len([a for a in appointments if a.status == Appointment.STATUS_PENDING])}"
        )
        self.stdout.write(
            f"  - Cancelled: {len([a for a in appointments if a.status == Appointment.STATUS_CANCELLED])}"
        )
        self.stdout.write(
            f"  - No Show: {len([a for a in appointments if a.status == Appointment.STATUS_NO_SHOW])}"
        )
        self.stdout.write(f"Medical Records: {MedicalRecord.objects.count()}")
        self.stdout.write(f"Vaccination Records: {VaccinationRecord.objects.count()}")
        self.stdout.write(f"Billing Records: {BillingRecord.objects.count()}")
        self.stdout.write(f"Payments: {Payment.objects.count()}")
        self.stdout.write(f"Vaccine Types: {VaccineType.objects.count()}")
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(
            self.style.SUCCESS("Test data is ready for dashboard, reports, and billing workflows!")
        )
        self.stdout.write("=" * 60)
        self.stdout.write("\nDefault credentials for testing:")
        self.stdout.write("  Manager: username='manager', password='password123'")
        self.stdout.write("  Staff: username='staff1-3', password='password123'")
        self.stdout.write("  Pet Owners: password='password123' for all generated users")
        self.stdout.write("=" * 60 + "\n")
