import hashlib
import hmac

import pytest

from thermovisi.google_drive import (
    build_upload_envelope,
    normalize_drive_folder_id,
    validate_gateway_config,
)


FOLDER_ID = "1mWx5bX5siYp0d63h1VSy0QHsblOXJT6i"
WEB_APP_URL = "https://script.google.com/macros/s/deployment-id_123/exec"
SECRET = "a" * 64


def test_gateway_config_requires_exec_url_and_long_secret():
    assert validate_gateway_config(WEB_APP_URL, SECRET) == (WEB_APP_URL, SECRET)
    with pytest.raises(ValueError, match="berakhir /exec"):
        validate_gateway_config("https://example.com/upload", SECRET)
    with pytest.raises(ValueError, match="minimal 32"):
        validate_gateway_config(WEB_APP_URL, "short")


def test_upload_envelope_has_matching_hash_and_signature():
    envelope = build_upload_envelope(
        file_bytes=b"excel-data",
        filename="hasil.xlsx",
        mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        folder_id=FOLDER_ID,
        destination_year=2026,
        destination_gi="GI 150KV PORSEA",
        destination_month=8,
        shared_secret=SECRET,
        timestamp=1_700_000_000,
        nonce="0123456789abcdef0123456789abcdef",
    )
    expected_hash = hashlib.sha256(b"excel-data").hexdigest()
    canonical = "\n".join(
        (
            str(envelope["timestamp"]),
            envelope["nonce"],
            envelope["filename"],
            envelope["mime_type"],
            envelope["folder_id"],
            "2026",
            "GI 150KV PORSEA",
            "08 - AGUSTUS",
            expected_hash,
        )
    )
    expected_signature = hmac.new(
        SECRET.encode(), canonical.encode(), hashlib.sha256
    ).hexdigest()
    assert envelope["file_sha256"] == expected_hash
    assert envelope["signature"] == expected_signature
    assert envelope["file_base64"] == "ZXhjZWwtZGF0YQ=="
    assert envelope["destination_year"] == "2026"
    assert envelope["destination_gi"] == "GI 150KV PORSEA"
    assert envelope["destination_month"] == "08 - AGUSTUS"


def test_drive_folder_accepts_id_or_full_url():
    assert normalize_drive_folder_id(FOLDER_ID) == FOLDER_ID
    assert normalize_drive_folder_id(
        f"https://drive.google.com/drive/folders/{FOLDER_ID}?usp=drive_link"
    ) == FOLDER_ID
