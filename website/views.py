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
from django.db.models import Q

from accounts.forms import PetForm, ProfileForm
from accounts.models import Pet, Profile
from appointments.forms import AppointmentBookingForm, AppointmentStaffForm
from appointments.models import Appointment
from records.models import VaccinationSchedule, FollowUpReminder

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
        context["profile_form"] = ProfileForm(instance=profile)

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

        # Upcoming vaccinations and follow-ups for all user's pets
        user_pets = Pet.objects.filter(owner=request.user)
        context["upcoming_vaccinations"] = VaccinationSchedule.objects.filter(
            pet__in=user_pets,
            status__in=[
                VaccinationSchedule.STATUS_PENDING,
                VaccinationSchedule.STATUS_DUE,
                VaccinationSchedule.STATUS_OVERDUE,
            ]
        ).select_related("pet", "vaccine_type").order_by("next_due_date")[:5]
        
        context["upcoming_followups"] = FollowUpReminder.objects.filter(
            pet__in=user_pets,
            status__in=[
                FollowUpReminder.STATUS_PENDING,
                FollowUpReminder.STATUS_DUE,
                FollowUpReminder.STATUS_OVERDUE,
            ]
        ).select_related("pet", "medical_record").order_by("follow_up_date")[:5]

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
        from django.db.models import Count
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

        # Upcoming vaccinations and follow-ups for all pets (staff/manager view)
        context["upcoming_vaccinations"] = VaccinationSchedule.objects.filter(
            status__in=[
                VaccinationSchedule.STATUS_DUE,
                VaccinationSchedule.STATUS_OVERDUE,
            ]
        ).select_related("pet", "vaccine_type").order_by("next_due_date")[:10]
        
        context["upcoming_followups"] = FollowUpReminder.objects.filter(
            status__in=[
                FollowUpReminder.STATUS_DUE,
                FollowUpReminder.STATUS_OVERDUE,
            ]
        ).select_related("pet", "medical_record").order_by("follow_up_date")[:10]

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


@login_required
def reminders_view(request):
    """Display all vaccination and follow-up reminders for the user."""
    profile = getattr(request.user, "profile", None)
    role = getattr(profile, "role", None)
    
    context = {"role": role, "today": date.today()}
    
    if role == Profile.ROLE_PET_OWNER:
        # Show reminders for all user's pets
        user_pets = Pet.objects.filter(owner=request.user)
        
        context["vaccinations_overdue"] = VaccinationSchedule.objects.filter(
            pet__in=user_pets,
            status=VaccinationSchedule.STATUS_OVERDUE,
        ).select_related("pet", "vaccine_type").order_by("next_due_date")
        
        context["vaccinations_due"] = VaccinationSchedule.objects.filter(
            pet__in=user_pets,
            status=VaccinationSchedule.STATUS_DUE,
        ).select_related("pet", "vaccine_type").order_by("next_due_date")
        
        context["vaccinations_pending"] = VaccinationSchedule.objects.filter(
            pet__in=user_pets,
            status=VaccinationSchedule.STATUS_PENDING,
        ).select_related("pet", "vaccine_type").order_by("next_due_date")
        
        context["followups_overdue"] = FollowUpReminder.objects.filter(
            pet__in=user_pets,
            status=FollowUpReminder.STATUS_OVERDUE,
        ).select_related("pet", "medical_record")
        
        context["followups_due"] = FollowUpReminder.objects.filter(
            pet__in=user_pets,
            status=FollowUpReminder.STATUS_DUE,
        ).select_related("pet", "medical_record").order_by("follow_up_date")
        
        context["followups_pending"] = FollowUpReminder.objects.filter(
            pet__in=user_pets,
            status=FollowUpReminder.STATUS_PENDING,
        ).select_related("pet", "medical_record").order_by("follow_up_date")
        
    elif role in (Profile.ROLE_STAFF, Profile.ROLE_MANAGER):
        # Show all overdue and due reminders across all pets
        context["vaccinations_overdue"] = VaccinationSchedule.objects.filter(
            status=VaccinationSchedule.STATUS_OVERDUE,
        ).select_related("pet", "vaccine_type").order_by("next_due_date")
        
        context["vaccinations_due"] = VaccinationSchedule.objects.filter(
            status=VaccinationSchedule.STATUS_DUE,
        ).select_related("pet", "vaccine_type").order_by("next_due_date")
        
        context["followups_overdue"] = FollowUpReminder.objects.filter(
            status=FollowUpReminder.STATUS_OVERDUE,
        ).select_related("pet", "medical_record")
        
        context["followups_due"] = FollowUpReminder.objects.filter(
            status=FollowUpReminder.STATUS_DUE,
        ).select_related("pet", "medical_record").order_by("follow_up_date")
    
    return render(request, "reminders.html", context)




