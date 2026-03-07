"""
Management command to update vaccination schedule statuses.
Run this daily via a scheduled task (cron, celery, etc.) to keep reminder statuses current.
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from records.models import VaccinationSchedule


class Command(BaseCommand):
    help = "Update vaccination schedule statuses based on due dates"

    def handle(self, *args, **options):
        today = timezone.now().date()
        updated_count = 0

        # Get all pending and due vaccines
        schedules = VaccinationSchedule.objects.exclude(
            status__in=[
                VaccinationSchedule.STATUS_COMPLETED,
                VaccinationSchedule.STATUS_SKIPPED,
            ]
        )

        for schedule in schedules:
            old_status = schedule.status
            
            # Calculate new status based on current date
            if schedule.next_due_date <= today:
                schedule.status = VaccinationSchedule.STATUS_OVERDUE
            elif (schedule.next_due_date - today).days <= 14:  # Due within 2 weeks
                schedule.status = VaccinationSchedule.STATUS_DUE
            else:
                schedule.status = VaccinationSchedule.STATUS_PENDING
            
            if schedule.status != old_status:
                schedule.save(update_fields=["status", "updated_at"])
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"✓ Updated {updated_count} vaccination schedule statuses"
            )
        )
