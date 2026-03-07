"""
Management command to update follow-up reminder statuses.
Run this daily via a scheduled task (cron, celery, etc.) to keep reminder statuses current.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from records.models import FollowUpReminder


class Command(BaseCommand):
    help = "Update follow-up reminder statuses based on due dates"

    def handle(self, *args, **options):
        today = timezone.now().date()
        updated_count = 0

        # Get all pending, due, and overdue follow-ups
        reminders = FollowUpReminder.objects.exclude(
            status__in=[
                FollowUpReminder.STATUS_COMPLETED,
                FollowUpReminder.STATUS_CANCELLED,
            ]
        )

        for reminder in reminders:
            old_status = reminder.status
            
            # Calculate new status based on current date
            if reminder.follow_up_date <= today:
                reminder.status = FollowUpReminder.STATUS_OVERDUE
            elif (reminder.follow_up_date - today).days <= 7:  # Due within 1 week
                reminder.status = FollowUpReminder.STATUS_DUE
            else:
                reminder.status = FollowUpReminder.STATUS_PENDING
            
            if reminder.status != old_status:
                reminder.save(update_fields=["status", "updated_at"])
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"✓ Updated {updated_count} follow-up reminder statuses"
            )
        )
