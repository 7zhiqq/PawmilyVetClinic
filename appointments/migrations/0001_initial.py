"""
Move Appointment model from accounts to appointments app.

This is a state-only migration — the database table already exists
as 'accounts_appointment' and is reused via db_table.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("accounts", "0022_medicalrecord_medicalattachment_vaccinationrecord"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name="Appointment",
                    fields=[
                        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                        ("appointment_date", models.DateField()),
                        ("start_time", models.TimeField()),
                        ("end_time", models.TimeField(blank=True, null=True)),
                        ("slot_number", models.PositiveSmallIntegerField(blank=True, default=1, help_text="Slot position (1–2) within a date/time block. NULL for cancelled/rejected.", null=True)),
                        ("status", models.CharField(choices=[("pending", "Pending"), ("confirmed", "Confirmed"), ("rejected", "Rejected"), ("cancelled", "Cancelled"), ("completed", "Completed"), ("no_show", "No Show")], default="pending", max_length=20)),
                        ("appointment_type", models.CharField(choices=[("scheduled", "Scheduled"), ("walk_in", "Walk-in")], default="scheduled", max_length=20)),
                        ("reason", models.CharField(blank=True, max_length=200)),
                        ("notes", models.TextField(blank=True)),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("updated_at", models.DateTimeField(auto_now=True)),
                        ("owner", models.ForeignKey(help_text="Pet owner who booked the appointment", on_delete=django.db.models.deletion.CASCADE, related_name="appointments", to=settings.AUTH_USER_MODEL)),
                        ("pet", models.ForeignKey(blank=True, help_text="Pet (optional for walk-ins)", null=True, on_delete=django.db.models.deletion.CASCADE, related_name="appointments", to="accounts.pet")),
                        ("staff", models.ForeignKey(blank=True, help_text="Staff who created/confirmed (for walk-ins)", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="managed_appointments", to=settings.AUTH_USER_MODEL)),
                    ],
                    options={
                        "db_table": "accounts_appointment",
                        "ordering": ["appointment_date", "start_time", "slot_number"],
                    },
                ),
                migrations.AddConstraint(
                    model_name="appointment",
                    constraint=models.UniqueConstraint(
                        fields=("appointment_date", "start_time", "slot_number", "appointment_type"),
                        name="unique_active_slot_per_datetime_and_type",
                    ),
                ),
            ],
            database_operations=[],
        ),
    ]
