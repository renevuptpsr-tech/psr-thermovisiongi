from __future__ import annotations

import base64
import hashlib
import hmac
import re
import time
import uuid
from typing import Any


def normalize_drive_folder_id(value: str) -> str:
    """Terima folder ID atau URL Google Drive dan kembalikan folder ID-nya."""
    raw = str(value or "").strip()
    match = re.search(r"/folders/([A-Za-z0-9_-]+)", raw)
    return match.group(1) if match else raw


def validate_gateway_config(web_app_url: str, shared_secret: str) -> tuple[str, str]:
    url = str(web_app_url or "").strip()
    secret = str(shared_secret or "").strip()
    if not re.fullmatch(r"https://script\.google\.com/macros/s/[A-Za-z0-9_-]+/exec", url):
        raise ValueError(
            "google_drive.web_app_url harus berupa URL deployment Apps Script yang berakhir /exec."
        )
    if len(secret) < 32:
        raise ValueError("google_drive.shared_secret minimal 32 karakter acak.")
    if secret.upper().startswith(("GANTI_", "ISI_")):
        raise ValueError("google_drive.shared_secret masih berupa placeholder.")
    return url, secret


def build_upload_envelope(
    *,
    file_bytes: bytes,
    filename: str,
    mime_type: str,
    folder_id: str,
    shared_secret: str,
    timestamp: int | None = None,
    nonce: str | None = None,
) -> dict[str, Any]:
    normalized_folder_id = normalize_drive_folder_id(folder_id)
    timestamp = int(timestamp if timestamp is not None else time.time())
    nonce = nonce or uuid.uuid4().hex
    file_hash = hashlib.sha256(file_bytes).hexdigest()
    canonical = "\n".join(
        (str(timestamp), nonce, filename, mime_type, normalized_folder_id, file_hash)
    )
    signature = hmac.new(
        shared_secret.encode("utf-8"),
        canonical.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return {
        "timestamp": timestamp,
        "nonce": nonce,
        "filename": filename,
        "mime_type": mime_type,
        "folder_id": normalized_folder_id,
        "file_sha256": file_hash,
        "signature": signature,
        "file_base64": base64.b64encode(file_bytes).decode("ascii"),
    }


def upload_excel(
    file_bytes: bytes,
    filename: str,
    mime_type: str,
    folder_id: str,
    *,
    web_app_url: str,
    shared_secret: str,
    timeout_seconds: int = 120,
) -> dict[str, str | None]:
    import requests

    url, secret = validate_gateway_config(web_app_url, shared_secret)
    envelope = build_upload_envelope(
        file_bytes=file_bytes,
        filename=filename,
        mime_type=mime_type,
        folder_id=folder_id,
        shared_secret=secret,
    )
    try:
        response = requests.post(
            url,
            json=envelope,
            timeout=(10, timeout_seconds),
            allow_redirects=True,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"Gateway Google Drive tidak dapat dihubungi: {exc}") from exc
    try:
        result = response.json()
    except ValueError as exc:
        raise RuntimeError(
            "Respons Apps Script bukan JSON. Periksa deployment Web App dan akses Anyone."
        ) from exc
    if not result.get("ok"):
        raise RuntimeError(f"Apps Script menolak upload: {result.get('error', 'Unknown error')}")
    return {
        "drive_file_id": result.get("drive_file_id"),
        "drive_web_view_link": result.get("drive_web_view_link"),
    }
