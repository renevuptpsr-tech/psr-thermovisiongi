import base64

import pytest

from thermovisi.google_credentials import normalize_service_account_info
from thermovisi.google_drive import normalize_drive_folder_id


def info(private_key):
    return {
        "type": "service_account",
        "project_id": "project-id",
        "private_key_id": "key-id",
        "private_key": private_key,
        "client_email": "uploader@project-id.iam.gserviceaccount.com",
        "client_id": "123456",
        "token_uri": "https://oauth2.googleapis.com/token",
    }


def valid_pem(*, escaped_newlines=False):
    body = base64.b64encode(b"not-a-real-secret-key-for-structure-test").decode()
    pem = f"-----BEGIN PRIVATE KEY-----\n{body}\n-----END PRIVATE KEY-----"
    return pem.replace("\n", "\\n") if escaped_newlines else pem


def test_literal_escaped_newlines_are_normalized():
    result = normalize_service_account_info(info(valid_pem(escaped_newlines=True)))
    assert "\\n" not in result["private_key"]
    assert result["private_key"].startswith("-----BEGIN PRIVATE KEY-----\n")


def test_placeholder_key_has_clear_error():
    with pytest.raises(ValueError, match="placeholder"):
        normalize_service_account_info(info("-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----"))


def test_invalid_pem_body_is_rejected():
    with pytest.raises(ValueError, match="Base64 PEM"):
        normalize_service_account_info(
            info("-----BEGIN PRIVATE KEY-----\n.invalid\n-----END PRIVATE KEY-----")
        )


def test_drive_folder_accepts_id_or_full_url():
    folder_id = "1mWx5bX5siYp0d63h1VSy0QHsblOXJT6i"
    assert normalize_drive_folder_id(folder_id) == folder_id
    assert normalize_drive_folder_id(
        f"https://drive.google.com/drive/folders/{folder_id}?usp=drive_link"
    ) == folder_id
