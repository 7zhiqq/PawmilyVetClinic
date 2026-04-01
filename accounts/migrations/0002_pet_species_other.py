# Generated migration to add species_other field to Pet model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='pet',
            name='species_other',
            field=models.CharField(
                blank=True,
                default='',
                help_text="Specify the species if 'Other' is selected above.",
                max_length=100,
            ),
        ),
    ]
