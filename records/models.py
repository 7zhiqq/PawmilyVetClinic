from django.conf import settings
from django.db import models
from django.utils import timezone


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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "accounts_medicalrecord"
        ordering = ["-visit_date", "-created_at"]

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

    def __str__(self) -> str:
        return f"{self.pet.name} – {self.vaccine_name} ({self.date_administered})"


class MedicalAttachment(models.Model):
    """File attachments linked to a medical record (lab results, X-rays, etc.)."""

    medical_record = models.ForeignKey(
        MedicalRecord,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    file = models.FileField(upload_to="medical_attachments/%Y/%m/")
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
        import os
        return os.path.basename(self.file.name)

    def __str__(self) -> str:
        return self.description or self.filename()
