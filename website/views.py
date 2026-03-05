from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render


def landing_page(request):
    if request.user.is_authenticated:
        return redirect("/dashboard/")
    return render(request, "landing.html")


from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from datetime import date

from django.contrib.auth import get_user_model

from accounts.forms import PetForm
from accounts.models import Pet, Profile
from appointments.forms import AppointmentBookingForm, AppointmentStaffForm
from appointments.models import Appointment

User = get_user_model()


def landing_page(request):
    if request.user.is_authenticated:
        return redirect("/dashboard/")
    return render(request, "landing.html")


@login_required
def dashboard(request):
    profile = getattr(request.user, "profile", None)
    role = getattr(profile, "role", None)

    context = {"role": role}

    if role == Profile.ROLE_PET_OWNER:
        context["pets"] = Pet.objects.filter(owner=request.user).order_by("name")
        context["book_form"] = AppointmentBookingForm(owner=request.user)
        context["book_error"] = None
        context["pet_form"]  = PetForm()

        # Upcoming appointments for the Reminders card
        context["upcoming_appointments"] = (
            Appointment.objects.select_related("pet")
            .filter(
                owner=request.user,
                appointment_date__gte=date.today(),
                status__in=[
                    Appointment.STATUS_PENDING,
                    Appointment.STATUS_CONFIRMED,
                ],
            )
            .order_by("appointment_date", "start_time")[:5]
        )

        # Queue View: owner's position in today's queue
        today = date.today()
        confirmed_today = list(
            Appointment.objects.select_related("pet")
            .filter(
                appointment_date=today,
                status=Appointment.STATUS_CONFIRMED,
            )
            .order_by("start_time", "slot_number")
        )
        served_count = Appointment.objects.filter(
            appointment_date=today,
            status__in=[Appointment.STATUS_COMPLETED, Appointment.STATUS_NO_SHOW],
        ).count()

        my_queue_items = []
        now_serving_number = (served_count + 1) if confirmed_today else None
        for idx, apt in enumerate(confirmed_today):
            queue_number = served_count + idx + 1
            if apt.owner_id == request.user.id:
                my_queue_items.append({
                    "pet_name": apt.pet.name if apt.pet else "Walk-in",
                    "species": apt.pet.species if apt.pet else "other",
                    "queue_number": queue_number,
                    "position": idx + 1,
                    "ahead": idx,
                    "is_now_serving": idx == 0,
                    "reason": apt.reason or "",
                    "start_time": apt.start_time,
                })
        context["my_queue_items"] = my_queue_items
        context["now_serving_number"] = now_serving_number

    elif role in (Profile.ROLE_STAFF, Profile.ROLE_MANAGER):
        from django.db.models import Count, Q
        today = date.today()

        context["owners"]     = User.objects.filter(profile__role=Profile.ROLE_PET_OWNER).order_by("username")
        context["pets"]       = Pet.objects.select_related("owner").order_by("owner__username", "name")
        context["staff_form"] = AppointmentStaffForm(initial={"appointment_type": Appointment.TYPE_WALK_IN})

        # Today's stats for the aside panel (staff)
        context["today_stats"] = Appointment.objects.filter(appointment_date=today).aggregate(
            total=Count("id"),
            pending=Count("id", filter=Q(status=Appointment.STATUS_PENDING)),
            confirmed=Count("id", filter=Q(status=Appointment.STATUS_CONFIRMED)),
            completed=Count("id", filter=Q(status=Appointment.STATUS_COMPLETED)),
        )

        if role == Profile.ROLE_MANAGER:
            # All-time clinic stats for manager panel
            context["clinic_stats"] = {
                "appointments": Appointment.objects.count(),
                "completed": Appointment.objects.filter(status=Appointment.STATUS_COMPLETED).count(),
                "pet_owners": User.objects.filter(profile__role=Profile.ROLE_PET_OWNER).count(),
                "staff_active": User.objects.filter(
                    profile__role__in=[Profile.ROLE_STAFF, Profile.ROLE_MANAGER],
                    is_active=True,
                ).count(),
            }

    return render(request, "dashboard.html", context)




