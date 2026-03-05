from django import forms
from django.contrib.auth import get_user_model

from accounts.models import Pet, Profile
from .models import Appointment

User = get_user_model()


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
