from __future__ import annotations

import base64
import binascii
import re
from typing import Any


_REQUIRED_FIELDS = {
    "type",
    "project_id",
    "private_key_id",
    "private_key",
    "client_email",
    "client_id",
    "token_uri",
}
_PLACEHOLDERS = {"...", "xxx", "replace", "replace_me", "isi_di_sini"}


def normalize_service_account_info(info: dict[str, Any]) -> dict[str, Any]:
    """Normalisasi dan validasi awal kredensial JSON service account Google."""
    normalized = {str(key): value for key, value in dict(info).items()}
    missing = sorted(
        field for field in _REQUIRED_FIELDS
        if not str(normalized.get(field) or "").strip()
    )
    if missing:
        raise ValueError(
            "Konfigurasi Google service account belum lengkap: " + ", ".join(missing)
        )
    if str(normalized.get("type")).strip() != "service_account":
        raise ValueError("google_service_account.type harus bernilai service_account.")

    for field in ("project_id", "private_key_id", "client_email", "client_id"):
        value = str(normalized.get(field) or "").strip()
        if value.casefold() in _PLACEHOLDERS or "..." in value:
            raise ValueError(
                f"google_service_account.{field} masih berupa placeholder. "
                "Salin nilai asli dari file JSON service account."
            )
        normalized[field] = value

    private_key = str(normalized["private_key"]).strip().lstrip("\ufeff")
    private_key = private_key.replace("\\r\\n", "\n").replace("\\n", "\n")
    if "..." in private_key or "REPLACE" in private_key.upper():
        raise ValueError(
            "google_service_account.private_key masih berupa placeholder. "
            "Salin seluruh private_key dari file JSON service account."
        )
    match = re.fullmatch(
        r"-----BEGIN PRIVATE KEY-----\s+([A-Za-z0-9+/=\s]+?)\s+-----END PRIVATE KEY-----",
        private_key,
        flags=re.DOTALL,
    )
    if not match:
        raise ValueError(
            "Format private_key Google tidak valid. Key harus dimulai dengan "
            "-----BEGIN PRIVATE KEY----- dan diakhiri -----END PRIVATE KEY-----."
        )
    encoded = re.sub(r"\s+", "", match.group(1))
    try:
        decoded = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError(
            "Isi private_key Google bukan Base64 PEM yang valid. "
            "Unduh ulang key JSON dan jangan mengganti karakter di dalam private_key."
        ) from exc
    if not decoded:
        raise ValueError("Isi private_key Google kosong.")
    normalized["private_key"] = private_key + "\n"
    return normalized
