from decimal import Decimal

from django import forms

from .models import MedicalAttachment, MedicalRecord, VaccinationRecord, VaccineType


class MedicalRecordForm(forms.ModelForm):
    class Meta:
        model = MedicalRecord
        fields = [
            "visit_date", "chief_complaint", "consultation_notes",
            "diagnosis", "treatment", "prescription", "follow_up_date", "follow_up_reason",
        ]
        widgets = {
            "visit_date": forms.DateInput(attrs={"type": "date"}),
            "chief_complaint": forms.TextInput(attrs={"placeholder": "e.g. Limping on right hind leg"}),
            "consultation_notes": forms.Textarea(attrs={"rows": 3, "placeholder": "Observations, history, examination findings…"}),
            "diagnosis": forms.Textarea(attrs={"rows": 2, "placeholder": "e.g. Mild dermatitis"}),
            "treatment": forms.Textarea(attrs={"rows": 2, "placeholder": "Treatment provided…"}),
            "prescription": forms.Textarea(attrs={"rows": 2, "placeholder": "Medications, dosage, frequency…"}),
            "follow_up_date": forms.DateInput(attrs={"type": "date"}),
            "follow_up_reason": forms.TextInput(attrs={"placeholder": "e.g. Monitor wound healing"}),
        }


class VaccinationRecordForm(forms.ModelForm):
    vaccination_fee = forms.DecimalField(
        max_digits=10, decimal_places=2, required=False, initial=Decimal("0.00"),
        widget=forms.NumberInput(attrs={"min": "0", "step": "0.01", "placeholder": "0.00"}),
        help_text="Fee to add to the billing record (₱). Leave 0 for no charge.",
    )

    class Meta:
        model = VaccinationRecord
        fields = [
            "vaccine_name", "vaccine_type", "date_administered", "next_due_date",
            "batch_number", "notes",
        ]
        widgets = {
            "vaccine_name": forms.TextInput(attrs={"placeholder": "e.g. Rabies, DHPP"}),
            "vaccine_type": forms.Select(attrs={"class": "form-control"}),
            "date_administered": forms.DateInput(attrs={"type": "date"}),
            "next_due_date": forms.DateInput(attrs={"type": "date"}),
            "batch_number": forms.TextInput(attrs={"placeholder": "Batch / lot number"}),
            "notes": forms.Textarea(attrs={"rows": 2, "placeholder": "Any reactions, notes…"}),
        }

    def __init__(self, *args, pet=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter vaccine types by pet species
        if pet:
            self.fields['vaccine_type'].queryset = VaccineType.objects.filter(
                species=pet.species,
                is_active=True
            )
        else:
            self.fields['vaccine_type'].queryset = VaccineType.objects.filter(is_active=True)
        
        # Make vaccine_type optional (user can enter custom vaccine name)
        self.fields['vaccine_type'].required = False
        self.fields['vaccine_type'].help_text = "Select for automatic booster calculation, or leave blank for custom vaccines"


class MedicalAttachmentForm(forms.ModelForm):
    class Meta:
        model = MedicalAttachment
        fields = ["file", "description"]
        widgets = {
            "description": forms.TextInput(attrs={"placeholder": "e.g. Blood work results"}),
        }

