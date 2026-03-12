import calendar
import json
from datetime import date, datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, models, transaction
from django.db.models import Count, Q
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST
from pawmily.pagination import paginate_queryset

from accounts.models import Pet, Profile
from accounts.views import _is_pet_owner, _is_staff_or_manager
from billing.models import BillingRecord
from billing.views import create_billing_for_appointment

from .forms import AppointmentBookingForm, AppointmentStaffForm
from .models import MAX_SLOTS, Appointment

User = get_user_model()


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _taken_slots(appt_date, start_time):
    """Return a set of slot numbers already booked for scheduled appointments at a date/time."""
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

    try:
        appt_date = date.fromisoformat(date_str)
    except (ValueError, TypeError):
        return JsonResponse({"error": "Invalid date."}, status=400)

    today = date.today()
    if appt_date < today:
        return JsonResponse({"error": "Cannot book a past date."}, status=400)

    try:
        appt_time = time.fromisoformat(time_str)
    except (ValueError, TypeError):
        return JsonResponse({"error": "Invalid time."}, status=400)

    if appt_date == today:
        now = datetime.now().time()
        if appt_time <= now:
            return JsonResponse({"error": "Cannot book a past time slot."}, status=400)

    if appt_type == "walk_in":
        count = _count_appointments_for_time(appt_date, appt_time)

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
            form.is_valid()
        else:
            if form.is_valid():
                appt_date = form.cleaned_data["appointment_date"]
                appt_time = form.cleaned_data["start_time"]

                today = date.today()
                if appt_date < today:
                    error = "Cannot book an appointment in the past."
                elif appt_date == today and appt_time <= datetime.now().time():
                    error = "Cannot book a past time slot for today."
                else:
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

        if appointment_type == "walk_in":
            slot_number = None
        else:
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
                        max_slot = Appointment.objects.filter(
                            appointment_date=appt_date,
                            start_time=appt_time,
                            appointment_type=Appointment.TYPE_WALK_IN,
                        ).aggregate(models.Max('slot_number'))['slot_number__max'] or 0

                        apt = form.save(commit=False)
                        apt.staff = request.user
                        apt.slot_number = max_slot + 1
                        apt.appointment_type = Appointment.TYPE_WALK_IN
                        apt.status = form.cleaned_data.get("status") or Appointment.STATUS_CONFIRMED
                        apt.save()
                        return redirect("appointment_manage")
                    else:
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
    ).exclude(
        billing_record__payment_status=BillingRecord.PAYMENT_STATUS_PAID,
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
            "now_serving": None,
            "waiting": [],
            "waiting_count": 0,
            "my_queue_info": [],
        })

    queue_qs = Appointment.objects.select_related("owner", "pet", "staff").filter(
        appointment_date=view_date,
        status=Appointment.STATUS_CONFIRMED,
    ).order_by("start_time", "slot_number")

    served_count = Appointment.objects.filter(
        appointment_date=view_date,
        status__in=[Appointment.STATUS_COMPLETED, Appointment.STATUS_NO_SHOW],
    ).count()

    items = []
    my_positions = []

    for idx, apt in enumerate(queue_qs):
        queue_number = served_count + idx + 1
        items.append(_apt_to_dict(apt, queue_number))
        if apt.owner_id == current_user_id:
            my_positions.append(idx)

    now_serving = items[0] if items else None
    waiting = items[1:] if len(items) > 1 else []

    my_queue_info = []
    for pos in my_positions:
        item = items[pos]
        my_queue_info.append({
            "position": pos + 1,
            "ahead": pos,
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

    if action == "completed":
        create_billing_for_appointment(apt, created_by=request.user)
        redirect_url = reverse("finalize_step1", args=[apt.pk])
        return JsonResponse({"success": True, "new_status": apt.status, "redirect_url": redirect_url})

    return JsonResponse({"success": True, "new_status": apt.status})


@login_required
@require_POST
def appointment_cancel(request):
    """Allow a pet owner to cancel their own pending or confirmed appointment."""
    apt_id = request.POST.get("appointment_id")
    if not apt_id:
        return JsonResponse({"error": "Missing appointment ID."}, status=400)

    apt = get_object_or_404(Appointment, pk=apt_id)

    if not _is_staff_or_manager(request.user) and apt.owner_id != request.user.id:
        return JsonResponse({"error": "You can only cancel your own appointments."}, status=403)

    if apt.status not in (Appointment.STATUS_PENDING, Appointment.STATUS_CONFIRMED):
        return JsonResponse({"error": "Only pending or confirmed appointments can be cancelled."}, status=400)

    apt.status = Appointment.STATUS_CANCELLED
    apt.slot_number = None
    apt.save(update_fields=["status", "slot_number", "updated_at"])

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
                create_billing_for_appointment(apt, created_by=request.user)
                return redirect("finalize_step1", appointment_id=apt.pk)
            elif action == "no_show":
                apt.status = Appointment.STATUS_NO_SHOW
                apt.staff = request.user
                apt.save(update_fields=["status", "staff", "updated_at"])

    appointments = Appointment.objects.select_related("owner", "pet", "staff").order_by(
        "-appointment_date", "-start_time", "slot_number"
    )
    appointments_page_obj, appointments_pagination_query = paginate_queryset(
        request,
        appointments,
        per_page=12,
        page_param="appointments_page",
    )

    stats = Appointment.objects.aggregate(
        total=Count("id"),
        pending=Count("id", filter=Q(status=Appointment.STATUS_PENDING)),
        confirmed=Count("id", filter=Q(status=Appointment.STATUS_CONFIRMED)),
        completed=Count("id", filter=Q(status=Appointment.STATUS_COMPLETED)),
        cancelled=Count("id", filter=Q(status=Appointment.STATUS_CANCELLED)),
        rejected=Count("id", filter=Q(status=Appointment.STATUS_REJECTED)),
        no_show=Count("id", filter=Q(status=Appointment.STATUS_NO_SHOW)),
    )

    return render(request, "appointment_manage.html", {
        "appointments": appointments_page_obj,
        "appointments_page_obj": appointments_page_obj,
        "appointments_pagination_query": appointments_pagination_query,
        "form": AppointmentStaffForm(),
        "stats": stats,
    })
