from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SECRETS = PROJECT_ROOT / ".streamlit" / "secrets.toml"


def load_config(path: Path) -> tuple[str, str]:
    if not path.exists():
        raise FileNotFoundError(f"File tidak ditemukan: {path}")
    with path.open("rb") as handle:
        config = tomllib.load(handle)
    telegram = config.get("telegram") or {}
    token = str(telegram.get("bot_token") or "").strip()
    chat_id = str(telegram.get("chat_id") or "").strip()
    if not token or token.startswith("TOKEN_"):
        raise ValueError("telegram.bot_token belum dikonfigurasi dengan token yang valid.")
    return token, chat_id


def api(token: str, method: str, **payload: Any) -> dict[str, Any]:
    request = Request(
        f"https://api.telegram.org/bot{token}/{method}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        try:
            result = json.loads(exc.read().decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise RuntimeError(f"Telegram API gagal: HTTP {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError(f"Koneksi Telegram gagal: {exc.reason}") from exc
    if not result.get("ok"):
        description = result.get("description") or "Respons Telegram tidak berhasil."
        raise RuntimeError(f"Telegram API gagal: {description}")
    return result


def chat_candidates(updates: list[dict[str, Any]]) -> list[dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for update in updates:
        for key in ("message", "edited_message", "channel_post", "my_chat_member"):
            event = update.get(key) or {}
            chat = event.get("chat") or {}
            if chat.get("id") is None:
                continue
            chat_id = str(chat["id"])
            result[chat_id] = {
                "chat_id": chat_id,
                "type": str(chat.get("type") or "-"),
                "name": str(
                    chat.get("title")
                    or " ".join(
                        value for value in (chat.get("first_name"), chat.get("last_name")) if value
                    )
                    or chat.get("username")
                    or "-"
                ),
            }
    return list(result.values())


def main() -> int:
    parser = argparse.ArgumentParser(description="Uji konfigurasi Telegram Thermovisi.")
    parser.add_argument("--secrets", type=Path, default=DEFAULT_SECRETS)
    parser.add_argument("--send", action="store_true", help="Kirim pesan uji ke chat_id.")
    args = parser.parse_args()

    try:
        token, chat_id = load_config(args.secrets)
        bot = api(token, "getMe")["result"]
        print(f"[OK] Token valid untuk bot: @{bot.get('username')}")

        updates = api(token, "getUpdates").get("result") or []
        candidates = chat_candidates(updates)
        if candidates:
            print("[OK] Chat ID yang ditemukan:")
            for item in candidates:
                print(f"  - {item['chat_id']} | {item['type']} | {item['name']}")
        else:
            print("[INFO] Belum ada Chat ID pada getUpdates.")
            print("       Kirim /start ke bot atau /test@UsernameBot di grup, lalu jalankan ulang.")

        if args.send:
            if not chat_id:
                raise ValueError(
                    "telegram.chat_id masih kosong. Isi dari daftar Chat ID, lalu jalankan ulang."
                )
            sent = api(
                token,
                "sendMessage",
                chat_id=chat_id,
                text="Tes notifikasi Thermovisi berhasil.",
                disable_web_page_preview=True,
            )["result"]
            print(f"[OK] Pesan uji terkirim. message_id={sent.get('message_id')}")
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"[GAGAL] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
