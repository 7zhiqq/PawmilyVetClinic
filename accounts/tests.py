import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Profile


User = get_user_model()


PNG_BYTES = (
	b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
	b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\x0cIDATx\x9cc``\x00\x00\x00\x02\x00\x01"
	b"\xe2!\xbc3\x00\x00\x00\x00IEND\xaeB`\x82"
)


@override_settings(MEDIA_ROOT=tempfile.gettempdir())
class ProfileManagementTests(TestCase):
    def setUp(self):
        self.owner = self._create_user("owner", "pet_owner")
        self.staff = self._create_user("staff", "staff")
        self.manager = self._create_user("manager", "manager")

    def _create_user(self, username, role):
        user = User.objects.create_user(
            username=username,
            password="StrongPass123!",
            email=f"{username}@example.com",
            first_name=username.title(),
            last_name="User",
        )
        Profile.objects.create(user=user, role=role)
        return user

    def test_all_roles_can_open_profile_page(self):
        for user in (self.owner, self.staff, self.manager):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                response = self.client.get(reverse("profile_edit"))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "My profile")

    def test_user_can_update_only_their_own_profile_details(self):
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("profile_edit"),
            {
                "action": "profile",
                "first_name": "Updated",
                "last_name": "Staff",
                "email": "updated.staff@example.com",
                "phone": "09990001111",
                "address": "Clinic Street",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.staff.refresh_from_db()
        self.staff.profile.refresh_from_db()
        self.manager.refresh_from_db()
        self.manager.profile.refresh_from_db()
        self.assertEqual(self.staff.first_name, "Updated")
        self.assertEqual(self.staff.last_name, "Staff")
        self.assertEqual(self.staff.email, "updated.staff@example.com")
        self.assertEqual(self.staff.profile.phone, "+639990001111")
        self.assertEqual(self.staff.profile.address, "Clinic Street")
        self.assertEqual(self.manager.email, "manager@example.com")
        self.assertEqual(self.manager.profile.phone, "")

    def test_user_can_upload_profile_photo(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("profile_edit"),
            {
                "action": "profile",
                "first_name": self.owner.first_name,
                "last_name": self.owner.last_name,
                "email": self.owner.email,
                "phone": "",
                "address": "",
                "profile_photo": SimpleUploadedFile(
                    "avatar.png",
                    PNG_BYTES,
                    content_type="image/png",
                ),
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.owner.profile.refresh_from_db()
        self.assertTrue(bool(self.owner.profile.profile_photo))

    def test_user_can_change_password(self):
        self.client.force_login(self.manager)

        response = self.client.post(
            reverse("profile_edit"),
            {
                "action": "password",
                "old_password": "StrongPass123!",
                "new_password1": "NewStrongPass456!",
                "new_password2": "NewStrongPass456!",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.manager.refresh_from_db()
        self.assertTrue(self.manager.check_password("NewStrongPass456!"))

    def test_email_must_remain_unique(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("profile_edit"),
            {
                "action": "profile",
                "first_name": self.owner.first_name,
                "last_name": self.owner.last_name,
                "email": self.staff.email,
                "phone": "",
                "address": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "An account with this email already exists.")

    def test_profile_page_defaults_to_profile_section(self):
        self.client.force_login(self.owner)

        response = self.client.get(reverse("profile_edit"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active_section"], "profile")
        self.assertContains(response, "Profile details")
        self.assertNotContains(response, "Change password")

    def test_password_section_shows_only_password_form(self):
        self.client.force_login(self.owner)

        response = self.client.get(f'{reverse("profile_edit")}?section=password')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active_section"], "password")
        self.assertContains(response, "Change password")
        self.assertContains(response, "Current password")
        self.assertNotContains(response, "Profile details")
        self.assertNotContains(response, "Email address")

    def test_invalid_password_submission_keeps_password_section_active(self):
        self.client.force_login(self.manager)

        response = self.client.post(
            reverse("profile_edit"),
            {
                "action": "password",
                "old_password": "wrong-password",
                "new_password1": "NewStrongPass456!",
                "new_password2": "NewStrongPass456!",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active_section"], "password")
        self.assertContains(response, "Your old password was entered incorrectly")
        self.assertContains(response, "Current password")
        self.assertNotContains(response, "Profile details")
