import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class BillingRecord(models.Model):
    """Master billing record created when an appointment is completed."""

    PAYMENT_STATUS_UNPAID = "unpaid"
    PAYMENT_STATUS_PARTIAL = "partial"
    PAYMENT_STATUS_PAID = "paid"

    PAYMENT_STATUS_CHOICES = [
        (PAYMENT_STATUS_UNPAID, "Unpaid"),
        (PAYMENT_STATUS_PARTIAL, "Partial"),
        (PAYMENT_STATUS_PAID, "Paid"),
    ]

    appointment = models.OneToOneField(
        "appointments.Appointment",
        on_delete=models.CASCADE,
        related_name="billing_record",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="billing_records",
    )
    pet = models.ForeignKey(
        "accounts.Pet",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="billing_records",
    )
    invoice_number = models.CharField(max_length=30, unique=True, editable=False)
    payment_status = models.CharField(
        max_length=10,
        choices=PAYMENT_STATUS_CHOICES,
        default=PAYMENT_STATUS_UNPAID,
    )
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="billing_records_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            self.invoice_number = self._generate_invoice_number()
        super().save(*args, **kwargs)

    @staticmethod
    def _generate_invoice_number():
        now = timezone.now()
        short_uuid = uuid.uuid4().hex[:6].upper()
        return f"INV-{now.strftime('%Y%m%d')}-{short_uuid}"

    @property
    def balance_due(self):
        return self.total_amount - self.amount_paid

    def recalculate(self):
        """Recalculate totals from line items and payments."""
        self.subtotal = sum(item.line_total for item in self.line_items.all())
        self.total_amount = self.subtotal
        self.amount_paid = sum(p.amount for p in self.payments.all())
        if self.amount_paid >= self.total_amount and self.total_amount > 0:
            self.payment_status = self.PAYMENT_STATUS_PAID
        elif self.amount_paid > 0:
            self.payment_status = self.PAYMENT_STATUS_PARTIAL
        else:
            self.payment_status = self.PAYMENT_STATUS_UNPAID
        self.save(update_fields=[
            "subtotal", "total_amount", "amount_paid", "payment_status", "updated_at",
        ])

    def __str__(self):
        return f"{self.invoice_number} – {self.owner.get_full_name() or self.owner.username}"


class BillingLineItem(models.Model):
    """Individual service/item line on a billing record."""

    billing_record = models.ForeignKey(
        BillingRecord,
        on_delete=models.CASCADE,
        related_name="line_items",
    )
    description = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        ordering = ["pk"]

    @property
    def line_total(self):
        return self.quantity * self.unit_price

    def __str__(self):
        return f"{self.description} × {self.quantity}"


class Payment(models.Model):
    """A payment made against a billing record."""

    METHOD_CASH = "cash"
    METHOD_EWALLET = "e_wallet"

    METHOD_CHOICES = [
        (METHOD_CASH, "Cash"),
        (METHOD_EWALLET, "E-wallet"),
    ]

    billing_record = models.ForeignKey(
        BillingRecord,
        on_delete=models.CASCADE,
        related_name="payments",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=10, choices=METHOD_CHOICES)
    reference = models.CharField(
        max_length=100, blank=True,
        help_text="Transaction/reference number for e-wallet payments",
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="payments_recorded",
    )
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-recorded_at"]

    def __str__(self):
        return f"₱{self.amount} via {self.get_method_display()}"
