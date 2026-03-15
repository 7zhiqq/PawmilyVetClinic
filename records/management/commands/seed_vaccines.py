"""
Management command to seed common vaccine types to the database.
Run with: python manage.py seed_vaccines
"""

from django.core.management.base import BaseCommand
from django.db import IntegrityError
from django.db.models import Q
from records.models import VaccineType


class Command(BaseCommand):
    help = "Seed common vaccine types for dogs and cats"

    def handle(self, *args, **options):
        standardized_vaccines = [
            {
                "name": "5-in-1 Vaccine",
                "species": "dog",
                "booster_interval_days": 365,
                "unit_price": "850.00",
                "description": "Core puppy/annual canine vaccine: Distemper, Adenovirus/Hepatitis, Parvovirus, Parainfluenza, Leptospirosis.",
            },
            {
                "name": "Rabies Vaccine",
                "species": "dog",
                "booster_interval_days": 365,
                "unit_price": "450.00",
                "description": "First dose at 12 weeks, then annual booster.",
            },
            {
                "name": "Kennel Cough (Bordetella)",
                "species": "dog",
                "booster_interval_days": 365,
                "unit_price": "650.00",
                "description": "First dose at 8 to 12 weeks, then annual booster.",
            },
            {
                "name": "Coronavirus",
                "species": "dog",
                "booster_interval_days": 365,
                "unit_price": "600.00",
                "description": "Optional canine coronavirus schedule with primary puppy series and annual booster.",
            },
            {
                "name": "Deworming",
                "species": "dog",
                "booster_interval_days": 90,
                "unit_price": "250.00",
                "description": "Deworming at 2, 4, 6, 8, 10, 12 weeks then every 3 months.",
            },
            {
                "name": "Tick & Flea Prevention",
                "species": "dog",
                "booster_interval_days": 30,
                "unit_price": "300.00",
                "description": "Start at 6 to 8 weeks then monthly preventive treatment.",
            },
            {
                "name": "FVRCP Vaccine",
                "species": "cat",
                "booster_interval_days": 365,
                "unit_price": "800.00",
                "description": "Core feline vaccine at 6 to 8 weeks, 10 to 12 weeks, 14 to 16 weeks, then annual booster.",
            },
            {
                "name": "Rabies Vaccine",
                "species": "cat",
                "booster_interval_days": 365,
                "unit_price": "450.00",
                "description": "First dose at 12 weeks, then annual booster.",
            },
            {
                "name": "Feline Leukemia (FeLV)",
                "species": "cat",
                "booster_interval_days": 365,
                "unit_price": "900.00",
                "description": "Primary dose at 8 to 12 weeks, second dose after 3 to 4 weeks, then annual booster.",
            },
            {
                "name": "Deworming",
                "species": "cat",
                "booster_interval_days": 90,
                "unit_price": "250.00",
                "description": "Deworming at 2, 4, 6, 8, 10, 12 weeks then every 3 months.",
            },
            {
                "name": "Tick & Flea Prevention",
                "species": "cat",
                "booster_interval_days": 30,
                "unit_price": "300.00",
                "description": "Start at 6 to 8 weeks then monthly preventive treatment.",
            },
        ]

        created_count = 0
        updated_count = 0
        active_pairs = set()
        
        for vaccine_data in standardized_vaccines:
            active_pairs.add((vaccine_data["name"], vaccine_data["species"]))
            defaults = {
                "booster_interval_days": vaccine_data["booster_interval_days"],
                "unit_price": vaccine_data["unit_price"],
                "description": vaccine_data["description"],
                "is_active": True,
            }
            vaccine = VaccineType.objects.filter(
                name=vaccine_data["name"],
                species=vaccine_data["species"],
            ).first()
            created = False
            if vaccine is None:
                try:
                    vaccine = VaccineType.objects.create(
                        name=vaccine_data["name"],
                        species=vaccine_data["species"],
                        **defaults,
                    )
                    created = True
                except IntegrityError:
                    vaccine = VaccineType.objects.filter(name=vaccine_data["name"]).first()

            if vaccine is None:
                continue

            updates = []
            for field, value in defaults.items():
                if getattr(vaccine, field) != value:
                    setattr(vaccine, field, value)
                    updates.append(field)
            if updates:
                vaccine.save(update_fields=updates)

            if created:
                created_count += 1
                self.stdout.write(f"✓ Created: {vaccine}")
            else:
                updated_count += 1
                self.stdout.write(f"→ Updated: {vaccine}")

        keep_filter = Q()
        for name, species in active_pairs:
            keep_filter |= Q(name=name, species=species)

        dog_cat_qs = VaccineType.objects.filter(species__in=["dog", "cat"])
        deactivated = dog_cat_qs.exclude(keep_filter).update(is_active=False)

        self.stdout.write(
            self.style.SUCCESS(
                f"\n✓ Vaccination setup complete: {created_count} created, {updated_count} updated, {deactivated} deactivated"
            )
        )
