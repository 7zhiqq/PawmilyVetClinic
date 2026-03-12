from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from pawmily.pagination import paginate_queryset

from accounts.views import _is_staff_or_manager

from .forms import LineItemForm, PaymentForm
from .models import BillingLineItem, BillingRecord, Payment

CHECKUP_FEE = Decimal("300.00")


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _ensure_staff(user):
    if not _is_staff_or_manager(user):
        return HttpResponseForbidden("Only staff can access billing.")
    return None


def create_billing_for_appointment(appointment, created_by=None):
    """Create a BillingRecord for a completed appointment (idempotent).

    Automatically adds a ₱300 check-up fee line item.
    """
    if hasattr(appointment, "billing_record"):
        return appointment.billing_record
    record = BillingRecord.objects.create(
        appointment=appointment,
        owner=appointment.owner,
        pet=appointment.pet,
        created_by=created_by,
    )
    BillingLineItem.objects.create(
        billing_record=record,
        description="Check-up Fee",
        quantity=1,
        unit_price=CHECKUP_FEE,
    )
    record.recalculate()
    return record


def add_vaccination_to_billing(appointment, vaccine_name, fee):
    """Add a vaccination line item to the billing record for an appointment."""
    if not hasattr(appointment, "billing_record"):
        return
    record = appointment.billing_record
    BillingLineItem.objects.create(
        billing_record=record,
        description=f"Vaccination – {vaccine_name}",
        quantity=1,
        unit_price=fee,
    )
    record.recalculate()


# ─── Views ────────────────────────────────────────────────────────────────────

@login_required
def billing_list(request):
    """Staff: list all invoices. Owners: see only their own invoices."""
    is_staff = _is_staff_or_manager(request.user)
    if is_staff:
        qs = BillingRecord.objects.select_related("appointment", "owner", "pet").all()
    else:
        qs = BillingRecord.objects.select_related("appointment", "owner", "pet").filter(
            owner=request.user,
        )

    status_filter = request.GET.get("status", "")
    if status_filter in ("paid", "partial", "unpaid"):
        qs = qs.filter(payment_status=status_filter)

    search_q = request.GET.get("q", "").strip()
    if search_q:
        qs = qs.filter(
            Q(invoice_number__icontains=search_q)
            | Q(owner__first_name__icontains=search_q)
            | Q(owner__last_name__icontains=search_q)
            | Q(pet__name__icontains=search_q)
        )

    summary = qs.aggregate(
        total_invoiced=Coalesce(
            Sum("total_amount"),
            Value(0),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        ),
        total_paid=Coalesce(
            Sum("amount_paid"),
            Value(0),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        ),
    )
    invoice_count = qs.count()
    outstanding_total = summary["total_invoiced"] - summary["total_paid"]

    records_page_obj, records_pagination_query = paginate_queryset(
        request,
        qs,
        per_page=12,
        page_param="billing_page",
    )

    return render(request, "billing_list.html", {
        "records": records_page_obj,
        "records_page_obj": records_page_obj,
        "records_pagination_query": records_pagination_query,
        "is_staff": is_staff,
        "current_status": status_filter,
        "search_q": search_q,
        "invoice_count": invoice_count,
        "total_invoiced": summary["total_invoiced"],
        "total_paid": summary["total_paid"],
        "outstanding_total": outstanding_total,
    })


@login_required
def billing_detail(request, pk):
    """View a single invoice (invoice or receipt mode)."""
    record = get_object_or_404(
        BillingRecord.objects.select_related("appointment", "owner", "pet"),
        pk=pk,
    )
    is_staff = _is_staff_or_manager(request.user)
    if not is_staff and record.owner != request.user:
        return HttpResponseForbidden("You cannot view this billing record.")

    line_items = record.line_items.all()
    payments = record.payments.all()

    line_items_page_obj, line_items_pagination_query = paginate_queryset(
        request,
        line_items,
        per_page=10,
        page_param="items_page",
    )
    payments_page_obj, payments_pagination_query = paginate_queryset(
        request,
        payments,
        per_page=10,
        page_param="payments_page",
    )
    line_form = LineItemForm() if is_staff else None
    payment_form = PaymentForm() if is_staff else None

    doc_view = request.GET.get("view", "invoice")
    if doc_view not in ("invoice", "receipt"):
        doc_view = "invoice"

    return render(request, "billing_detail.html", {
        "record": record,
        "line_items": line_items_page_obj,
        "line_items_page_obj": line_items_page_obj,
        "line_items_pagination_query": line_items_pagination_query,
        "payments": payments_page_obj,
        "payments_page_obj": payments_page_obj,
        "payments_pagination_query": payments_pagination_query,
        "line_form": line_form,
        "payment_form": payment_form,
        "is_staff": is_staff,
        "doc_view": doc_view,
    })


@login_required
def billing_add_line_item(request, pk):
    """Staff: add a line item to a billing record."""
    forbidden = _ensure_staff(request.user)
    if forbidden:
        return forbidden

    record = get_object_or_404(BillingRecord, pk=pk)

    if request.method == "POST":
        form = LineItemForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.billing_record = record
            item.save()
            record.recalculate()
            messages.success(request, "Line item added.")
        else:
            for err in form.errors.values():
                messages.error(request, err.as_text())

    return redirect("billing_detail", pk=pk)


@login_required
def billing_remove_line_item(request, pk, item_id):
    """Staff: remove a line item."""
    forbidden = _ensure_staff(request.user)
    if forbidden:
        return forbidden

    record = get_object_or_404(BillingRecord, pk=pk)
    item = get_object_or_404(BillingLineItem, pk=item_id, billing_record=record)

    if request.method == "POST":
        item.delete()
        record.recalculate()
        messages.success(request, "Line item removed.")

    return redirect("billing_detail", pk=pk)


@login_required
def billing_add_payment(request, pk):
    """Staff: record a payment against a billing record."""
    forbidden = _ensure_staff(request.user)
    if forbidden:
        return forbidden

    record = get_object_or_404(BillingRecord, pk=pk)

    if request.method == "POST":
        form = PaymentForm(request.POST)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.billing_record = record
            payment.recorded_by = request.user
            payment.save()
            record.recalculate()
            messages.success(request, f"Payment of ₱{payment.amount} recorded.")
        else:
            for err in form.errors.values():
                messages.error(request, err.as_text())

    return redirect("billing_detail", pk=pk)

