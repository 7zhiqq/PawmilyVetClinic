from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from appointments.models import Appointment
from website.notifications import (
    notify_appointment_reminder_24h,
    notify_same_day_queue_update,
)


class Command(BaseCommand):
    help = "Send automated appointment reminders (24h) and same-day queue updates for pet owners"

    def handle(self, *args, **options):
        today = timezone.localdate()
        tomorrow = today + timedelta(days=1)

        reminder_qs = Appointment.objects.select_related("owner", "pet").filter(
            appointment_date=tomorrow,
            status=Appointment.STATUS_CONFIRMED,
            owner__profile__role="pet_owner",
        )

        reminder_count = 0
        for appointment in reminder_qs:
            notify_appointment_reminder_24h(appointment)
            reminder_count += 1

        today_confirmed = list(
            Appointment.objects.select_related("owner", "pet").filter(
                appointment_date=today,
                status=Appointment.STATUS_CONFIRMED,
                owner__profile__role="pet_owner",
            ).order_by("start_time", "slot_number")
        )

        served_count = Appointment.objects.filter(
            appointment_date=today,
            status__in=[Appointment.STATUS_COMPLETED, Appointment.STATUS_NO_SHOW],
        ).count()

        queue_count = 0
        current_serving = served_count + 1 if today_confirmed else served_count

        for idx, appointment in enumerate(today_confirmed):
            queue_position = served_count + idx + 1
            notify_same_day_queue_update(
                appointment,
                queue_position=queue_position,
                current_serving_number=current_serving,
            )
            queue_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Sent/updated {reminder_count} 24-hour reminders and {queue_count} same-day queue notifications."
            )
        )
