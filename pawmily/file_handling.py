"""Shared file upload configuration and small helpers.

Keeping file path configuration here avoids repeating upload destinations
across models and forms.
"""

import os


PET_PROFILE_PICTURE_UPLOAD_TO = "pet_profiles/"
MEDICAL_ATTACHMENT_UPLOAD_TO = "medical_attachments/%Y/%m/"


def uploaded_basename(file_name: str) -> str:
    """Return a file's basename from its storage path."""
    return os.path.basename(file_name or "")