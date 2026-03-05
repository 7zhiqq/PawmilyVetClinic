from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

from .models import (
    Appointment, Invitation, MedicalAttachment, MedicalRecord, Pet, Profile,
    VaccinationRecord, WalkInRegistration,
)


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
        self.fields["status"].initial = Appointment.STATUS_CONFIRMED


class WalkInClientForm(forms.Form):
    """Staff form for registering a walk-in client (no online account yet)."""
    first_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={"placeholder": "First name"}))
    last_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={"placeholder": "Last name"}))
    email = forms.EmailField(required=False, widget=forms.EmailInput(attrs={"placeholder": "client@example.com (optional)"}))
    phone = forms.CharField(max_length=20, required=False, widget=forms.TextInput(attrs={"placeholder": "+63 912 345 6789"}))
    address = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2, "placeholder": "Client's address"}))

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if not email:
            return email
        normalized = email_normalize(email)
        if User.objects.filter(email__iexact=normalized).exists():
            raise forms.ValidationError(
                "An account with this email already exists. Use the existing client instead."
            )
        return email


class WalkInPetForm(forms.ModelForm):
    """Pet form used during walk-in registration (no owner set yet)."""
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


class WalkInActivationForm(UserCreationForm):
    """Form for a walk-in client to activate their online account."""
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username",)

    def clean_username(self):
        username = self.cleaned_data["username"]
        # Allow the client to keep the suggested username already reserved
        # on their own User record. Only reject if another user has it.
        qs = User.objects.filter(username=username)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(
                "A user with that username already exists."
            )
        return username


class WalkInLinkForm(forms.Form):
    """Form shown during pet-owner registration to link an existing walk-in record."""
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"placeholder": "Email used during walk-in registration"}),
        help_text="Enter the email the clinic used when registering you.",
    )


# ─── Medical Records ─────────────────────────────────────────────────────────


class MedicalRecordForm(forms.ModelForm):
    class Meta:
        model = MedicalRecord
        fields = [
            "visit_date", "chief_complaint", "consultation_notes",
            "diagnosis", "treatment", "prescription", "follow_up_date",
        ]
        widgets = {
            "visit_date": forms.DateInput(attrs={"type": "date"}),
            "chief_complaint": forms.TextInput(attrs={"placeholder": "e.g. Limping on right hind leg"}),
            "consultation_notes": forms.Textarea(attrs={"rows": 3, "placeholder": "Observations, history, examination findings…"}),
            "diagnosis": forms.Textarea(attrs={"rows": 2, "placeholder": "e.g. Mild dermatitis"}),
            "treatment": forms.Textarea(attrs={"rows": 2, "placeholder": "Treatment provided…"}),
            "prescription": forms.Textarea(attrs={"rows": 2, "placeholder": "Medications, dosage, frequency…"}),
            "follow_up_date": forms.DateInput(attrs={"type": "date"}),
        }


class VaccinationRecordForm(forms.ModelForm):
    class Meta:
        model = VaccinationRecord
        fields = [
            "vaccine_name", "date_administered", "next_due_date",
            "batch_number", "notes",
        ]
        widgets = {
            "vaccine_name": forms.TextInput(attrs={"placeholder": "e.g. Rabies, DHPP"}),
            "date_administered": forms.DateInput(attrs={"type": "date"}),
            "next_due_date": forms.DateInput(attrs={"type": "date"}),
            "batch_number": forms.TextInput(attrs={"placeholder": "Batch / lot number"}),
            "notes": forms.Textarea(attrs={"rows": 2, "placeholder": "Any reactions, notes…"}),
        }


class MedicalAttachmentForm(forms.ModelForm):
    class Meta:
        model = MedicalAttachment
        fields = ["file", "description"]
        widgets = {
            "description": forms.TextInput(attrs={"placeholder": "e.g. Blood work results"}),
        }