from __future__ import annotations

import io
import json
import re
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload


DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.file"
DEFAULT_TOKEN_PATH = Path(".streamlit/google_drive_token.json")


def normalize_drive_folder_id(value: str) -> str:
    """Terima folder ID atau URL Google Drive dan kembalikan folder ID-nya."""
    raw = str(value or "").strip()
    match = re.search(r"/folders/([A-Za-z0-9_-]+)", raw)
    return match.group(1) if match else raw


def normalize_oauth_client_config(info: dict[str, Any]) -> dict[str, Any]:
    """Ubah konfigurasi TOML menjadi format OAuth Desktop Google."""
    raw = dict(info or {})
    installed = dict(raw.get("installed") or raw)
    required = ("client_id", "client_secret", "auth_uri", "token_uri")
    missing = [key for key in required if not str(installed.get(key) or "").strip()]
    if missing:
        raise ValueError("Konfigurasi google_oauth belum lengkap: " + ", ".join(missing))
    for key in required:
        value = str(installed[key]).strip()
        if value == "..." or "GANTI_" in value.upper():
            raise ValueError(
                f"google_oauth.{key} masih berupa placeholder. "
                "Salin nilai OAuth Client Desktop yang sebenarnya."
            )
        installed[key] = value
    redirect_uris = installed.get("redirect_uris") or ["http://localhost"]
    if isinstance(redirect_uris, str):
        redirect_uris = [redirect_uris]
    installed["redirect_uris"] = [
        str(uri).strip() for uri in redirect_uris if str(uri).strip()
    ]
    installed.setdefault("project_id", "")
    return {"installed": installed}


def load_drive_credentials(
    oauth_client_config: dict[str, Any],
    *,
    token_path: str | Path = DEFAULT_TOKEN_PATH,
    interactive: bool = False,
) -> Credentials | None:
    """Muat/refresh token OAuth; buka login browser hanya saat diminta pengguna."""
    config = normalize_oauth_client_config(oauth_client_config)
    path = Path(token_path)
    credentials: Credentials | None = None
    if path.exists():
        try:
            credentials = Credentials.from_authorized_user_file(str(path), [DRIVE_SCOPE])
        except (ValueError, json.JSONDecodeError):
            credentials = None
    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
    if credentials and credentials.valid:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(credentials.to_json(), encoding="utf-8")
        return credentials
    if not interactive:
        return None
    flow = InstalledAppFlow.from_client_config(config, [DRIVE_SCOPE])
    credentials = flow.run_local_server(
        host="localhost",
        port=0,
        open_browser=True,
        authorization_prompt_message="Silakan selesaikan login Google Drive di browser.",
        success_message="Google Drive terhubung. Anda dapat kembali ke aplikasi Thermovisi.",
        access_type="offline",
        prompt="consent",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(credentials.to_json(), encoding="utf-8")
    return credentials


def disconnect_drive(token_path: str | Path = DEFAULT_TOKEN_PATH) -> None:
    Path(token_path).unlink(missing_ok=True)


def upload_excel(
    file_bytes: bytes,
    filename: str,
    mime_type: str,
    folder_id: str,
    credentials: Credentials,
) -> dict[str, str | None]:
    if not credentials or not credentials.valid:
        raise ValueError("Google Drive belum terhubung atau token OAuth tidak valid.")
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
    return {
        "drive_file_id": result["id"],
        "drive_web_view_link": result.get("webViewLink"),
    }
