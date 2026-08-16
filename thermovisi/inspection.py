from __future__ import annotations

from datetime import date, datetime, time
from typing import Any


def _date_iso(value: Any) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return date.fromisoformat(str(value)).isoformat()


def _time_iso(value: Any) -> str:
    if isinstance(value, datetime):
        value = value.time()
    if isinstance(value, time):
        return value.replace(microsecond=0).isoformat()
    return time.fromisoformat(str(value)).replace(microsecond=0).isoformat()


def build_inspection_row(
    *,
    inspection_id: str,
    upload_id: str,
    target_functloc_id: str,
    source_sheet_name: str,
    template_code: str,
    metadata: dict[str, Any],
    executor: str | None,
    notes: str | None,
    user_id: str,
) -> dict[str, Any]:
    current_a = float(metadata["measurement_current_a"])
    peak_a = float(metadata["monthly_peak_current_a"])
    ambient_c = float(metadata["ambient_temperature_c"])
    if current_a < 0 or peak_a < 0:
        raise ValueError(f"Beban Bay {target_functloc_id} tidak boleh negatif.")
    if current_a > 0 and peak_a < current_a:
        raise ValueError(
            f"Beban tertinggi Bay {target_functloc_id} tidak boleh lebih kecil dari beban pengukuran."
        )
    if not -50 <= ambient_c <= 100:
        raise ValueError(f"Suhu lingkungan Bay {target_functloc_id} berada di luar -50 sampai 100 °C.")

    return {
        "inspection_id": inspection_id,
        "upload_id": upload_id,
        "target_functloc_id": target_functloc_id,
        "source_sheet_name": source_sheet_name,
        "measurement_date": _date_iso(metadata["measurement_date"]),
        "measurement_time": _time_iso(metadata["measurement_time"]),
        "measurement_current_a": current_a,
        "monthly_peak_current_a": peak_a,
        "ambient_temperature_c": ambient_c,
        "executor": executor or None,
        "inspection_status": "PROCESSED",
        "notes": notes or None,
        "created_by": user_id,
        "template_code": template_code,
    }
