# Generated migration — add slot_number to Appointment

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0007_remove_appointmentauditlog_accounts_ap_appoint_07f45a_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='appointment',
            name='slot_number',
            field=models.PositiveSmallIntegerField(
                default=1,
                help_text='Slot position (1–5) within a date/time block',
            ),
        ),
        migrations.AddConstraint(
            model_name='appointment',
            constraint=models.UniqueConstraint(
                fields=['appointment_date', 'start_time', 'slot_number'],
                name='unique_slot_per_datetime',
            ),
        ),
    ]