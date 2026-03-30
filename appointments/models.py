from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

MAX_SLOTS = 2


class Appointment(models.Model):
    STATUS_PENDING = "pending"
    STATUS_CONFIRMED = "confirmed"
    STATUS_REJECTED = "rejected"
    STATUS_CANCELLED = "cancelled"
    STATUS_COMPLETED = "completed"
    STATUS_NO_SHOW = "no_show"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_CONFIRMED, "Confirmed"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_CANCELLED, "Cancelled"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_NO_SHOW, "No Show"),
    ]

    TYPE_SCHEDULED = "scheduled"
    TYPE_WALK_IN = "walk_in"

    TYPE_CHOICES = [
        (TYPE_SCHEDULED, "Scheduled"),
        (TYPE_WALK_IN, "Walk-in"),
    ]

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="appointments",
        help_text="Pet owner who booked the appointment",
    )
    pet = models.ForeignKey(
        "accounts.Pet",
        on_delete=models.CASCADE,
        related_name="appointments",
        null=True,
        blank=True,
        help_text="Pet (optional for walk-ins)",
    )
    staff = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="managed_appointments",
        help_text="Staff who created/confirmed (for walk-ins)",
    )
    appointment_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField(null=True, blank=True)
    slot_number = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        default=1,
        help_text="Slot position (1–2) within a date/time block. NULL for cancelled/rejected.",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    appointment_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default=TYPE_SCHEDULED,
    )
    reason = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "accounts_appointment"
        ordering = ["appointment_date", "start_time", "slot_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["appointment_date", "start_time", "slot_number", "appointment_type"],
                name="unique_active_slot_per_datetime_and_type",
            ),
        ]

    def clean(self):
        if (
            self.appointment_type == self.TYPE_SCHEDULED
            and self.slot_number is not None
            and not (1 <= self.slot_number <= MAX_SLOTS)
        ):
            raise ValidationError(
                {"slot_number": f"Slot number must be between 1 and {MAX_SLOTS}."}
            )
        if self.status in (self.STATUS_CANCELLED, self.STATUS_REJECTED):
            self.slot_number = None
        
        # Check for duplicate pet bookings at the same date/time
        if self.pet and self.appointment_date and self.start_time:
            duplicate_query = Appointment.objects.filter(
                pet=self.pet,
                appointment_date=self.appointment_date,
                start_time=self.start_time,
            ).exclude(
                status__in=[self.STATUS_CANCELLED, self.STATUS_REJECTED]
            )
            # Exclude current appointment if updating
            if self.pk:
                duplicate_query = duplicate_query.exclude(pk=self.pk)
            
            if duplicate_query.exists():
                raise ValidationError(
                    "This pet already has an appointment scheduled for this date and time."
                )

    def __str__(self) -> str:
        pet_name = self.pet.name if self.pet else "Walk-in"
        return (
            f"{pet_name} on {self.appointment_date} at {self.start_time} "
            f"slot {self.slot_number} ({self.get_status_display()})"
        )
