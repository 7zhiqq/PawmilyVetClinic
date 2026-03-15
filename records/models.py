from django.conf import settings
from django.db import models
from django.utils import timezone
from datetime import timedelta

from pawmily.file_handling import (
    MEDICAL_ATTACHMENT_UPLOAD_TO,
    uploaded_basename,
)


class VaccineType(models.Model):
    """Master list of vaccines with their recommended booster intervals."""

    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Vaccine name (e.g., Rabies, DHPP, FeLV)"
    )
    species = models.CharField(
        max_length=20,
        choices=[
            ("dog", "Dog"),
            ("cat", "Cat"),
            ("bird", "Bird"),
            ("other", "Other"),
        ],
        help_text="Species this vaccine applies to"
    )
    booster_interval_days = models.PositiveIntegerField(
        default=365,
        help_text="Days between booster vaccinations (e.g., 365 for annual)"
    )
    description = models.TextField(
        blank=True,
        help_text="Additional information about the vaccine"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "records_vaccinetype"
        ordering = ["species", "name"]
        unique_together = [["name", "species"]]

    def __str__(self) -> str:
        return f"{self.name} ({self.get_species_display()})"


class MedicalRecord(models.Model):
    """A single consultation / visit record for a pet."""

    pet = models.ForeignKey(
        "accounts.Pet",
        on_delete=models.CASCADE,
        related_name="medical_records",
    )
    appointment = models.ForeignKey(
        "appointments.Appointment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="medical_records",
        help_text="Linked appointment (optional)",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="medical_records_created",
    )
    visit_date = models.DateField(default=timezone.now)
    chief_complaint = models.CharField(max_length=255, blank=True)
    consultation_notes = models.TextField(blank=True)
    diagnosis = models.TextField(blank=True)
    treatment = models.TextField(blank=True)
    prescription = models.TextField(
        blank=True,
        help_text="Medications prescribed, dosage, frequency",
    )
    follow_up_date = models.DateField(null=True, blank=True)
    follow_up_reason = models.CharField(
        max_length=255,
        blank=True,
        help_text="Reason for follow-up visit"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "accounts_medicalrecord"
        ordering = ["-visit_date", "-created_at"]

    def save(self, *args, **kwargs):
        """Auto-create FollowUpReminder when follow_up_date is set."""
        super().save(*args, **kwargs)
        
        # Create or update FollowUpReminder if follow_up_date is set
        if self.follow_up_date:
            self._update_followup_reminder()

    def _update_followup_reminder(self):
        """Create or update FollowUpReminder for this medical record."""
        from django.utils import timezone as tz
        today = tz.now().date()
        
        # Determine status based on follow_up_date
        if self.follow_up_date <= today:
            status = FollowUpReminder.STATUS_OVERDUE
        elif (self.follow_up_date - today).days <= 7:  # Due within 1 week
            status = FollowUpReminder.STATUS_DUE
        else:
            status = FollowUpReminder.STATUS_PENDING
        
        reminder, created = FollowUpReminder.objects.update_or_create(
            medical_record=self,
            defaults={
                "pet": self.pet,
                "follow_up_date": self.follow_up_date,
                "reason": self.follow_up_reason or f"Follow-up from {self.visit_date}",
                "status": status,
            }
        )

    def __str__(self) -> str:
        return f"{self.pet.name} – {self.visit_date}"


class VaccinationRecord(models.Model):
    """Tracks individual vaccinations for a pet."""

    pet = models.ForeignKey(
        "accounts.Pet",
        on_delete=models.CASCADE,
        related_name="vaccinations",
    )
    medical_record = models.ForeignKey(
        MedicalRecord,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vaccinations",
    )
    vaccine_name = models.CharField(max_length=150)
    vaccine_type = models.ForeignKey(
        VaccineType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vaccination_records",
        help_text="Link to vaccine type for automatic booster calculation"
    )
    date_administered = models.DateField(default=timezone.now)
    next_due_date = models.DateField(null=True, blank=True)
    batch_number = models.CharField(max_length=100, blank=True)
    administered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vaccinations_administered",
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "accounts_vaccinationrecord"
        ordering = ["-date_administered"]

    def save(self, *args, **kwargs):
        """Auto-calculate next_due_date based on vaccine_type if not manually set."""
        # If vaccine_type is set and next_due_date is not manually provided
        if self.vaccine_type and not self.next_due_date:
            self.next_due_date = self.date_administered + timedelta(
                days=self.vaccine_type.booster_interval_days
            )
        super().save(*args, **kwargs)
        
        # After saving, create or update VaccinationSchedule
        self._update_vaccination_schedule()

    def _update_vaccination_schedule(self):
        """Create or update the VaccinationSchedule for this vaccination."""
        if self.next_due_date:
            from django.utils import timezone as tz
            today = tz.now().date()
            
            # Determine status based on next_due_date
            if self.next_due_date <= today:
                status = VaccinationSchedule.STATUS_OVERDUE
            elif (self.next_due_date - today).days <= 14:  # Due within 2 weeks
                status = VaccinationSchedule.STATUS_DUE
            else:
                status = VaccinationSchedule.STATUS_PENDING
            
            schedule, created = VaccinationSchedule.objects.update_or_create(
                vaccination_record=self,
                defaults={
                    "pet": self.pet,
                    "vaccine_type": self.vaccine_type,
                    "next_due_date": self.next_due_date,
                    "status": status,
                }
            )

    def __str__(self) -> str:
        return f"{self.pet.name} – {self.vaccine_name} ({self.date_administered})"


class MedicalAttachment(models.Model):
    """File attachments linked to a medical record (lab results, X-rays, etc.)."""

    medical_record = models.ForeignKey(
        MedicalRecord,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    file = models.FileField(upload_to=MEDICAL_ATTACHMENT_UPLOAD_TO)
    description = models.CharField(max_length=255, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "accounts_medicalattachment"

    def filename(self):
        return uploaded_basename(self.file.name)

    def __str__(self) -> str:
        return self.description or self.filename()


class VaccinationSchedule(models.Model):
    """Tracks scheduled booster vaccinations with reminder status."""

    STATUS_PENDING = "pending"
    STATUS_DUE = "due"
    STATUS_OVERDUE = "overdue"
    STATUS_COMPLETED = "completed"
    STATUS_SKIPPED = "skipped"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_DUE, "Due Soon"),
        (STATUS_OVERDUE, "Overdue"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_SKIPPED, "Skipped"),
    ]

    pet = models.ForeignKey(
        "accounts.Pet",
        on_delete=models.CASCADE,
        related_name="vaccination_schedules",
    )
    vaccination_record = models.ForeignKey(
        VaccinationRecord,
        on_delete=models.CASCADE,
        related_name="schedules",
        help_text="The vaccination record this schedule is based on"
    )
    vaccine_type = models.ForeignKey(
        VaccineType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="schedules",
    )
    next_due_date = models.DateField(
        help_text="When the next booster vaccination is due"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    reminder_sent = models.BooleanField(
        default=False,
        help_text="Whether a reminder notification has been sent"
    )
    reminder_sent_date = models.DateTimeField(null=True, blank=True)
    completed_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "records_vaccinationschedule"
        ordering = ["next_due_date", "-created_at"]

    def is_overdue(self) -> bool:
        """Check if vaccination is overdue."""
        from django.utils import timezone
        return self.next_due_date < timezone.now().date() and self.status != self.STATUS_COMPLETED

    def days_until_due(self) -> int:
        """Return number of days until due (negative if overdue)."""
        from django.utils import timezone
        delta = self.next_due_date - timezone.now().date()
        return delta.days

    def __str__(self) -> str:
        return f"{self.pet.name} – {self.vaccine_type.name if self.vaccine_type else 'Unknown'} (Due: {self.next_due_date})"


class FollowUpReminder(models.Model):
    """Tracks follow-up consultations scheduled from medical records."""

    STATUS_PENDING = "pending"
    STATUS_DUE = "due"
    STATUS_OVERDUE = "overdue"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_DUE, "Due Soon"),
        (STATUS_OVERDUE, "Overdue"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    pet = models.ForeignKey(
        "accounts.Pet",
        on_delete=models.CASCADE,
        related_name="followup_reminders",
    )
    medical_record = models.ForeignKey(
        MedicalRecord,
        on_delete=models.CASCADE,
        related_name="followup_reminders",
        help_text="The medical record that required follow-up"
    )
    follow_up_date = models.DateField(
        help_text="Scheduled follow-up date"
    )
    reason = models.CharField(
        max_length=255,
        help_text="Reason for follow-up (e.g., 'Monitor wound healing')"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    reminder_sent = models.BooleanField(
        default=False,
        help_text="Whether a reminder notification has been sent"
    )
    reminder_sent_date = models.DateTimeField(null=True, blank=True)
    completed_appointment = models.ForeignKey(
        "appointments.Appointment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="followup_reminders",
        help_text="Appointment where follow-up was completed"
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "records_followupreminder"
        ordering = ["follow_up_date", "-created_at"]

    def is_overdue(self) -> bool:
        """Check if follow-up is overdue."""
        from django.utils import timezone
        return self.follow_up_date < timezone.now().date() and self.status != self.STATUS_COMPLETED

    def days_until_due(self) -> int:
        """Return number of days until due (negative if overdue)."""
        from django.utils import timezone
        delta = self.follow_up_date - timezone.now().date()
        return delta.days

    def __str__(self) -> str:
        return f"{self.pet.name} – Follow-up ({self.follow_up_date}): {self.reason}"
