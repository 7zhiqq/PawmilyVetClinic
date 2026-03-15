from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.crypto import get_random_string

from pawmily.file_handling import PET_PROFILE_PICTURE_UPLOAD_TO


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
    profile_picture = models.ImageField(
        upload_to=PET_PROFILE_PICTURE_UPLOAD_TO, null=True, blank=True
    )
    is_active = models.BooleanField(default=True)
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
