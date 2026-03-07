"""
Management command to seed common vaccine types to the database.
Run with: python manage.py seed_vaccines
"""

from django.core.management.base import BaseCommand
from records.models import VaccineType


class Command(BaseCommand):
    help = "Seed common vaccine types for dogs and cats"

    def handle(self, *args, **options):
        # Common dog vaccines
        dog_vaccines = [
            {
                "name": "DHPP (5-in-1)",
                "species": "dog",
                "booster_interval_days": 365,
                "description": "Distemper, Hepatitis, Parvovirus, Parainfluenza. Core vaccine for all dogs."
            },
            {
                "name": "Rabies (Dog)",
                "species": "dog",
                "booster_interval_days": 730,
                "description": "Required by law in most jurisdictions. Typically given annually initially, then every 3 years."
            },
            {
                "name": "Bordetella",
                "species": "dog",
                "booster_interval_days": 365,
                "description": "Kennel cough vaccine. Recommended for dogs in social/boarding situations."
            },
            {
                "name": "Leptospirosis",
                "species": "dog",
                "booster_interval_days": 365,
                "description": "Protects against leptospira bacteria. Recommended for outdoor dogs."
            },
            {
                "name": "Lyme Disease",
                "species": "dog",
                "booster_interval_days": 365,
                "description": "For dogs in tick-endemic areas. Protects against Borrelia burgdorferi."
            },
            {
                "name": "Influenza (H3N2)",
                "species": "dog",
                "booster_interval_days": 365,
                "description": "Canine influenza vaccine. Recommended for dogs with high exposure risk."
            },
        ]

        # Common cat vaccines
        cat_vaccines = [
            {
                "name": "FVRCP",
                "species": "cat",
                "booster_interval_days": 365,
                "description": "Feline Viral Rhinotracheitis, Calicivirus, Panleukopenia. Core vaccine for all cats."
            },
            {
                "name": "Rabies (Cat)",
                "species": "cat",
                "booster_interval_days": 730,
                "description": "Required by law in most jurisdictions. Typically given annually initially, then every 3 years."
            },
            {
                "name": "FeLV (Feline Leukemia)",
                "species": "cat",
                "booster_interval_days": 365,
                "description": "Recommended for outdoor cats or cats using shared equipment. Currently no vaccine for FIV."
            },
            {
                "name": "Chlamydia",
                "species": "cat",
                "booster_interval_days": 365,
                "description": "Optional vaccine for cats with history of upper respiratory infections."
            },
        ]

        created_count = 0
        
        for vaccine_data in dog_vaccines + cat_vaccines:
            vaccine, created = VaccineType.objects.get_or_create(
                name=vaccine_data["name"],
                species=vaccine_data["species"],
                defaults={
                    "booster_interval_days": vaccine_data["booster_interval_days"],
                    "description": vaccine_data["description"],
                    "is_active": True,
                }
            )
            if created:
                created_count += 1
                self.stdout.write(f"✓ Created: {vaccine}")
            else:
                self.stdout.write(f"→ Already exists: {vaccine}")

        self.stdout.write(
            self.style.SUCCESS(
                f"\n✓ Vaccination setup complete: {created_count} new vaccines added"
            )
        )
