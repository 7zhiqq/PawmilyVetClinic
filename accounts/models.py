from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils.crypto import get_random_string


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

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_CONFIRMED, "Confirmed"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_CANCELLED, "Cancelled"),
        (STATUS_COMPLETED, "Completed"),
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
        ordering = ["appointment_date", "start_time"]

    def __str__(self) -> str:
        pet_name = self.pet.name if self.pet else "Walk-in"
        return f"{pet_name} on {self.appointment_date} at {self.start_time} ({self.get_status_display()})"

