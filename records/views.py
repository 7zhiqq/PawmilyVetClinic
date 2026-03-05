from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import Pet
from accounts.views import _is_staff_or_manager

from .forms import MedicalAttachmentForm, MedicalRecordForm, VaccinationRecordForm
from .models import MedicalRecord


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _can_view_medical_records(user, pet):
    """Staff/managers can view any pet's records; owners can view their own."""
    if _is_staff_or_manager(user):
        return True
    return pet.owner_id == user.id


# ─── Medical Records ─────────────────────────────────────────────────────────


@login_required
def medical_records_list(request, pet_id):
    """List all medical records for a given pet."""
    pet = get_object_or_404(Pet, pk=pet_id)
    if not _can_view_medical_records(request.user, pet):
        return HttpResponseForbidden("You do not have access to this pet's records.")

    records = pet.medical_records.prefetch_related("vaccinations", "attachments").all()
    vaccinations = pet.vaccinations.all()

    return render(request, "medical_records_list.html", {
        "pet": pet,
        "records": records,
        "vaccinations": vaccinations,
        "is_staff": _is_staff_or_manager(request.user),
    })


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

    return render(request, "medical_record_detail.html", {
        "pet": pet,
        "record": record,
        "is_staff": _is_staff_or_manager(request.user),
    })


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
    else:
        form = MedicalRecordForm()

    return render(request, "medical_record_form.html", {
        "pet": pet,
        "form": form,
        "title": "New Medical Record",
    })


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
    else:
        form = MedicalRecordForm(instance=record)

    return render(request, "medical_record_form.html", {
        "pet": pet,
        "form": form,
        "record": record,
        "title": "Edit Medical Record",
    })


@login_required
@transaction.atomic
def vaccination_add(request, pet_id):
    """Staff adds a vaccination record, optionally linked to a medical record."""
    if not _is_staff_or_manager(request.user):
        return HttpResponseForbidden("Only staff can add vaccination records.")

    pet = get_object_or_404(Pet, pk=pet_id)
    medical_record_id = request.GET.get("record") or request.POST.get("medical_record")

    if request.method == "POST":
        form = VaccinationRecordForm(request.POST)
        if form.is_valid():
            vax = form.save(commit=False)
            vax.pet = pet
            vax.administered_by = request.user
            if medical_record_id:
                vax.medical_record_id = int(medical_record_id)
            vax.save()
            messages.success(request, "Vaccination record added.")
            if vax.medical_record_id:
                return redirect("medical_record_detail", pet_id=pet.pk, record_id=vax.medical_record_id)
            return redirect("medical_records_list", pet_id=pet.pk)
    else:
        form = VaccinationRecordForm()

    return render(request, "vaccination_form.html", {
        "pet": pet,
        "form": form,
        "medical_record_id": medical_record_id,
        "title": "Add Vaccination",
    })


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
    else:
        form = MedicalAttachmentForm()

    return render(request, "attachment_form.html", {
        "pet": pet,
        "record": record,
        "form": form,
    })


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
