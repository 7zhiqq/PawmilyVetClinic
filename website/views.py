from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render


def landing_page(request):
    if request.user.is_authenticated:
        return redirect("/dashboard/")
    return render(request, "landing.html")


from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from accounts.forms import AppointmentBookingForm, AppointmentStaffForm, PetForm
from accounts.models import Appointment, Pet, Profile
from django.contrib.auth import get_user_model

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
        context["pet_form"]  = PetForm()

    elif role in (Profile.ROLE_STAFF, Profile.ROLE_MANAGER):
        context["owners"]     = User.objects.filter(profile__role=Profile.ROLE_PET_OWNER).order_by("username")
        context["pets"]       = Pet.objects.select_related("owner").order_by("owner__username", "name")
        context["staff_form"] = AppointmentStaffForm(initial={"appointment_type": Appointment.TYPE_WALK_IN})

    return render(request, "dashboard.html", context)