from __future__ import annotations

from typing import Any

import requests


def send_telegram_message(
    *,
    bot_token: str,
    chat_id: str,
    text: str,
    timeout_seconds: float = 20.0,
) -> dict[str, Any]:
    token = bot_token.strip()
    target = chat_id.strip()
    if not token or not target:
        raise ValueError("Bot token dan Chat ID Telegram wajib dikonfigurasi.")
    response = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": target, "text": text, "disable_web_page_preview": True},
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("ok"):
        raise RuntimeError(str(payload.get("description") or "Telegram menolak pesan."))
    result = payload.get("result") or {}
    return {
        "chat_id": str((result.get("chat") or {}).get("id") or target),
        "message_id": str(result.get("message_id") or ""),
    }
