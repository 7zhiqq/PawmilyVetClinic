from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("records", "0002_medicalrecord_follow_up_reason_followupreminder_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="vaccinetype",
            name="unit_price",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text="Standard price per shot in Philippine Pesos (PHP)",
                max_digits=10,
            ),
        ),
        migrations.AddField(
            model_name="vaccinationrecord",
            name="shots_administered",
            field=models.PositiveIntegerField(
                default=1,
                help_text="Number of shots/doses administered during this visit",
            ),
        ),
    ]
