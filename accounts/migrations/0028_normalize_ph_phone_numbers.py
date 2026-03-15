"""
Data migration: normalize all existing Profile.phone values to the canonical
Philippine mobile format +639XXXXXXXXX.

Accepted source formats (spaces/dashes/dots are stripped first):
  09XXXXXXXXX     → +639XXXXXXXXX
  +639XXXXXXXXX   → +639XXXXXXXXX  (already canonical)
  639XXXXXXXXX    → +639XXXXXXXXX

Numbers that cannot be recognized as valid Philippine mobile numbers are
cleared (set to '') because they cannot be migrated in a meaningful way.
"""

import re

from django.db import migrations


_PH_PHONE_RE = re.compile(r'^(?:\+63|63|0)(9\d{9})$')


def _normalize(raw):
    stripped = re.sub(r'[\s\-.]', '', raw or '')
    if not stripped:
        return ''
    m = _PH_PHONE_RE.match(stripped)
    if not m:
        return ''          # unrecognised — clear rather than store garbage
    return f'+63{m.group(1)}'


def normalize_profile_phones(apps, schema_editor):
    Profile = apps.get_model('accounts', 'Profile')
    to_update = []
    for profile in Profile.objects.exclude(phone=''):
        normalized = _normalize(profile.phone)
        if profile.phone != normalized:
            profile.phone = normalized
            to_update.append(profile)
    if to_update:
        Profile.objects.bulk_update(to_update, ['phone'])


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0027_profile_profile_photo'),
    ]

    operations = [
        migrations.RunPython(
            normalize_profile_phones,
            migrations.RunPython.noop,
        ),
    ]
