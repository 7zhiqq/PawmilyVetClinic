from django.contrib import admin

from .models import Invitation, Pet, Profile, WalkInRegistration


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role")
    list_filter = ("role",)
    search_fields = ("user__username", "user__email")


@admin.register(Pet)
class PetAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "species", "breed", "birth_date")
    list_filter = ("species",)
    search_fields = ("name", "owner__username", "breed")


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = ("email", "role", "is_used", "created_at")
    list_filter = ("role", "is_used")
    search_fields = ("email",)
    readonly_fields = ("token", "created_at")


@admin.register(WalkInRegistration)
class WalkInRegistrationAdmin(admin.ModelAdmin):
    list_display = ("user", "is_activated", "created_by", "created_at", "activated_at")
    list_filter = ("is_activated",)
    search_fields = ("user__first_name", "user__last_name", "user__email")
    readonly_fields = ("token", "created_at")
