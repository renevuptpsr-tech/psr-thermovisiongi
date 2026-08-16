import pytest

from thermovisi.google_drive import (
    normalize_drive_folder_id,
    normalize_oauth_client_config,
)


def oauth_info():
    return {
        "project_id": "project-id",
        "client_id": "client-id.apps.googleusercontent.com",
        "client_secret": "client-secret",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"],
    }


def test_oauth_toml_is_wrapped_as_installed_client():
    result = normalize_oauth_client_config(oauth_info())
    assert result["installed"]["client_id"].endswith(".apps.googleusercontent.com")
    assert result["installed"]["redirect_uris"] == ["http://localhost"]


def test_oauth_accepts_downloaded_json_shape():
    result = normalize_oauth_client_config({"installed": oauth_info()})
    assert result["installed"]["client_secret"] == "client-secret"


def test_oauth_placeholder_is_rejected():
    value = oauth_info()
    value["client_secret"] = "GANTI_DARI_JSON_OAUTH_DESKTOP"
    with pytest.raises(ValueError, match="placeholder"):
        normalize_oauth_client_config(value)


def test_drive_folder_accepts_id_or_full_url():
    folder_id = "1mWx5bX5siYp0d63h1VSy0QHsblOXJT6i"
    assert normalize_drive_folder_id(folder_id) == folder_id
    assert normalize_drive_folder_id(
        f"https://drive.google.com/drive/folders/{folder_id}?usp=drive_link"
    ) == folder_id
