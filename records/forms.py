from decimal import Decimal

from django import forms

from .models import MedicalAttachment, MedicalRecord, VaccinationRecord


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
    vaccination_fee = forms.DecimalField(
        max_digits=10, decimal_places=2, required=False, initial=Decimal("0.00"),
        widget=forms.NumberInput(attrs={"min": "0", "step": "0.01", "placeholder": "0.00"}),
        help_text="Fee to add to the billing record (₱). Leave 0 for no charge.",
    )

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
