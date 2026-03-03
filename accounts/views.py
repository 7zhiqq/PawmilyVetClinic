import calendar
from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import (
    AppointmentBookingForm,
    AppointmentStaffForm,
    InvitationForm,
    PetForm,
    PetOwnerRegistrationForm,
    ProfileForm,
    StaffInviteRegistrationForm,
)
from .models import Appointment, Invitation, Pet, Profile

User = get_user_model()


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

    # One user per email: do not create a duplicate account
    if User.objects.filter(email__iexact=invitation.email).exists():
        context = {
            "form": StaffInviteRegistrationForm(),
            "invitation": invitation,
            "invite_error": "An account with this email already exists. One email per user.",
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

    context = {
        "form": form,
        "invitation": invitation,
    }
    return render(request, "register_invited.html", context)


@login_required
def manage_invitations(request):
    # Only managers (or superusers) are allowed here.
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
                # Only allow managing staff and managers
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
    return render(request, "pet_list.html", {"pets": pets})


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


@login_required
def appointment_book(request):
    if not _is_pet_owner(request.user):
        return HttpResponseForbidden("Only pet owners can book appointments.")
    pets = Pet.objects.filter(owner=request.user).order_by("name")
    if not pets.exists():
        return redirect("pet_add")
    if request.method == "POST":
        form = AppointmentBookingForm(request.POST, owner=request.user)
        if form.is_valid():
            apt = form.save(commit=False)
            apt.owner = request.user
            apt.status = Appointment.STATUS_PENDING
            apt.appointment_type = Appointment.TYPE_SCHEDULED
            apt.save()
            return redirect("appointment_calendar")
    else:
        form = AppointmentBookingForm(owner=request.user)
    return render(request, "appointment_book.html", {"form": form})


@login_required
def appointment_calendar(request):
    year = int(request.GET.get("year", date.today().year))
    month = int(request.GET.get("month", date.today().month))
    try:
        cal_date = date(year, month, 1)
    except ValueError:
        cal_date = date.today()
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
        if key not in by_date:
            by_date[key] = []
        by_date[key].append(apt)

    cal = calendar.Calendar(firstweekday=6)  # Sunday first
    weeks = cal.monthdatescalendar(cal_date.year, cal_date.month)
    calendar_weeks = [
        [(d, by_date.get(d.isoformat(), [])) for d in week]
        for week in weeks
    ]
    context = {
        "cal_date": cal_date,
        "prev_month": prev_month,
        "next_month": next_month,
        "calendar_weeks": calendar_weeks,
        "is_staff": _is_staff_or_manager(request.user),
    }
    return render(request, "appointment_calendar.html", context)


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
    appointments = _appointment_queryset(request.user).filter(
        appointment_date=view_date,
    ).order_by("start_time")
    context = {
        "view_date": view_date,
        "appointments": appointments,
        "is_staff": _is_staff_or_manager(request.user),
    }
    return render(request, "appointment_queue.html", context)


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
                apt.staff = request.user
                apt.save(update_fields=["status", "staff", "updated_at"])
            elif action == "complete":
                apt.status = Appointment.STATUS_COMPLETED
                apt.staff = request.user
                apt.save(update_fields=["status", "staff", "updated_at"])
    appointments = Appointment.objects.select_related("owner", "pet", "staff").order_by(
        "-appointment_date", "-start_time"
    )
    context = {"appointments": appointments, "form": AppointmentStaffForm()}
    return render(request, "appointment_manage.html", context)


@login_required
def appointment_schedule(request):
    if not _is_staff_or_manager(request.user):
        return HttpResponseForbidden("Only staff can schedule appointments.")
    if request.method == "POST":
        form = AppointmentStaffForm(request.POST)
        if form.is_valid():
            apt = form.save(commit=False)
            apt.staff = request.user
            apt.appointment_type = (
                Appointment.TYPE_WALK_IN
                if form.cleaned_data.get("appointment_type") == Appointment.TYPE_WALK_IN
                else Appointment.TYPE_SCHEDULED
            )
            apt.status = form.cleaned_data.get("status") or Appointment.STATUS_CONFIRMED
            apt.save()
            return redirect("appointment_manage")
    else:
        form = AppointmentStaffForm(initial={"appointment_type": Appointment.TYPE_WALK_IN})
    return render(request, "appointment_schedule.html", {"form": form})