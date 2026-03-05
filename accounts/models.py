from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.crypto import get_random_string

MAX_SLOTS = 2


class Profile(models.Model):
    ROLE_PET_OWNER = "pet_owner"
    ROLE_STAFF = "staff"
    ROLE_MANAGER = "manager"

    ROLE_CHOICES = [
        (ROLE_PET_OWNER, "Pet owner"),
        (ROLE_STAFF, "Staff"),
        (ROLE_MANAGER, "Manager"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=ROLE_PET_OWNER,
    )
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    date_created = models.DateTimeField(default=timezone.now)
    is_profile_completed = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.user.username} ({self.get_role_display()})"


class Pet(models.Model):
    SPECIES_DOG = "dog"
    SPECIES_CAT = "cat"
    SPECIES_BIRD = "bird"
    SPECIES_OTHER = "other"

    SPECIES_CHOICES = [
        (SPECIES_DOG, "Dog"),
        (SPECIES_CAT, "Cat"),
        (SPECIES_BIRD, "Bird"),
        (SPECIES_OTHER, "Other"),
    ]

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="pets",
    )
    name = models.CharField(max_length=100)
    species = models.CharField(max_length=20, choices=SPECIES_CHOICES)
    breed = models.CharField(max_length=100, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    weight_kg = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )
    GENDER_MALE = "male"
    GENDER_FEMALE = "female"
    GENDER_UNKNOWN = "unknown"

    GENDER_CHOICES = [
        (GENDER_MALE, "Male"),
        (GENDER_FEMALE, "Female"),
        (GENDER_UNKNOWN, "Unknown"),
    ]

    gender = models.CharField(
        max_length=20, choices=GENDER_CHOICES, default=GENDER_UNKNOWN, blank=True
    )
    color = models.CharField(max_length=50, blank=True, default='')
    
    is_active = models.BooleanField(default=True)
    profile_picture = models.ImageField(upload_to='pet_pictures/', blank=True, null=True, default=None)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.name} ({self.get_species_display()})"


class Invitation(models.Model):
    ROLE_STAFF = Profile.ROLE_STAFF
    ROLE_MANAGER = Profile.ROLE_MANAGER

    ROLE_CHOICES = [
        (ROLE_STAFF, "Staff"),
        (ROLE_MANAGER, "Manager"),
    ]

    email = models.EmailField()
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    token = models.CharField(max_length=40, unique=True, editable=False)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["email"],
                condition=Q(is_used=False),
                name="unique_pending_invitation_per_email",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = get_random_string(32)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        status = "used" if self.is_used else "pending"
        return f"{self.email} ({self.get_role_display()}, {status})"


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
        Pet,
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
        ordering = ["appointment_date", "start_time", "slot_number"]
        constraints = [
            # Global 2-slot limit per time range: each (date, time, slot_number,
            # type) combination can only have ONE appointment across ALL owners.
            # Cancelled / rejected appointments have slot_number set to NULL,
            # which MySQL allows as duplicates in a UNIQUE index.
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
        # Cancelled / rejected appointments must have slot_number cleared.
        if self.status in (self.STATUS_CANCELLED, self.STATUS_REJECTED):
            self.slot_number = None

    def __str__(self) -> str:
        pet_name = self.pet.name if self.pet else "Walk-in"
        return (
            f"{pet_name} on {self.appointment_date} at {self.start_time} "
            f"slot {self.slot_number} ({self.get_status_display()})"
        )


class WalkInRegistration(models.Model):
    """
    Tracks walk-in clients registered by staff who haven't activated
    their online account yet.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="walkin_registration",
    )
    token = models.CharField(max_length=64, unique=True, editable=False)
    is_activated = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="walkin_registrations_created",
        help_text="Staff member who registered this client",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    activated_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = get_random_string(48)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        status = "activated" if self.is_activated else "pending"
        return f"{self.user.get_full_name() or self.user.username} ({status})"


# ─── Medical Records ─────────────────────────────────────────────────────────


class MedicalRecord(models.Model):
    """A single consultation / visit record for a pet."""

    pet = models.ForeignKey(
        Pet,
        on_delete=models.CASCADE,
        related_name="medical_records",
    )
    appointment = models.ForeignKey(
        Appointment,
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
        ordering = ["-visit_date", "-created_at"]

    def __str__(self) -> str:
        return f"{self.pet.name} – {self.visit_date}"


class VaccinationRecord(models.Model):
    """Tracks individual vaccinations for a pet."""

    pet = models.ForeignKey(
        Pet,
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

    def filename(self):
        import os
        return os.path.basename(self.file.name)

    def __str__(self) -> str:
        return self.description or self.filename()