from __future__ import annotations

import io
import re
from typing import Any

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

from .google_credentials import normalize_service_account_info


DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.file"


def normalize_drive_folder_id(value: str) -> str:
    """Terima folder ID atau URL Google Drive dan kembalikan folder ID-nya."""
    raw = str(value or "").strip()
    match = re.search(r"/folders/([A-Za-z0-9_-]+)", raw)
    return match.group(1) if match else raw


def upload_excel(
    file_bytes: bytes,
    filename: str,
    mime_type: str,
    folder_id: str,
    service_account_info: dict[str, Any],
) -> dict[str, str | None]:
    normalized_info = normalize_service_account_info(service_account_info)
    credentials = Credentials.from_service_account_info(normalized_info, scopes=[DRIVE_SCOPE])
    drive = build("drive", "v3", credentials=credentials, cache_discovery=False)
    metadata: dict[str, Any] = {"name": filename}
    normalized_folder_id = normalize_drive_folder_id(folder_id)
    if normalized_folder_id:
        metadata["parents"] = [normalized_folder_id]
    media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mime_type, resumable=False)
    result = (
        drive.files()
        .create(body=metadata, media_body=media, fields="id, webViewLink", supportsAllDrives=True)
        .execute()
    )
    return {"drive_file_id": result["id"], "drive_web_view_link": result.get("webViewLink")}
