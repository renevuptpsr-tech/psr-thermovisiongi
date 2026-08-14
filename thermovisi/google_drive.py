from __future__ import annotations

import io
from typing import Any

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload


DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.file"


def upload_excel(
    file_bytes: bytes,
    filename: str,
    mime_type: str,
    folder_id: str,
    service_account_info: dict[str, Any],
) -> dict[str, str | None]:
    credentials = Credentials.from_service_account_info(service_account_info, scopes=[DRIVE_SCOPE])
    drive = build("drive", "v3", credentials=credentials, cache_discovery=False)
    metadata: dict[str, Any] = {"name": filename}
    if folder_id:
        metadata["parents"] = [folder_id]
    media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mime_type, resumable=False)
    result = (
        drive.files()
        .create(body=metadata, media_body=media, fields="id, webViewLink", supportsAllDrives=True)
        .execute()
    )
    return {"drive_file_id": result["id"], "drive_web_view_link": result.get("webViewLink")}

