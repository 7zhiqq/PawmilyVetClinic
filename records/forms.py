from decimal import Decimal
import json

from django import forms
from django.db import IntegrityError
from django.utils import timezone

from .models import MedicalAttachment, MedicalRecord, VaccinationRecord, VaccineType
from .vaccination_protocols import (
    find_protocol,
    protocol_catalog_for_species,
    protocol_price_for_species,
    schedule_reference_for_vaccine,
)


def _protocol_interval_days(protocol):
    if protocol.maintenance_days:
        return protocol.maintenance_days
    if protocol.maintenance_months:
        return protocol.maintenance_months * 30
    return 365


def _active_vaccine_types_for_species(species):
    queryset = VaccineType.objects.filter(is_active=True)
    if species:
        queryset = queryset.filter(species=species)
    return queryset.order_by("name")


def _resolve_vaccine_type_for_protocol(pet, protocol):
    default_interval = _protocol_interval_days(protocol)
    default_price = protocol_price_for_species(pet.species, protocol.name)
    default_description = schedule_reference_for_vaccine(
        pet.species,
        protocol.name,
        booster_interval_days=default_interval,
    )

    matched_type = VaccineType.objects.filter(
        name=protocol.name,
        species=pet.species,
    ).first()
    if not matched_type:
        try:
            matched_type = VaccineType.objects.create(
                name=protocol.name,
                species=pet.species,
                booster_interval_days=default_interval,
                unit_price=default_price,
                description=default_description,
                is_active=True,
            )
        except IntegrityError:
            # Legacy databases may still enforce a global unique index on name.
            matched_type = VaccineType.objects.filter(name=protocol.name).first()

    if not matched_type:
        return None

    updates = []
    if matched_type.booster_interval_days != default_interval:
        matched_type.booster_interval_days = default_interval
        updates.append("booster_interval_days")
    if matched_type.unit_price != default_price and default_price > 0:
        matched_type.unit_price = default_price
        updates.append("unit_price")
    if matched_type.description != default_description:
        matched_type.description = default_description
        updates.append("description")
    if not matched_type.is_active:
        matched_type.is_active = True
        updates.append("is_active")

    # Only rewrite species when it already matches or the name is no longer globally unique.
    if matched_type.species != pet.species and not VaccineType.objects.filter(name=protocol.name, species=pet.species).exists():
        duplicate_name_count = VaccineType.objects.filter(name=protocol.name).count()
        if duplicate_name_count == 0:
            matched_type.species = pet.species
            updates.append("species")

    if updates:
        matched_type.save(update_fields=updates)
    return matched_type


class VaccineCatalogForm(forms.ModelForm):
    class Meta:
        model = VaccineType
        fields = [
            "name",
            "species",
            "booster_interval_days",
            "unit_price",
            "description",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "e.g. Rabies Vaccine"}),
            "species": forms.Select(),
            "booster_interval_days": forms.NumberInput(attrs={"min": "1", "step": "1"}),
            "unit_price": forms.NumberInput(attrs={"min": "0", "step": "0.01"}),
            "description": forms.Textarea(attrs={"rows": 3, "placeholder": "Default schedule reference or clinic notes"}),
            "is_active": forms.CheckboxInput(),
        }
        labels = {
            "booster_interval_days": "Booster Interval (Days)",
            "unit_price": "Price per Shot (PHP)",
            "description": "Default Schedule Reference",
            "is_active": "Available in vaccination dropdowns",
        }

    def clean_name(self):
        return (self.cleaned_data.get("name") or "").strip()

    def clean_unit_price(self):
        unit_price = self.cleaned_data.get("unit_price")
        if unit_price is not None and unit_price < 0:
            raise forms.ValidationError("Price per shot cannot be negative.")
        return unit_price


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
    administered_vaccine = forms.ChoiceField(
        required=False,
        choices=(),
        widget=forms.Select(attrs={"class": "form-control"}),
        help_text="Choose the vaccine or preventive treatment administered this visit.",
    )

    vaccine_price = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        initial=Decimal("0.00"),
        widget=forms.NumberInput(attrs={"min": "0", "step": "0.01", "readonly": "readonly"}),
        help_text="Auto-priced from the selected vaccine (₱ per shot).",
    )

    class Meta:
        model = VaccinationRecord
        fields = [
            "vaccine_name", "vaccine_type", "date_administered", "shots_administered", "next_due_date",
            "batch_number", "notes",
        ]
        widgets = {
            "vaccine_name": forms.HiddenInput(),
            "vaccine_type": forms.Select(attrs={"class": "form-control"}),
            "date_administered": forms.DateInput(attrs={"type": "date"}),
            "shots_administered": forms.NumberInput(attrs={"min": "1", "step": "1"}),
            "next_due_date": forms.DateInput(attrs={"type": "date"}),
            "batch_number": forms.TextInput(attrs={"placeholder": "Batch / lot number"}),
            "notes": forms.Textarea(attrs={"rows": 2, "placeholder": "Any reactions, notes…"}),
        }

    def __init__(self, *args, pet=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.pet = pet
        species = getattr(pet, "species", None)

        # Filter vaccine types by pet species
        if pet:
            vaccine_queryset = _active_vaccine_types_for_species(species)
        else:
            vaccine_queryset = VaccineType.objects.filter(is_active=True).order_by("species", "name")
        self.fields['vaccine_type'].queryset = vaccine_queryset
        
        # Vaccine name is derived from selected dropdown value.
        self.fields["vaccine_name"].required = False

        # Make vaccine_type optional; it is auto-linked from the selected vaccine when possible.
        self.fields['vaccine_type'].required = False
        self.fields['vaccine_type'].widget = forms.HiddenInput()
        self.fields['vaccine_type'].help_text = "Auto-linked for schedule tracking"

        vaccine_catalog = list(vaccine_queryset)
        if vaccine_catalog:
            price_map = {vaccine.name: vaccine.unit_price for vaccine in vaccine_catalog}
            schedule_map = {
                vaccine.name: schedule_reference_for_vaccine(
                    vaccine.species,
                    vaccine.name,
                    description=vaccine.description,
                    booster_interval_days=vaccine.booster_interval_days,
                )
                for vaccine in vaccine_catalog
            }
            protocol_choices = [("", "Select vaccine/treatment")] + [
                (vaccine.name, f"{vaccine.name} (₱{vaccine.unit_price:,.2f})")
                for vaccine in vaccine_catalog
            ]
        else:
            species_protocols = protocol_catalog_for_species(species)
            price_map = {
                protocol.name: protocol_price_for_species(species, protocol.name)
                for protocol in species_protocols
            }
            schedule_map = {
                protocol.name: schedule_reference_for_vaccine(species, protocol.name)
                for protocol in species_protocols
            }
            protocol_choices = [("", "Select vaccine/treatment")] + [
                (protocol.name, f"{protocol.name} (₱{price_map[protocol.name]:,.2f})")
                for protocol in species_protocols
            ]

        self.fields["administered_vaccine"].choices = protocol_choices
        self.fields["administered_vaccine"].required = bool(protocol_choices[1:])
        self.fields["administered_vaccine"].widget.attrs["data-price-map"] = json.dumps(
            {name: str(price) for name, price in price_map.items()}
        )
        self.fields["administered_vaccine"].widget.attrs["data-schedule-map"] = json.dumps(schedule_map)

        self.fields["shots_administered"].required = False
        self.fields["shots_administered"].initial = 1
        self.fields["shots_administered"].help_text = "Number of shots/doses given for this vaccine entry."

        if self.instance and self.instance.pk and self.instance.vaccine_name:
            self.fields["administered_vaccine"].initial = self.instance.vaccine_name
            resolved_price = Decimal("0.00")
            if self.instance.vaccine_type_id:
                resolved_price = self.instance.vaccine_type.unit_price
            if resolved_price <= 0:
                resolved_price = protocol_price_for_species(getattr(pet, "species", None), self.instance.vaccine_name)
            self.fields["vaccine_price"].initial = resolved_price
        else:
            self.fields["vaccine_price"].initial = Decimal("0.00")

        self.fields['date_administered'].required = False
        self.fields['date_administered'].initial = timezone.localdate()
        self.fields['next_due_date'].required = False
        self.fields['next_due_date'].help_text = "Leave blank to auto-calculate from birth date and dose history"

    def clean(self):
        cleaned_data = super().clean()
        selected_vaccine = (cleaned_data.get("administered_vaccine") or "").strip()
        vaccine_type = cleaned_data.get("vaccine_type")
        vaccine_name = (cleaned_data.get("vaccine_name") or "").strip()
        date_administered = cleaned_data.get("date_administered")
        shots_administered = cleaned_data.get("shots_administered") or 1
        cleaned_data["shots_administered"] = max(1, int(shots_administered))
        resolved_price = Decimal("0.00")

        if not date_administered:
            cleaned_data["date_administered"] = timezone.localdate()

        if selected_vaccine:
            vaccine_name = selected_vaccine
            cleaned_data["vaccine_name"] = selected_vaccine

            if self.pet:
                matched_type = VaccineType.objects.filter(
                    name=selected_vaccine,
                    species=self.pet.species,
                ).order_by("-is_active", "name").first()
                if matched_type:
                    cleaned_data["vaccine_type"] = matched_type
                    vaccine_type = matched_type
                    resolved_price = matched_type.unit_price

                protocol = find_protocol(self.pet.species, selected_vaccine)
                if protocol and not matched_type:
                    matched_type = _resolve_vaccine_type_for_protocol(self.pet, protocol)
                    if matched_type:
                        cleaned_data["vaccine_type"] = matched_type
                        vaccine_type = matched_type
                        resolved_price = matched_type.unit_price
            elif not vaccine_type:
                matched_type = VaccineType.objects.filter(name=selected_vaccine, is_active=True).order_by("species", "name").first()
                if matched_type:
                    cleaned_data["vaccine_type"] = matched_type
                    vaccine_type = matched_type
                    resolved_price = matched_type.unit_price

        elif vaccine_type and not vaccine_name:
            cleaned_data["vaccine_name"] = vaccine_type.name
            vaccine_name = vaccine_type.name
            resolved_price = vaccine_type.unit_price

        if vaccine_type and resolved_price <= 0:
            resolved_price = vaccine_type.unit_price
        if resolved_price <= 0 and self.pet and vaccine_name:
            resolved_price = protocol_price_for_species(self.pet.species, vaccine_name)

        cleaned_data["vaccine_price"] = resolved_price

        if not vaccine_name:
            self.add_error("administered_vaccine", "Please select a vaccine or treatment.")

        return cleaned_data


class MedicalAttachmentForm(forms.ModelForm):
    class Meta:
        model = MedicalAttachment
        fields = ["file", "description"]
        widgets = {
            "description": forms.TextInput(attrs={"placeholder": "e.g. Blood work results"}),
        }

