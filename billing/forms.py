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
            "reference": forms.TextInput(attrs={"placeholder": "Ref # (for e-wallet)"}),
        }

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if amount <= 0:
            raise forms.ValidationError("Payment amount must be greater than zero.")
        return amount
