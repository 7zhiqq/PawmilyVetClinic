from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

from .models import Appointment, Invitation, Pet, Profile


User = get_user_model()


def email_normalize(email):
    return (email or "").strip().lower()


class PetOwnerRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(required=True)
    last_name = forms.CharField(required=True)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("first_name", "last_name", "username", "email")

    def clean_email(self):
        email = self.cleaned_data["email"]
        normalized = email_normalize(email)
        if User.objects.filter(email__iexact=normalized).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email


class StaffInviteRegistrationForm(UserCreationForm):
    first_name = forms.CharField(required=True)
    last_name = forms.CharField(required=True)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("first_name", "last_name", "username")


class InvitationForm(forms.ModelForm):
    class Meta:
        model = Invitation
        fields = ["email", "role"]
        widgets = {
            "email": forms.EmailInput(attrs={"placeholder": "staff@example.com"}),
        }

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if not email:
            return email
        normalized = email_normalize(email)
        if User.objects.filter(email__iexact=normalized).exists():
            raise forms.ValidationError(
                "A user with this email already has an account. One email per user."
            )
        if Invitation.objects.filter(email__iexact=normalized, is_used=False).exists():
            raise forms.ValidationError(
                "A pending invitation for this email already exists."
            )
        return email


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ["phone", "address"]
        widgets = {
            "phone": forms.TextInput(attrs={"placeholder": "+63 912 345 6789"}),
            "address": forms.Textarea(attrs={"rows": 3, "placeholder": "Your address"}),
        }


class PetForm(forms.ModelForm):
    class Meta:
        model = Pet
        fields = ["name", "species", "breed", "gender", "birth_date", "weight_kg", "color", "notes"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Pet's name"}),
            "breed": forms.TextInput(attrs={"placeholder": "e.g. Golden Retriever"}),
            "birth_date": forms.DateInput(attrs={"type": "date"}),
            "weight_kg": forms.NumberInput(attrs={"step": "0.01", "placeholder": "0.00"}),
            "color": forms.TextInput(attrs={"placeholder": "e.g. Brown, Black and white"}),
            "notes": forms.Textarea(attrs={"rows": 2, "placeholder": "Medical notes, allergies, etc."}),
        }


class AppointmentBookingForm(forms.ModelForm):
    """Pet owner booking form."""

    class Meta:
        model = Appointment
        fields = ["pet", "appointment_date", "start_time", "reason"]
        widgets = {
            "appointment_date": forms.DateInput(attrs={"type": "date"}),
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "reason": forms.TextInput(attrs={"placeholder": "e.g. Vaccination, check-up"}),
        }

    def __init__(self, *args, owner=None, **kwargs):
        super().__init__(*args, **kwargs)
        if owner:
            self.fields["pet"].queryset = Pet.objects.filter(owner=owner).order_by("name")


class AppointmentStaffForm(forms.ModelForm):
    """Staff form for walk-ins and scheduling."""

    class Meta:
        model = Appointment
        fields = ["owner", "pet", "appointment_date", "start_time", "end_time", "appointment_type", "reason", "notes", "status"]
        widgets = {
            "appointment_date": forms.DateInput(attrs={"type": "date"}),
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "end_time": forms.TimeInput(attrs={"type": "time"}),
            "reason": forms.TextInput(attrs={"placeholder": "Reason for visit"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        pet_owners = User.objects.filter(profile__role=Profile.ROLE_PET_OWNER).order_by("username")
        self.fields["owner"].queryset = pet_owners