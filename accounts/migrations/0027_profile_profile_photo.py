from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0026_pet_profile_picture"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="profile_photo",
            field=models.ImageField(blank=True, null=True, upload_to="user_profiles/"),
        ),
    ]