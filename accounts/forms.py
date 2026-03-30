import re

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordChangeForm, PasswordResetForm, SetPasswordForm, UserCreationForm

from .models import (
    Invitation, Pet, Profile,
    WalkInRegistration,
)


User = get_user_model()

# ─── Philippine phone validation ─────────────────────────────────────────────

_PH_PHONE_RE = re.compile(r'^(?:\+63|63|0)(9\d{9})$')
_PH_PHONE_ERROR = (
    "Enter a valid Philippine mobile number, e.g. 09XX XXX XXXX or +63 9XX XXX XXXX."
)


def ph_phone_normalize(value):
    """
    Validate and normalize a Philippine mobile phone number.

    Accepted input formats (spaces, dashes, and dots are stripped first):
      09XXXXXXXXX      — local 11-digit format
      +639XXXXXXXXX    — international format with plus
      639XXXXXXXXX     — international format without plus

    Returns the canonical +639XXXXXXXXX form, or '' for an empty value.
    Raises ValueError with a user-friendly message on failure.
    """
    stripped = re.sub(r'[\s\-.]', '', value or '')
    if not stripped:
        return ''
    m = _PH_PHONE_RE.match(stripped)
    if not m:
        raise ValueError(_PH_PHONE_ERROR)
    return f'+63{m.group(1)}'

PET_SHARED_FIELDS = [
    "name",
    "species",
    "breed",
    "gender",
    "birth_date",
    "weight_kg",
    "color",
    "notes",
]

PET_SHARED_WIDGETS = {
    "name": forms.TextInput(attrs={"placeholder": "Pet's name"}),
    "breed": forms.TextInput(attrs={"placeholder": "e.g. Golden Retriever"}),
    "birth_date": forms.DateInput(attrs={"type": "date"}),
    "weight_kg": forms.NumberInput(attrs={"step": "0.01", "placeholder": "0.00"}),
    "color": forms.TextInput(attrs={"placeholder": "e.g. Brown, Black and white"}),
    "notes": forms.Textarea(attrs={"rows": 2, "placeholder": "Medical notes, allergies, etc."}),
}


def email_normalize(email):
    return (email or "").strip().lower()


class PetOwnerRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(required=True)
    last_name = forms.CharField(required=True)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("first_name", "last_name", "username", "email")

    def clean_email(self):
        email = self.cleaned_data["email"]
        normalized = email_normalize(email)
        if User.objects.filter(email__iexact=normalized).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email


class StaffInviteRegistrationForm(UserCreationForm):
    first_name = forms.CharField(required=True)
    last_name = forms.CharField(required=True)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("first_name", "last_name", "username")


class InvitationForm(forms.ModelForm):
    class Meta:
        model = Invitation
        fields = ["email", "role"]
        widgets = {
            "email": forms.EmailInput(attrs={"placeholder": "staff@example.com"}),
        }

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if not email:
            return email
        normalized = email_normalize(email)
        if User.objects.filter(email__iexact=normalized).exists():
            raise forms.ValidationError(
                "A user with this email already has an account. One email per user."
            )
        if Invitation.objects.filter(email__iexact=normalized, is_used=False).exists():
            raise forms.ValidationError(
                "A pending invitation for this email already exists."
            )
        return email


class ProfileForm(forms.ModelForm):
    first_name = forms.CharField(required=True)
    last_name = forms.CharField(required=True)
    email = forms.EmailField(required=True)
    clear_profile_photo = forms.BooleanField(required=False)

    class Meta:
        model = Profile
        fields = ["first_name", "last_name", "email", "phone", "address", "profile_photo"]
        widgets = {
            "first_name": forms.TextInput(attrs={"placeholder": "First name"}),
            "last_name": forms.TextInput(attrs={"placeholder": "Last name"}),
            "email": forms.EmailInput(attrs={"placeholder": "you@example.com"}),
            "phone": forms.TextInput(attrs={"placeholder": "09XX XXX XXXX or +63 9XX XXX XXXX"}),
            "address": forms.Textarea(attrs={"rows": 3, "placeholder": "Your address"}),
            "profile_photo": forms.ClearableFileInput(attrs={"accept": "image/*"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        user = getattr(self.instance, "user", None)
        if user is not None:
            self.fields["first_name"].initial = user.first_name
            self.fields["last_name"].initial = user.last_name
            self.fields["email"].initial = user.email
        self.fields["clear_profile_photo"].widget = forms.CheckboxInput()

    def clean_email(self):
        email = self.cleaned_data["email"]
        normalized = email_normalize(email)
        qs = User.objects.filter(email__iexact=normalized)
        if self.instance and self.instance.user_id:
            qs = qs.exclude(pk=self.instance.user_id)
        if qs.exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean_phone(self):
        value = self.cleaned_data.get("phone", "")
        try:
            return ph_phone_normalize(value)
        except ValueError as exc:
            raise forms.ValidationError(str(exc))

    def save(self, commit=True):
        profile = super().save(commit=False)
        user = profile.user
        user.first_name = self.cleaned_data["first_name"].strip()
        user.last_name = self.cleaned_data["last_name"].strip()
        user.email = email_normalize(self.cleaned_data["email"])

        if (
            self.cleaned_data.get("clear_profile_photo")
            and profile.profile_photo
            and not self.cleaned_data.get("profile_photo")
        ):
            profile.profile_photo.delete(save=False)
            profile.profile_photo = None

        if commit:
            user.save(update_fields=["first_name", "last_name", "email"])
            profile.save()
        else:
            self._pending_user = user
        return profile


class ProfilePasswordForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["old_password"].widget.attrs.update({"placeholder": "Current password"})
        self.fields["new_password1"].widget.attrs.update({"placeholder": "New password"})
        self.fields["new_password2"].widget.attrs.update({"placeholder": "Confirm new password"})


class ExistingEmailPasswordResetForm(PasswordResetForm):
    def clean_email(self):
        email = self.cleaned_data["email"]
        normalized = email_normalize(email)
        if not User.objects.filter(email__iexact=normalized).exists():
            raise forms.ValidationError("No account was found for this email address.")
        return normalized


class StyledSetPasswordForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["new_password1"].widget.attrs.update({"placeholder": "Enter your new password"})
        self.fields["new_password2"].widget.attrs.update({"placeholder": "Confirm your new password"})


class PetForm(forms.ModelForm):
    class Meta:
        model = Pet
        fields = [*PET_SHARED_FIELDS, "profile_picture"]
        widgets = {
            **PET_SHARED_WIDGETS,
            "profile_picture": forms.ClearableFileInput(attrs={"accept": "image/*"}),
        }
    
    def __init__(self, *args, owner=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.owner = owner
    
    def clean(self):
        cleaned_data = super().clean()
        name = cleaned_data.get("name")
        species = cleaned_data.get("species")
        owner = self.owner or (self.instance.owner if self.instance.pk else None)
        
        # Check for duplicate pet records for same owner
        if owner and name and species:
            duplicate_query = Pet.objects.filter(
                owner=owner,
                name=name,
                species=species,
            )
            # Exclude current instance if updating
            if self.instance.pk:
                duplicate_query = duplicate_query.exclude(pk=self.instance.pk)
            
            if duplicate_query.exists():
                raise forms.ValidationError(
                    f"You already have a {species.title()} named '{name}'. "
                    "Please use a different name or check your existing pets."
                )
        
        return cleaned_data


class WalkInClientForm(forms.Form):
    """Staff form for registering a walk-in client (no online account yet)."""
    first_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={"placeholder": "First name"}))
    last_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={"placeholder": "Last name"}))
    email = forms.EmailField(required=False, widget=forms.EmailInput(attrs={"placeholder": "client@example.com (optional)"}))
    phone = forms.CharField(max_length=20, required=False, widget=forms.TextInput(attrs={"placeholder": "09XX XXX XXXX or +63 9XX XXX XXXX (optional)"}))
    address = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2, "placeholder": "Client's address"}))

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if not email:
            return email
        normalized = email_normalize(email)
        if User.objects.filter(email__iexact=normalized).exists():
            raise forms.ValidationError(
                "An account with this email already exists. Use the existing client instead."
            )
        return email

    def clean_phone(self):
        value = self.cleaned_data.get("phone", "")
        try:
            return ph_phone_normalize(value)
        except ValueError as exc:
            raise forms.ValidationError(str(exc))


class WalkInPetForm(forms.ModelForm):
    """Pet form used during walk-in registration (no owner set yet)."""
    class Meta:
        model = Pet
        fields = PET_SHARED_FIELDS
        widgets = PET_SHARED_WIDGETS


class WalkInActivationForm(UserCreationForm):
    """Form for a walk-in client to activate their online account."""
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username",)

    def clean_username(self):
        username = self.cleaned_data["username"]
        # Allow the client to keep the suggested username already reserved
        # on their own User record. Only reject if another user has it.
        qs = User.objects.filter(username=username)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(
                "A user with that username already exists."
            )
        return username


class WalkInLinkForm(forms.Form):
    """Form shown during pet-owner registration to link an existing walk-in record."""
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"placeholder": "Email used during walk-in registration"}),
        help_text="Enter the email the clinic used when registering you.",
    )
