from django import forms
from decimal import Decimal

from .models import BillingLineItem, Payment


class LineItemForm(forms.ModelForm):
    class Meta:
        model = BillingLineItem
        fields = ["description", "quantity", "unit_price"]
        widgets = {
            "description": forms.TextInput(attrs={"placeholder": "Service / item description"}),
            "quantity": forms.NumberInput(attrs={"min": 1, "value": 1}),
            "unit_price": forms.NumberInput(attrs={"min": 0, "step": "0.01", "placeholder": "0.00"}),
        }

    def clean_unit_price(self):
        price = self.cleaned_data["unit_price"]
        if price < 0:
            raise forms.ValidationError("Price cannot be negative.")
        return price


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ["amount", "method", "reference"]
        widgets = {
            "amount": forms.NumberInput(attrs={"min": "0.01", "step": "0.01", "placeholder": "0.00"}),
            "reference": forms.TextInput(attrs={"placeholder": "Ref # (required for non-cash)"}),
        }

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if amount <= 0:
            raise forms.ValidationError("Payment amount must be greater than zero.")
        return amount

    def clean(self):
        cleaned_data = super().clean()
        method = cleaned_data.get("method")
        reference = (cleaned_data.get("reference") or "").strip()

        if method and method != Payment.METHOD_CASH and not reference:
            self.add_error("reference", "Reference number is required for non-cash payments.")
        return cleaned_data


class OwnerPaymentSubmissionForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ["amount", "method", "reference"]
        widgets = {
            "amount": forms.NumberInput(attrs={"min": "0.01", "step": "0.01", "placeholder": "0.00"}),
            "reference": forms.TextInput(attrs={"placeholder": "Enter payment reference number"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["method"].choices = [
            (Payment.METHOD_GCASH, "GCash"),
            (Payment.METHOD_MAYA, "Maya"),
            (Payment.METHOD_BANK_TRANSFER, "Bank Transfer"),
            (Payment.METHOD_EWALLET, "Other E-wallet"),
        ]

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if amount <= 0:
            raise forms.ValidationError("Payment amount must be greater than zero.")
        return amount

    def clean_reference(self):
        reference = (self.cleaned_data.get("reference") or "").strip()
        if not reference:
            raise forms.ValidationError("Reference number is required for payment submission.")
        return reference
