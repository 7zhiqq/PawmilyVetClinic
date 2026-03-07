from decimal import Decimal
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import Pet
from accounts.views import _is_staff_or_manager
from appointments.models import Appointment
from billing.views import add_vaccination_to_billing

from .forms import MedicalAttachmentForm, MedicalRecordForm, VaccinationRecordForm
from .models import MedicalRecord, VaccinationSchedule, FollowUpReminder



# ─── Helpers ──────────────────────────────────────────────────────────────────


def _can_view_medical_records(user, pet):
    """Staff/managers can view any pet's records; owners can view their own."""
    if _is_staff_or_manager(user):
        return True
    return pet.owner_id == user.id


def _get_pet_reminders(pet):
    """Get all vaccination and follow-up reminders for a pet, grouped by status."""
    vaccin_schedules = pet.vaccination_schedules.filter(
        status__in=[
            VaccinationSchedule.STATUS_PENDING,
            VaccinationSchedule.STATUS_DUE,
            VaccinationSchedule.STATUS_OVERDUE,
        ]
    ).select_related("vaccine_type").order_by("next_due_date")
    
    followup_reminders = pet.followup_reminders.filter(
        status__in=[
            FollowUpReminder.STATUS_PENDING,
            FollowUpReminder.STATUS_DUE,
            FollowUpReminder.STATUS_OVERDUE,
        ]
    ).select_related("medical_record").order_by("follow_up_date")
    
    return {
        "vaccinations": vaccin_schedules,
        "followups": followup_reminders,
    }



# ─── Medical Records ─────────────────────────────────────────────────────────


@login_required
def medical_records_list(request, pet_id):
    """List all medical records for a given pet."""
    pet = get_object_or_404(Pet, pk=pet_id)
    if not _can_view_medical_records(request.user, pet):
        return HttpResponseForbidden("You do not have access to this pet's records.")

    records = pet.medical_records.prefetch_related("vaccinations", "attachments").all()
    vaccinations = pet.vaccinations.all()
    reminders = _get_pet_reminders(pet)

    ctx = {
        "pet": pet,
        "records": records,
        "vaccinations": vaccinations,
        "vaccination_schedules": reminders["vaccinations"],
        "followup_reminders": reminders["followups"],
        "is_staff": _is_staff_or_manager(request.user),
    }

    # Provide blank forms for modals (staff only)
    if _is_staff_or_manager(request.user):
        ctx["record_form"] = MedicalRecordForm()
        ctx["vaccination_form"] = VaccinationRecordForm(pet=pet)

    return render(request, "medical_records_list.html", ctx)


@login_required
def medical_record_detail(request, pet_id, record_id):
    """View a single medical record with vaccinations and attachments."""
    pet = get_object_or_404(Pet, pk=pet_id)
    if not _can_view_medical_records(request.user, pet):
        return HttpResponseForbidden("You do not have access to this pet's records.")

    record = get_object_or_404(
        MedicalRecord.objects.prefetch_related("vaccinations", "attachments"),
        pk=record_id,
        pet=pet,
    )

    ctx = {
        "pet": pet,
        "record": record,
        "is_staff": _is_staff_or_manager(request.user),
    }

    # Provide blank forms for modals (staff only)
    if _is_staff_or_manager(request.user):
        ctx["edit_form"] = MedicalRecordForm(instance=record)
        ctx["vaccination_form"] = VaccinationRecordForm(pet=pet)
        ctx["attachment_form"] = MedicalAttachmentForm()

    return render(request, "medical_record_detail.html", ctx)


@login_required
@transaction.atomic
def medical_record_add(request, pet_id):
    """Staff creates a new medical record for a pet."""
    if not _is_staff_or_manager(request.user):
        return HttpResponseForbidden("Only staff can create medical records.")

    pet = get_object_or_404(Pet, pk=pet_id)

    if request.method == "POST":
        form = MedicalRecordForm(request.POST)
        if form.is_valid():
            record = form.save(commit=False)
            record.pet = pet
            record.created_by = request.user
            record.save()
            messages.success(request, "Medical record created.")
            return redirect("medical_record_detail", pet_id=pet.pk, record_id=record.pk)
        # Re-render records list with invalid form so modal auto-opens
        records = pet.medical_records.prefetch_related("vaccinations", "attachments").all()
        vaccinations = pet.vaccinations.all()
        reminders = _get_pet_reminders(pet)
        return render(request, "medical_records_list.html", {
            "pet": pet,
            "records": records,
            "vaccinations": vaccinations,
            "vaccination_schedules": reminders["vaccinations"],
            "followup_reminders": reminders["followups"],
            "is_staff": True,
            "record_form": form,
            "vaccination_form": VaccinationRecordForm(pet=pet),
        })
    return redirect("medical_records_list", pet_id=pet_id)


@login_required
@transaction.atomic
def medical_record_edit(request, pet_id, record_id):
    """Staff edits an existing medical record."""
    if not _is_staff_or_manager(request.user):
        return HttpResponseForbidden("Only staff can edit medical records.")

    pet = get_object_or_404(Pet, pk=pet_id)
    record = get_object_or_404(MedicalRecord, pk=record_id, pet=pet)

    if request.method == "POST":
        form = MedicalRecordForm(request.POST, instance=record)
        if form.is_valid():
            form.save()
            messages.success(request, "Medical record updated.")
            return redirect("medical_record_detail", pet_id=pet.pk, record_id=record.pk)
        # Re-render detail page with invalid form so edit modal auto-opens
        return render(request, "medical_record_detail.html", {
            "pet": pet,
            "record": record,
            "is_staff": True,
            "edit_form": form,
            "vaccination_form": VaccinationRecordForm(pet=pet),
            "attachment_form": MedicalAttachmentForm(),
        })
    return redirect("medical_record_detail", pet_id=pet_id, record_id=record_id)


@login_required
@transaction.atomic
def vaccination_add(request, pet_id):
    """Staff adds a vaccination record, optionally linked to a medical record."""
    if not _is_staff_or_manager(request.user):
        return HttpResponseForbidden("Only staff can add vaccination records.")

    pet = get_object_or_404(Pet, pk=pet_id)
    medical_record_id = request.GET.get("record") or request.POST.get("medical_record")
    appointment_id = request.POST.get("appointment_id") or request.GET.get("appointment_id")

    if request.method == "POST":
        form = VaccinationRecordForm(request.POST, pet=pet)
        if form.is_valid():
            vax = form.save(commit=False)
            vax.pet = pet
            vax.administered_by = request.user
            if medical_record_id:
                vax.medical_record_id = int(medical_record_id)
            vax.save()

            # Auto-add vaccination fee to billing if linked to an appointment
            vax_fee = form.cleaned_data.get("vaccination_fee") or Decimal("0.00")
            if vax_fee > 0 and appointment_id:
                apt = Appointment.objects.filter(pk=int(appointment_id)).first()
                if apt:
                    add_vaccination_to_billing(apt, vax.vaccine_name, vax_fee)

            messages.success(request, "Vaccination record added.")

            # If coming from the finalize flow, redirect back to step 3
            if appointment_id:
                return redirect("finalize_step3", appointment_id=int(appointment_id))
            if vax.medical_record_id:
                return redirect("medical_record_detail", pet_id=pet.pk, record_id=vax.medical_record_id)
            return redirect("medical_records_list", pet_id=pet.pk)
        # Re-render the appropriate page with the invalid form so modal auto-opens
        if appointment_id:
            return redirect("finalize_step3", appointment_id=int(appointment_id))
        if medical_record_id:
            record = get_object_or_404(MedicalRecord, pk=int(medical_record_id), pet=pet)
            return render(request, "medical_record_detail.html", {
                "pet": pet,
                "record": record,
                "is_staff": True,
                "edit_form": MedicalRecordForm(instance=record),
                "vaccination_form": form,
                "attachment_form": MedicalAttachmentForm(),
            })
        else:
            records = pet.medical_records.prefetch_related("vaccinations", "attachments").all()
            vaccinations = pet.vaccinations.all()
            reminders = _get_pet_reminders(pet)
            return render(request, "medical_records_list.html", {
                "pet": pet,
                "records": records,
                "vaccinations": vaccinations,
                "vaccination_schedules": reminders["vaccinations"],
                "followup_reminders": reminders["followups"],
                "is_staff": True,
                "record_form": MedicalRecordForm(),
                "vaccination_form": form,
            })
    return redirect("medical_records_list", pet_id=pet_id)


@login_required
@transaction.atomic
def attachment_add(request, pet_id, record_id):
    """Staff uploads a file attachment to a medical record."""
    if not _is_staff_or_manager(request.user):
        return HttpResponseForbidden("Only staff can upload attachments.")

    pet = get_object_or_404(Pet, pk=pet_id)
    record = get_object_or_404(MedicalRecord, pk=record_id, pet=pet)

    if request.method == "POST":
        form = MedicalAttachmentForm(request.POST, request.FILES)
        if form.is_valid():
            att = form.save(commit=False)
            att.medical_record = record
            att.uploaded_by = request.user
            att.save()
            messages.success(request, "Attachment uploaded.")
            return redirect("medical_record_detail", pet_id=pet.pk, record_id=record.pk)
        # Re-render detail page with invalid form so attachment modal auto-opens
        return render(request, "medical_record_detail.html", {
            "pet": pet,
            "record": record,
            "is_staff": True,
            "edit_form": MedicalRecordForm(instance=record),
            "vaccination_form": VaccinationRecordForm(pet=pet),
            "attachment_form": form,
        })
    return redirect("medical_record_detail", pet_id=pet_id, record_id=record_id)


@login_required
def pet_records_search(request):
    """Staff view to search for any pet and access their medical records."""
    if not _is_staff_or_manager(request.user):
        return HttpResponseForbidden("Only staff can access this page.")

    query = request.GET.get("q", "").strip()
    pets = Pet.objects.select_related("owner").order_by("name")
    if query:
        pets = pets.filter(
            Q(name__icontains=query)
            | Q(owner__first_name__icontains=query)
            | Q(owner__last_name__icontains=query)
            | Q(breed__icontains=query)
        )

    return render(request, "pet_records_search.html", {
        "pets": pets,
        "query": query,
    })


# ─── Post-Completion Stepper Flow ─────────────────────────────────────────────

STEPS = [
    {"num": 1, "label": "Appointment", "icon": "fa-calendar-check"},
    {"num": 2, "label": "Medical Record", "icon": "fa-notes-medical"},
    {"num": 3, "label": "Vaccination", "icon": "fa-syringe"},
    {"num": 4, "label": "Billing", "icon": "fa-file-invoice"},
]


def _get_completed_appointment(request, appointment_id):
    """Helper: validate staff access and return completed appointment + pet."""
    if not _is_staff_or_manager(request.user):
        return None, None, HttpResponseForbidden("Only staff can access this page.")
    apt = get_object_or_404(
        Appointment.objects.select_related("owner", "pet", "staff"),
        pk=appointment_id,
        status=Appointment.STATUS_COMPLETED,
    )
    return apt, apt.pet, None


def _max_allowed_step(apt):
    """Return the highest step the user may visit based on saved data."""
    has_record = MedicalRecord.objects.filter(appointment=apt).exists()
    return 4 if has_record else 2  # steps 3 & 4 require a saved medical record


def _stepper_context(current_step, apt):
    """Build the stepper info list for templates."""
    max_step = _max_allowed_step(apt)
    steps = []
    for s in STEPS:
        state = "completed" if s["num"] < current_step else (
            "active" if s["num"] == current_step else "upcoming"
        )
        clickable = s["num"] <= max(max_step, current_step)
        steps.append({**s, "state": state, "clickable": clickable})
    return steps


@login_required
def finalize_step1(request, appointment_id):
    """Step 1 — Appointment completed summary."""
    apt, pet, err = _get_completed_appointment(request, appointment_id)
    if err:
        return err

    return render(request, "finalize_step1.html", {
        "appointment": apt,
        "pet": pet,
        "steps": _stepper_context(1, apt),
        "current_step": 1,
    })


@login_required
@transaction.atomic
def finalize_step2(request, appointment_id):
    """Step 2 — Create / edit the medical record."""
    apt, pet, err = _get_completed_appointment(request, appointment_id)
    if err:
        return err

    medical_record = MedicalRecord.objects.filter(appointment=apt).first()

    if request.method == "POST":
        form = MedicalRecordForm(request.POST, instance=medical_record)
        if form.is_valid():
            record = form.save(commit=False)
            if not medical_record:
                record.pet = pet
                record.appointment = apt
                record.created_by = request.user
            record.save()
            messages.success(request, "Medical record saved.")
            return redirect("finalize_step3", appointment_id=apt.pk)
    else:
        if medical_record:
            form = MedicalRecordForm(instance=medical_record)
        else:
            form = MedicalRecordForm(initial={
                "visit_date": apt.appointment_date,
                "chief_complaint": apt.reason,
            })

    return render(request, "finalize_step2.html", {
        "appointment": apt,
        "pet": pet,
        "form": form,
        "medical_record": medical_record,
        "steps": _stepper_context(2, apt),
        "current_step": 2,
    })


@login_required
def finalize_step3(request, appointment_id):
    """Step 3 — Vaccinations (optional)."""
    apt, pet, err = _get_completed_appointment(request, appointment_id)
    if err:
        return err

    if _max_allowed_step(apt) < 3:
        return redirect("finalize_step2", appointment_id=apt.pk)

    medical_record = MedicalRecord.objects.filter(appointment=apt).first()
    vaccinations = medical_record.vaccinations.all() if medical_record else []

    return render(request, "finalize_step3.html", {
        "appointment": apt,
        "pet": pet,
        "medical_record": medical_record,
        "vaccination_form": VaccinationRecordForm(pet=pet),
        "vaccinations": vaccinations,
        "steps": _stepper_context(3, apt),
        "current_step": 3,
    })


@login_required
def finalize_step4(request, appointment_id):
    """Step 4 — Billing summary."""
    apt, pet, err = _get_completed_appointment(request, appointment_id)
    if err:
        return err

    if _max_allowed_step(apt) < 3:
        return redirect("finalize_step2", appointment_id=apt.pk)

    billing_record = getattr(apt, "billing_record", None)

    return render(request, "finalize_step4.html", {
        "appointment": apt,
        "pet": pet,
        "billing_record": billing_record,
        "steps": _stepper_context(4, apt),
        "current_step": 4,
    })
