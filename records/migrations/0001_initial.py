"""
Move MedicalRecord, VaccinationRecord, MedicalAttachment from accounts to records app.

This is a state-only migration — the database tables already exist
under their original 'accounts_*' names and are reused via db_table.
"""
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("accounts", "0022_medicalrecord_medicalattachment_vaccinationrecord"),
        ("appointments", "0001_initial"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name="MedicalRecord",
                    fields=[
                        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                        ("visit_date", models.DateField(default=django.utils.timezone.now)),
                        ("chief_complaint", models.CharField(blank=True, max_length=255)),
                        ("consultation_notes", models.TextField(blank=True)),
                        ("diagnosis", models.TextField(blank=True)),
                        ("treatment", models.TextField(blank=True)),
                        ("prescription", models.TextField(blank=True, help_text="Medications prescribed, dosage, frequency")),
                        ("follow_up_date", models.DateField(blank=True, null=True)),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("updated_at", models.DateTimeField(auto_now=True)),
                        ("appointment", models.ForeignKey(blank=True, help_text="Linked appointment (optional)", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="medical_records", to="appointments.appointment")),
                        ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="medical_records_created", to=settings.AUTH_USER_MODEL)),
                        ("pet", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="medical_records", to="accounts.pet")),
                    ],
                    options={
                        "db_table": "accounts_medicalrecord",
                        "ordering": ["-visit_date", "-created_at"],
                    },
                ),
                migrations.CreateModel(
                    name="VaccinationRecord",
                    fields=[
                        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                        ("vaccine_name", models.CharField(max_length=150)),
                        ("date_administered", models.DateField(default=django.utils.timezone.now)),
                        ("next_due_date", models.DateField(blank=True, null=True)),
                        ("batch_number", models.CharField(blank=True, max_length=100)),
                        ("notes", models.TextField(blank=True)),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("administered_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="vaccinations_administered", to=settings.AUTH_USER_MODEL)),
                        ("medical_record", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="vaccinations", to="records.medicalrecord")),
                        ("pet", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="vaccinations", to="accounts.pet")),
                    ],
                    options={
                        "db_table": "accounts_vaccinationrecord",
                        "ordering": ["-date_administered"],
                    },
                ),
                migrations.CreateModel(
                    name="MedicalAttachment",
                    fields=[
                        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                        ("file", models.FileField(upload_to="medical_attachments/%Y/%m/")),
                        ("description", models.CharField(blank=True, max_length=255)),
                        ("uploaded_at", models.DateTimeField(auto_now_add=True)),
                        ("medical_record", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="attachments", to="records.medicalrecord")),
                        ("uploaded_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                    ],
                    options={
                        "db_table": "accounts_medicalattachment",
                    },
                ),
            ],
            database_operations=[],
        ),
    ]
