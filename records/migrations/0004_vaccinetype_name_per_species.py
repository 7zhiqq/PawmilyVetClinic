from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("records", "0003_vaccinetype_unit_price_and_vaccinationrecord_shots"),
    ]

    operations = [
        migrations.AlterField(
            model_name="vaccinetype",
            name="name",
            field=models.CharField(
                help_text="Vaccine name (e.g., Rabies, DHPP, FeLV)",
                max_length=100,
            ),
        ),
    ]
