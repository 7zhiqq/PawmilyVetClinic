from django.contrib import admin

from .models import BillingLineItem, BillingRecord, Payment


class LineItemInline(admin.TabularInline):
    model = BillingLineItem
    extra = 0


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0


@admin.register(BillingRecord)
class BillingRecordAdmin(admin.ModelAdmin):
    list_display = ("invoice_number", "owner", "pet", "total_amount", "amount_paid", "payment_status", "created_at")
    list_filter = ("payment_status", "created_at")
    search_fields = ("invoice_number", "owner__first_name", "owner__last_name", "pet__name")
    date_hierarchy = "created_at"
    inlines = [LineItemInline, PaymentInline]
