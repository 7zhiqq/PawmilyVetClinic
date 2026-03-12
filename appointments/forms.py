from django import forms
from django.contrib.auth import get_user_model

from accounts.models import Pet, Profile
from .models import Appointment

User = get_user_model()


REASON_CHOICES = [
    ("", "Select reason"),
    ("Check-up", "Check-up"),
    ("Vaccination", "Vaccination"),
    ("Consultation", "Consultation"),
    ("Grooming", "Grooming"),
    ("Surgery", "Surgery"),
    ("Other", "Other"),
]


class AppointmentBookingForm(forms.ModelForm):
    """Pet owner booking form."""

    reason = forms.ChoiceField(choices=REASON_CHOICES, required=True)
    reason_other = forms.CharField(required=False, max_length=200)

    class Meta:
        model = Appointment
        fields = ["pet", "appointment_date", "start_time", "reason"]
        widgets = {
            "appointment_date": forms.DateInput(attrs={"type": "date"}),
            "start_time": forms.TimeInput(attrs={"type": "time"}),
        }

    def __init__(self, *args, owner=None, **kwargs):
        super().__init__(*args, **kwargs)
        if owner:
            self.fields["pet"].queryset = Pet.objects.filter(owner=owner).order_by("name")

        # Backfill "Other" value when editing/redisplaying existing free-text reasons.
        reason_value = self.initial.get("reason") or getattr(self.instance, "reason", "")
        if reason_value and reason_value not in dict(REASON_CHOICES):
            self.initial["reason"] = "Other"
            self.initial["reason_other"] = reason_value

    def clean(self):
        cleaned_data = super().clean()
        reason = cleaned_data.get("reason")
        custom_reason = (cleaned_data.get("reason_other") or "").strip()

        if reason == "Other":
            if not custom_reason:
                self.add_error("reason_other", "Please provide the specific reason for the visit.")
            else:
                cleaned_data["reason"] = custom_reason

        return cleaned_data


class AppointmentStaffForm(forms.ModelForm):
    """Staff form for walk-ins and scheduling."""

    reason = forms.ChoiceField(choices=REASON_CHOICES, required=True)
    reason_other = forms.CharField(required=False, max_length=200)

    class Meta:
        model = Appointment
        fields = ["owner", "pet", "appointment_date", "start_time", "end_time", "appointment_type", "reason", "notes", "status"]
        widgets = {
            "appointment_date": forms.DateInput(attrs={"type": "date"}),
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "end_time": forms.TimeInput(attrs={"type": "time"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        pet_owners = User.objects.filter(profile__role=Profile.ROLE_PET_OWNER).order_by("username")
        self.fields["owner"].queryset = pet_owners
        self.fields["status"].initial = Appointment.STATUS_CONFIRMED

        reason_value = self.initial.get("reason") or getattr(self.instance, "reason", "")
        if reason_value and reason_value not in dict(REASON_CHOICES):
            self.initial["reason"] = "Other"
            self.initial["reason_other"] = reason_value

    def clean(self):
        cleaned_data = super().clean()
        reason = cleaned_data.get("reason")
        custom_reason = (cleaned_data.get("reason_other") or "").strip()

        if reason == "Other":
            if not custom_reason:
                self.add_error("reason_other", "Please provide the specific reason for the visit.")
            else:
                cleaned_data["reason"] = custom_reason

        return cleaned_data
