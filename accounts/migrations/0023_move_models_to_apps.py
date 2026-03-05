"""
Remove moved models from accounts app state.

The Appointment model moved to the 'appointments' app.
MedicalRecord, VaccinationRecord, and MedicalAttachment moved to the 'records' app.

This is a state-only migration — no database tables are dropped.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0022_medicalrecord_medicalattachment_vaccinationrecord"),
        ("appointments", "0001_initial"),
        ("records", "0001_initial"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name="MedicalAttachment"),
                migrations.DeleteModel(name="VaccinationRecord"),
                migrations.DeleteModel(name="MedicalRecord"),
                migrations.DeleteModel(name="Appointment"),
            ],
            database_operations=[],
        ),
    ]
