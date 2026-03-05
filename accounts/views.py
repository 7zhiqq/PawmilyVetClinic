import calendar
import io
import json
from datetime import date, datetime, time, timedelta

import qrcode
import qrcode.constants

from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.db import IntegrityError, transaction
from django.db import models
from django.db.models import Q
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .forms import (
    AppointmentBookingForm,
    AppointmentStaffForm,
    InvitationForm,
    MedicalAttachmentForm,
    MedicalRecordForm,
    PetForm,
    PetOwnerRegistrationForm,
    ProfileForm,
    StaffInviteRegistrationForm,
    VaccinationRecordForm,
    WalkInActivationForm,
    WalkInClientForm,
    WalkInPetForm,
)
from .models import (
    MAX_SLOTS, Appointment, Invitation, MedicalAttachment, MedicalRecord,
    Pet, Profile, VaccinationRecord, WalkInRegistration,
)

User = get_user_model()


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _is_pet_owner(user):
    try:
        return user.profile.role == Profile.ROLE_PET_OWNER
    except Profile.DoesNotExist:
        return False


def _is_staff_or_manager(user):
    try:
        return user.profile.role in (Profile.ROLE_STAFF, Profile.ROLE_MANAGER)
    except Profile.DoesNotExist:
        return user.is_superuser


def _taken_slots(appt_date, start_time):
    """Return a set of slot numbers already booked for scheduled appointments at a date/time.

    This is a GLOBAL check across ALL owners — each time range has at most
    MAX_SLOTS (2) scheduled appointments regardless of who booked them.
    Cancelled and rejected appointments do NOT block slots.
    """
    return set(
        Appointment.objects.filter(
            appointment_date=appt_date,
            start_time=start_time,
            appointment_type=Appointment.TYPE_SCHEDULED,
        ).exclude(
            status__in=[Appointment.STATUS_CANCELLED, Appointment.STATUS_REJECTED],
        ).values_list("slot_number", flat=True)
    )


def _next_free_slot(appt_date, start_time):
    """Return the lowest free slot (1–2) or None if all taken."""
    taken = _taken_slots(appt_date, start_time)
    for n in range(1, MAX_SLOTS + 1):
        if n not in taken:
            return n
    return None


def _slot_data(appt_date, start_time):
    """Build the list of slot dicts for the JSON response."""
    taken = _taken_slots(appt_date, start_time)
    return [
        {"number": n, "available": n not in taken}
        for n in range(1, MAX_SLOTS + 1)
    ]


def _count_appointments_for_time(appt_date, start_time):
    """Count the number of walk-in appointments for a given date and time."""
    return Appointment.objects.filter(
        appointment_date=appt_date,
        start_time=start_time,
        appointment_type=Appointment.TYPE_WALK_IN,
    ).count()


def _round_to_half_hour(t: time) -> time:
    """Round a time down to the nearest 30-minute block."""
    minute = 0 if t.minute < 30 else 30
    return time(t.hour, minute)


# ─── Auth views ───────────────────────────────────────────────────────────────


def login_view(request):
    if request.user.is_authenticated:
        return redirect("/dashboard/")

    form = AuthenticationForm(request, data=request.POST or None)

    if request.method == "POST":
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect("/dashboard/")
        else:
            messages.error(request, "Invalid username or password.")

    return render(request, "login.html", {"form": form})


def logout_view(request):
    logout(request)
    return redirect("/")


@transaction.atomic
def register_pet_owner(request):
    if request.user.is_authenticated:
        return redirect("/dashboard/")

    if request.method == "POST":
        form = PetOwnerRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            Profile.objects.create(user=user, role=Profile.ROLE_PET_OWNER)
            login(request, user)
            return redirect("/dashboard/")
    else:
        form = PetOwnerRegistrationForm()

    return render(request, "register_pet_owner.html", {"form": form})


@transaction.atomic
def register_with_invite(request, token):
    if request.user.is_authenticated:
        return redirect("/dashboard/")

    invitation = get_object_or_404(Invitation, token=token, is_used=False)

    if User.objects.filter(email__iexact=invitation.email).exists():
        context = {
            "form": StaffInviteRegistrationForm(),
            "invitation": invitation,
            "invite_error": "An account with this email already exists.",
        }
        return render(request, "register_invited.html", context)

    if request.method == "POST":
        form = StaffInviteRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.email = invitation.email
            user.save()
            Profile.objects.create(user=user, role=invitation.role)
            invitation.is_used = True
            invitation.save(update_fields=["is_used"])
            login(request, user)
            return redirect("/dashboard/")
    else:
        form = StaffInviteRegistrationForm()

    return render(request, "register_invited.html", {"form": form, "invitation": invitation})


# ─── Invitations / user management ───────────────────────────────────────────


@login_required
def manage_invitations(request):
    is_manager = False
    try:
        profile = request.user.profile
        is_manager = profile.role == Profile.ROLE_MANAGER
    except Profile.DoesNotExist:
        is_manager = request.user.is_superuser

    if not is_manager:
        return HttpResponseForbidden("You do not have permission to manage invitations.")

    invite_message = None
    user_message = None

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "invite":
            form = InvitationForm(request.POST)
            if form.is_valid():
                invitation = form.save()
                invite_path = reverse("register_with_invite", args=[invitation.token])
                invite_url = request.build_absolute_uri(invite_path)
                invite_message = f"Invitation created for {invitation.email}. Share this link: {invite_url}"
                form = InvitationForm()
        elif action in {"deactivate", "reactivate", "change_role"}:
            form = InvitationForm()
            user_id = request.POST.get("user_id")
            try:
                target_user = User.objects.select_related("profile").get(pk=user_id)
            except (User.DoesNotExist, ValueError, TypeError):
                user_message = "Selected user could not be found."
            else:
                if getattr(target_user, "profile", None) and target_user.profile.role in {
                    Profile.ROLE_STAFF,
                    Profile.ROLE_MANAGER,
                }:
                    display_name = target_user.get_full_name() or target_user.username
                    if action == "deactivate":
                        target_user.is_active = False
                        target_user.save(update_fields=["is_active"])
                        user_message = f"{display_name} was deactivated."
                    elif action == "reactivate":
                        target_user.is_active = True
                        target_user.save(update_fields=["is_active"])
                        user_message = f"{display_name} was reactivated."
                    elif action == "change_role":
                        new_role = request.POST.get("role")
                        if new_role in {Profile.ROLE_STAFF, Profile.ROLE_MANAGER}:
                            target_user.profile.role = new_role
                            target_user.profile.save(update_fields=["role"])
                            user_message = f"{display_name} is now {target_user.profile.get_role_display()}."
                        else:
                            user_message = "Invalid role selected."
                else:
                    user_message = "This account cannot be managed from here."
    else:
        form = InvitationForm()

    invitations = Invitation.objects.order_by("-created_at")
    for invitation in invitations:
        invite_path = reverse("register_with_invite", args=[invitation.token])
        invitation.full_url = request.build_absolute_uri(invite_path)

    staff_manager_users = (
        User.objects.filter(profile__role__in=[Profile.ROLE_STAFF, Profile.ROLE_MANAGER])
        .select_related("profile")
        .order_by("date_joined")
    )

    return render(
        request,
        "manage_invitations.html",
        {
            "form": form,
            "invitations": invitations,
            "staff_manager_users": staff_manager_users,
            "invite_message": invite_message,
            "user_message": user_message,
        },
    )


# ─── Profile / pets ───────────────────────────────────────────────────────────


@login_required
def profile_edit(request):
    if not _is_pet_owner(request.user):
        return HttpResponseForbidden("Only pet owners can edit their profile.")
    profile = request.user.profile
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            return redirect("profile_edit")
    else:
        form = ProfileForm(instance=profile)
    return render(request, "profile_edit.html", {"form": form})


@login_required
def pet_list(request):
    if not _is_pet_owner(request.user):
        return HttpResponseForbidden("Only pet owners can view their pets.")
    pets = Pet.objects.filter(owner=request.user).order_by("name")

    # pass blank form so the "Add pet" modal works from this page
    from .forms import PetForm as PF
    form = PF()
    return render(request, "pet_list.html", {"pets": pets, "form": form})


@login_required
def pet_add(request):
    if not _is_pet_owner(request.user):
        return HttpResponseForbidden("Only pet owners can add pets.")
    if request.method == "POST":
        form = PetForm(request.POST)
        if form.is_valid():
            pet = form.save(commit=False)
            pet.owner = request.user
            pet.save()
            return redirect("pet_list")
    else:
        form = PetForm()
    return render(request, "pet_form.html", {"form": form, "title": "Add pet"})


@login_required
def pet_edit(request, pk):
    if not _is_pet_owner(request.user):
        return HttpResponseForbidden("Only pet owners can edit their pets.")
    pet = get_object_or_404(Pet, pk=pk, owner=request.user)
    if request.method == "POST":
        form = PetForm(request.POST, instance=pet)
        if form.is_valid():
            form.save()
            return redirect("pet_list")
    else:
        form = PetForm(instance=pet)
    return render(request, "pet_form.html", {"form": form, "title": "Edit pet", "pet": pet})


# ─── Appointments ─────────────────────────────────────────────────────────────


def _appointment_queryset(user):
    if _is_staff_or_manager(user):
        return Appointment.objects.select_related("owner", "pet", "staff").all()
    return Appointment.objects.filter(owner=user).select_related("owner", "pet", "staff")


# ── AJAX: available slots ──────────────────────────────────────────────────────

@login_required
@require_GET
def get_available_slots(request):
    """
    GET /accounts/appointments/slots/?date=YYYY-MM-DD&time=HH:MM&type=walk_in|scheduled
    For scheduled: Returns JSON: {"slots": [{"number": 1, "available": true}, ...]}
    For walk-in: Returns JSON: {"appointment_count": 3, "load_status": "moderate"}
    """
    date_str = request.GET.get("date", "")
    time_str = request.GET.get("time", "")
    appt_type = request.GET.get("type", "scheduled")

    # ── parse & validate date ──────────────────────────────────────────────
    try:
        appt_date = date.fromisoformat(date_str)
    except (ValueError, TypeError):
        return JsonResponse({"error": "Invalid date."}, status=400)

    today = date.today()
    if appt_date < today:
        return JsonResponse({"error": "Cannot book a past date."}, status=400)

    # ── parse & validate time ──────────────────────────────────────────────
    try:
        appt_time = time.fromisoformat(time_str)
    except (ValueError, TypeError):
        return JsonResponse({"error": "Invalid time."}, status=400)

    if appt_date == today:
        now = datetime.now().time()
        if appt_time <= now:
            return JsonResponse({"error": "Cannot book a past time slot."}, status=400)

    # ── Return different data based on appointment type ─────────────────────
    if appt_type == "walk_in":
        # For walk-ins, return the count of existing appointments
        count = _count_appointments_for_time(appt_date, appt_time)
        
        # Determine load status based on appointment count
        if count == 0:
            load_status = "light"
        elif count <= 2:
            load_status = "moderate"
        elif count <= 4:
            load_status = "heavy"
        else:
            load_status = "very_heavy"
        
        return JsonResponse({
            "appointment_count": count,
            "load_status": load_status,
        })
    else:
        # For scheduled appointments, return slot availability (1-2)
        slots = _slot_data(appt_date, appt_time)
        return JsonResponse({"slots": slots})


# ── Owner booking ──────────────────────────────────────────────────────────────

@login_required
def appointment_book(request):
    if not _is_pet_owner(request.user):
        return HttpResponseForbidden("Only pet owners can book appointments.")

    pets = Pet.objects.filter(owner=request.user).order_by("name")
    if not pets.exists():
        return redirect("pet_add")

    error = None

    if request.method == "POST":
        form = AppointmentBookingForm(request.POST, owner=request.user)
        slot_number = request.POST.get("slot_number")

        try:
            slot_number = int(slot_number)
            if not (1 <= slot_number <= MAX_SLOTS):
                raise ValueError
        except (ValueError, TypeError):
            error = "Please select a valid slot (1–2)."
            form.is_valid()  # populate cleaned_data even on slot error
        else:
            if form.is_valid():
                appt_date = form.cleaned_data["appointment_date"]
                appt_time = form.cleaned_data["start_time"]

                # ── past-date / past-time guard ────────────────────────────
                today = date.today()
                if appt_date < today:
                    error = "Cannot book an appointment in the past."
                elif appt_date == today and appt_time <= datetime.now().time():
                    error = "Cannot book a past time slot for today."
                else:
                    # ── atomic slot reservation ────────────────────────────
                    try:
                        with transaction.atomic():
                            taken = _taken_slots(appt_date, appt_time)
                            if len(taken) >= MAX_SLOTS:
                                error = "This time slot is fully booked. Please choose another."
                            elif slot_number in taken:
                                error = f"Slot {slot_number} was just taken. Please pick another slot."
                            else:
                                apt = form.save(commit=False)
                                apt.owner = request.user
                                apt.slot_number = slot_number
                                apt.status = Appointment.STATUS_PENDING
                                apt.appointment_type = Appointment.TYPE_SCHEDULED
                                apt.save()
                                return redirect("appointment_calendar")
                    except IntegrityError:
                        error = "That slot was just taken by another booking. Please try again."
    else:
        form = AppointmentBookingForm(owner=request.user)

    return render(request, "appointment_calendar.html", {
        "form": form,
        "pets": pets,
        "error": error,
        "is_staff": False,
        **_calendar_context(request),
    })


# ── Staff schedule / walk-in ───────────────────────────────────────────────────

@login_required
def appointment_schedule(request):
    if not _is_staff_or_manager(request.user):
        return HttpResponseForbidden("Only staff can schedule appointments.")

    error = None

    if request.method == "POST":
        form = AppointmentStaffForm(request.POST)
        appointment_type = request.POST.get("appointment_type", "scheduled")
        slot_number = request.POST.get("slot_number")

        # ── For walk-in appointments, slot_number is not required ──────────
        if appointment_type == "walk_in":
            slot_number = None
        else:
            # For scheduled appointments, validate slot_number
            try:
                slot_number = int(slot_number)
                if not (1 <= slot_number <= MAX_SLOTS):
                    raise ValueError
            except (ValueError, TypeError):
                error = "Please select a valid slot (1–2)."
                form.is_valid()
                slot_number = None

        if form.is_valid() and (appointment_type == "walk_in" or slot_number is not None):
            appt_date = form.cleaned_data["appointment_date"]
            appt_time = form.cleaned_data["start_time"]

            try:
                with transaction.atomic():
                    if appointment_type == "walk_in":
                        # ── Walk-in appointments: unlimited slots, auto-assign next slot number ──
                        # Only count walk-in appointments (separate from scheduled slots)
                        max_slot = Appointment.objects.filter(
                            appointment_date=appt_date,
                            start_time=appt_time,
                            appointment_type=Appointment.TYPE_WALK_IN,
                        ).aggregate(models.Max('slot_number'))['slot_number__max'] or 0
                        
                        apt = form.save(commit=False)
                        apt.staff = request.user
                        apt.slot_number = max_slot + 1  # Auto-assign next slot (unlimited)
                        apt.appointment_type = Appointment.TYPE_WALK_IN
                        apt.status = form.cleaned_data.get("status") or Appointment.STATUS_CONFIRMED
                        apt.save()
                        return redirect("appointment_manage")
                    else:
                        # ── Scheduled appointments: use existing slot constraint (MAX_SLOTS = 2) ──
                        taken = _taken_slots(appt_date, appt_time)
                        if len(taken) >= MAX_SLOTS:
                            error = "This time slot is fully booked."
                        elif slot_number in taken:
                            error = f"Slot {slot_number} was just taken. Please pick another."
                        else:
                            apt = form.save(commit=False)
                            apt.staff = request.user
                            apt.slot_number = slot_number
                            apt.appointment_type = Appointment.TYPE_SCHEDULED
                            apt.status = form.cleaned_data.get("status") or Appointment.STATUS_CONFIRMED
                            apt.save()
                            return redirect("appointment_manage")
            except IntegrityError:
                error = "That slot was just taken by another booking. Please try again."
    else:
        form = AppointmentStaffForm(initial={"appointment_type": Appointment.TYPE_WALK_IN, "status": Appointment.STATUS_CONFIRMED})

    owners = User.objects.filter(profile__role=Profile.ROLE_PET_OWNER).order_by("username")
    pets = Pet.objects.select_related("owner").order_by("name")

    return render(request, "appointment_calendar.html", {
        "staff_form": form,
        "owners": owners,
        "pets": pets,
        "staff_error": error,
        "is_staff": True,
        **_calendar_context(request),
    })


# ── Calendar helper ────────────────────────────────────────────────────────────

def _calendar_context(request):
    year = int(request.GET.get("year", date.today().year))
    month = int(request.GET.get("month", date.today().month))
    try:
        cal_date = date(year, month, 1)
    except ValueError:
        cal_date = date.today().replace(day=1)

    if month == 1:
        prev_month = date(year - 1, 12, 1)
        next_month = date(year, 2, 1)
    else:
        prev_month = date(year, month - 1, 1)
        next_month = date(year, month + 1, 1) if month < 12 else date(year + 1, 1, 1)

    start = cal_date
    if cal_date.month == 12:
        end = date(cal_date.year + 1, 1, 1) - timedelta(days=1)
    else:
        end = date(cal_date.year, cal_date.month + 1, 1) - timedelta(days=1)

    appointments = _appointment_queryset(request.user).filter(
        appointment_date__gte=start,
        appointment_date__lte=end,
    ).order_by("appointment_date", "start_time")

    by_date = {}
    for apt in appointments:
        key = apt.appointment_date.isoformat()
        by_date.setdefault(key, []).append(apt)

    cal_obj = calendar.Calendar(firstweekday=6)
    weeks = cal_obj.monthdatescalendar(cal_date.year, cal_date.month)
    calendar_weeks = [
        [(d, by_date.get(d.isoformat(), [])) for d in week]
        for week in weeks
    ]

    return {
        "cal_date": cal_date,
        "prev_month": prev_month,
        "next_month": next_month,
        "calendar_weeks": calendar_weeks,
        "today": date.today(),
    }


@login_required
def appointment_calendar(request):
    pets = Pet.objects.filter(owner=request.user).order_by("name") if _is_pet_owner(request.user) else Pet.objects.none()
    owners = User.objects.filter(profile__role=Profile.ROLE_PET_OWNER).order_by("username") if _is_staff_or_manager(request.user) else User.objects.none()
    all_pets = Pet.objects.select_related("owner").order_by("name") if _is_staff_or_manager(request.user) else Pet.objects.none()

    ctx = {
        "form": AppointmentBookingForm(owner=request.user),
        "staff_form": AppointmentStaffForm(initial={"appointment_type": Appointment.TYPE_WALK_IN}),
        "pets": pets,
        "owners": owners,
        "all_pets": all_pets,
        "is_staff": _is_staff_or_manager(request.user),
        **_calendar_context(request),
    }
    return render(request, "appointment_calendar.html", ctx)


@login_required
def appointment_queue(request):
    day_str = request.GET.get("date")
    if day_str:
        try:
            view_date = date.fromisoformat(day_str)
        except (ValueError, TypeError):
            view_date = date.today()
    else:
        view_date = date.today()

    return render(request, "appointment_queue.html", {
        "view_date": view_date,
        "is_staff": _is_staff_or_manager(request.user),
    })


@login_required
@require_GET
def queue_data(request):
    """API endpoint returning current queue state as JSON for real-time polling."""
    day_str = request.GET.get("date")
    if day_str:
        try:
            view_date = date.fromisoformat(day_str)
        except (ValueError, TypeError):
            view_date = date.today()
    else:
        view_date = date.today()

    is_today = view_date == date.today()
    current_user_id = request.user.id
    is_staff = _is_staff_or_manager(request.user)

    # ── Helper to serialise an appointment row ──
    def _apt_to_dict(apt, queue_number=None):
        species = apt.pet.species if apt.pet else "other"
        return {
            "id": apt.id,
            "queue_number": queue_number,
            "pet_name": apt.pet.name if apt.pet else "Walk-in",
            "species": species,
            "owner_id": apt.owner_id,
            "owner_name": apt.owner.get_full_name() or apt.owner.username,
            "appointment_type": apt.get_appointment_type_display(),
            "reason": apt.reason or "",
            "start_time": apt.start_time.strftime("%I:%M").lstrip("0") if hasattr(apt.start_time, 'strftime') else str(apt.start_time),
            "start_time_ampm": apt.start_time.strftime("%p") if hasattr(apt.start_time, 'strftime') else "",
            "status": apt.status,
            "status_display": apt.get_status_display(),
        }

    # ══════════════════════════════════════════════════════════════════
    # NON-TODAY: schedule-only view — no live queue logic
    # ══════════════════════════════════════════════════════════════════
    if not is_today:
        schedule_qs = Appointment.objects.select_related("owner", "pet", "staff").filter(
            appointment_date=view_date,
        ).order_by("start_time", "slot_number")

        if not is_staff:
            schedule_qs = schedule_qs.filter(owner=request.user)

        scheduled_items = [_apt_to_dict(apt) for apt in schedule_qs]

        return JsonResponse({
            "view_date": view_date.isoformat(),
            "view_date_display": view_date.strftime("%A, %B %d, %Y"),
            "is_today": False,
            "scheduled": scheduled_items,
            "total_count": len(scheduled_items),
            "is_staff": is_staff,
            "current_user_id": current_user_id,
            # These are intentionally empty for non-today
            "now_serving": None,
            "waiting": [],
            "waiting_count": 0,
            "my_queue_info": [],
        })

    # ══════════════════════════════════════════════════════════════════
    # TODAY: full live-queue logic
    # ══════════════════════════════════════════════════════════════════
    queue_qs = Appointment.objects.select_related("owner", "pet", "staff").filter(
        appointment_date=view_date,
        status=Appointment.STATUS_CONFIRMED,
    ).order_by("start_time", "slot_number")

    # Count already-served appointments today for running queue numbering
    served_count = Appointment.objects.filter(
        appointment_date=view_date,
        status__in=[Appointment.STATUS_COMPLETED, Appointment.STATUS_NO_SHOW],
    ).count()

    items = []
    my_positions = []  # 0-based positions of the current owner in the queue

    for idx, apt in enumerate(queue_qs):
        queue_number = served_count + idx + 1  # running number for the day
        items.append(_apt_to_dict(apt, queue_number))
        if apt.owner_id == current_user_id:
            my_positions.append(idx)

    now_serving = items[0] if items else None
    waiting = items[1:] if len(items) > 1 else []

    # Build owner-facing position summary
    my_queue_info = []
    for pos in my_positions:
        item = items[pos]
        my_queue_info.append({
            "position": pos + 1,        # 1-based
            "ahead": pos,               # how many before this one
            "pet_name": item["pet_name"],
            "is_now_serving": pos == 0,
            "appointment_type": item["appointment_type"],
            "reason": item["reason"],
            "species": item["species"],
            "start_time": item["start_time"],
            "start_time_ampm": item["start_time_ampm"],
            "status": item["status"],
            "status_display": item["status_display"],
        })

    # For non-staff, only send their own items (no other clients visible)
    if is_staff:
        resp_now_serving = now_serving
        resp_waiting = waiting
    else:
        resp_now_serving = None
        resp_waiting = []

    return JsonResponse({
        "view_date": view_date.isoformat(),
        "view_date_display": view_date.strftime("%A, %B %d, %Y"),
        "is_today": True,
        "now_serving": resp_now_serving,
        "waiting": resp_waiting,
        "total_count": len(items),
        "waiting_count": len(waiting),
        "current_user_id": current_user_id,
        "my_queue_info": my_queue_info,
        "is_staff": is_staff,
    })


@login_required
@require_POST
def queue_action(request):
    """Handle Completed / No Show actions from the queue view."""
    if not _is_staff_or_manager(request.user):
        return JsonResponse({"error": "Only staff can perform queue actions."}, status=403)

    apt_id = request.POST.get("appointment_id")
    action = request.POST.get("action")

    if not apt_id or action not in ("completed", "no_show"):
        return JsonResponse({"error": "Invalid request."}, status=400)

    apt = get_object_or_404(Appointment, pk=apt_id)

    if action == "completed":
        apt.status = Appointment.STATUS_COMPLETED
    elif action == "no_show":
        apt.status = Appointment.STATUS_NO_SHOW

    apt.staff = request.user
    apt.save(update_fields=["status", "staff", "updated_at"])

    return JsonResponse({"success": True, "new_status": apt.status})


@login_required
@require_POST
def appointment_cancel(request):
    """Allow a pet owner to cancel their own pending or confirmed appointment."""
    apt_id = request.POST.get("appointment_id")
    if not apt_id:
        return JsonResponse({"error": "Missing appointment ID."}, status=400)

    apt = get_object_or_404(Appointment, pk=apt_id)

    # Staff can cancel any; owners can only cancel their own
    if not _is_staff_or_manager(request.user) and apt.owner_id != request.user.id:
        return JsonResponse({"error": "You can only cancel your own appointments."}, status=403)

    if apt.status not in (Appointment.STATUS_PENDING, Appointment.STATUS_CONFIRMED):
        return JsonResponse({"error": "Only pending or confirmed appointments can be cancelled."}, status=400)

    apt.status = Appointment.STATUS_CANCELLED
    apt.slot_number = None
    apt.save(update_fields=["status", "slot_number", "updated_at"])

    # If called via AJAX, return JSON; otherwise redirect
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"success": True})
    return redirect("appointment_calendar")


@login_required
def appointment_manage(request):
    if not _is_staff_or_manager(request.user):
        return HttpResponseForbidden("Only staff can manage appointments.")

    if request.method == "POST":
        action = request.POST.get("action")
        apt_id = request.POST.get("appointment_id")
        if action and apt_id:
            apt = get_object_or_404(Appointment, pk=apt_id)
            if action == "confirm":
                apt.status = Appointment.STATUS_CONFIRMED
                apt.staff = request.user
                apt.save(update_fields=["status", "staff", "updated_at"])
            elif action == "reject":
                apt.status = Appointment.STATUS_REJECTED
                apt.slot_number = None
                apt.staff = request.user
                apt.save(update_fields=["status", "slot_number", "staff", "updated_at"])
            elif action == "cancel":
                apt.status = Appointment.STATUS_CANCELLED
                apt.slot_number = None
                apt.staff = request.user
                apt.save(update_fields=["status", "slot_number", "staff", "updated_at"])
            elif action == "complete":
                apt.status = Appointment.STATUS_COMPLETED
                apt.staff = request.user
                apt.save(update_fields=["status", "staff", "updated_at"])
            elif action == "no_show":
                apt.status = Appointment.STATUS_NO_SHOW
                apt.staff = request.user
                apt.save(update_fields=["status", "staff", "updated_at"])

    appointments = Appointment.objects.select_related("owner", "pet", "staff").order_by(
        "-appointment_date", "-start_time", "slot_number"
    )

    # Statistics
    from django.db.models import Count
    stats = Appointment.objects.aggregate(
        total=Count("id"),
        pending=Count("id", filter=models.Q(status=Appointment.STATUS_PENDING)),
        confirmed=Count("id", filter=models.Q(status=Appointment.STATUS_CONFIRMED)),
        completed=Count("id", filter=models.Q(status=Appointment.STATUS_COMPLETED)),
        cancelled=Count("id", filter=models.Q(status=Appointment.STATUS_CANCELLED)),
        rejected=Count("id", filter=models.Q(status=Appointment.STATUS_REJECTED)),
        no_show=Count("id", filter=models.Q(status=Appointment.STATUS_NO_SHOW)),
    )

    return render(request, "appointment_manage.html", {
        "appointments": appointments,
        "form": AppointmentStaffForm(),
        "stats": stats,
    })


# ─── Walk-in client registration (staff) ──────────────────────────────────────


@login_required
@transaction.atomic
def walkin_register(request):
    """Staff registers a new walk-in client and their pet."""
    if not _is_staff_or_manager(request.user):
        return HttpResponseForbidden("Only staff can register walk-in clients.")

    success_info = None

    if request.method == "POST":
        client_form = WalkInClientForm(request.POST)
        pet_form = WalkInPetForm(request.POST)

        if client_form.is_valid() and pet_form.is_valid():
            # Create user with unusable password (can't log in until activated)
            email = client_form.cleaned_data.get("email") or ""
            first = client_form.cleaned_data["first_name"]
            last = client_form.cleaned_data["last_name"]

            # Generate a unique username from first+last name
            base_username = f"{first.lower()}.{last.lower()}"[:30]
            base_username = "".join(c for c in base_username if c.isalnum() or c == ".")
            username = base_username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1

            user = User(
                username=username,
                first_name=first,
                last_name=last,
                email=email,
            )
            user.set_unusable_password()
            user.save()

            # Create profile
            Profile.objects.create(
                user=user,
                role=Profile.ROLE_PET_OWNER,
                phone=client_form.cleaned_data.get("phone", ""),
                address=client_form.cleaned_data.get("address", ""),
                is_profile_completed=True,
            )

            # Create pet
            pet = pet_form.save(commit=False)
            pet.owner = user
            pet.save()

            # Create activation token
            registration = WalkInRegistration.objects.create(
                user=user,
                created_by=request.user,
            )

            activate_path = reverse("walkin_activate", args=[registration.token])
            activate_url = request.build_absolute_uri(activate_path)

            qr_path = reverse("walkin_qr_image", args=[registration.token])
            qr_url = request.build_absolute_uri(qr_path)
            print_path = reverse("walkin_print_card", args=[registration.token])
            print_url = request.build_absolute_uri(print_path)

            success_info = {
                "client_name": user.get_full_name(),
                "pet_name": pet.name,
                "activate_url": activate_url,
                "qr_url": qr_url,
                "print_url": print_url,
            }

            # Reset forms for next registration
            client_form = WalkInClientForm()
            pet_form = WalkInPetForm()
    else:
        client_form = WalkInClientForm()
        pet_form = WalkInPetForm()

    # List recent walk-in registrations created by any staff
    recent_registrations = (
        WalkInRegistration.objects.select_related("user", "user__profile", "created_by")
        .order_by("-created_at")[:20]
    )

    return render(request, "walkin_register.html", {
        "client_form": client_form,
        "pet_form": pet_form,
        "success_info": success_info,
        "recent_registrations": recent_registrations,
    })


# ─── Walk-in account activation (client) ─────────────────────────────────────


@transaction.atomic
def walkin_activate(request, token):
    """Walk-in client sets username & password to activate their account."""
    if request.user.is_authenticated:
        return redirect("/dashboard/")

    registration = get_object_or_404(WalkInRegistration, token=token)

    if registration.is_activated:
        return render(request, "walkin_activate.html", {
            "already_activated": True,
        })

    user = registration.user

    if request.method == "POST":
        form = WalkInActivationForm(request.POST, instance=user)
        if form.is_valid():
            activated_user = form.save()
            registration.is_activated = True
            registration.activated_at = timezone.now()
            registration.save(update_fields=["is_activated", "activated_at"])
            login(request, activated_user)
            messages.success(request, "Your account has been activated! Welcome to Pawmily.")
            return redirect("/dashboard/")
    else:
        form = WalkInActivationForm(instance=user)

    return render(request, "walkin_activate.html", {
        "form": form,
        "registration": registration,
        "user_info": user,
    })


# ─── Link existing walk-in record to new account ─────────────────────────────


@transaction.atomic
def register_pet_owner_link(request):
    """
    During normal pet-owner registration, allow linking to an existing
    walk-in record by email.
    """
    if request.user.is_authenticated:
        return redirect("/dashboard/")

    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        if email:
            try:
                walkin_reg = WalkInRegistration.objects.select_related("user").get(
                    user__email__iexact=email,
                    is_activated=False,
                )
                # Redirect to the activation page for this walk-in record
                return redirect("walkin_activate", token=walkin_reg.token)
            except WalkInRegistration.DoesNotExist:
                messages.error(
                    request,
                    "No walk-in record found for this email. "
                    "Please register a new account or check the email address."
                )

    return render(request, "walkin_link.html")


# ─── Walk-in QR code generation ───────────────────────────────────────────────


@login_required
@require_GET
def walkin_qr_image(request, token):
    """Return a QR code PNG image for the activation link."""
    if not _is_staff_or_manager(request.user):
        return HttpResponseForbidden("Only staff can generate QR codes.")

    registration = get_object_or_404(WalkInRegistration, token=token)
    activate_path = reverse("walkin_activate", args=[registration.token])
    activate_url = request.build_absolute_uri(activate_path)

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(activate_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return HttpResponse(buf.getvalue(), content_type="image/png")


@login_required
def walkin_print_card(request, token):
    """Render a print-friendly card with QR code for the client."""
    if not _is_staff_or_manager(request.user):
        return HttpResponseForbidden("Only staff can print activation cards.")

    registration = get_object_or_404(
        WalkInRegistration.objects.select_related("user"),
        token=token,
    )
    activate_path = reverse("walkin_activate", args=[registration.token])
    activate_url = request.build_absolute_uri(activate_path)
    qr_url = request.build_absolute_uri(
        reverse("walkin_qr_image", args=[registration.token])
    )

    return render(request, "walkin_print_card.html", {
        "registration": registration,
        "activate_url": activate_url,
        "qr_url": qr_url,
    })


# ─── Medical Records ─────────────────────────────────────────────────────────


def _can_view_medical_records(user, pet):
    """Staff/managers can view any pet's records; owners can view their own."""
    if _is_staff_or_manager(user):
        return True
    return pet.owner_id == user.id


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