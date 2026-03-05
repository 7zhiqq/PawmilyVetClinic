import io

import qrcode
import qrcode.constants

from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.db import transaction
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET

from .forms import (
    InvitationForm,
    PetForm,
    PetOwnerRegistrationForm,
    ProfileForm,
    StaffInviteRegistrationForm,
    WalkInActivationForm,
    WalkInClientForm,
    WalkInPetForm,
)
from .models import (
    Invitation, Pet, Profile, WalkInRegistration,
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
