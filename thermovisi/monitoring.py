from __future__ import annotations

from typing import Any


def build_upload_monitoring_rows(
    eligible_bays: list[dict[str, Any]],
    inspections: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Bandingkan master Bay eligible dengan realisasi upload terakhir per Bay."""
    latest_by_bay: dict[str, dict[str, Any]] = {}
    for inspection in inspections:
        bay_id = str(inspection["target_functloc_id"])
        current = latest_by_bay.get(bay_id)
        marker = (
            str(inspection.get("measurement_date") or ""),
            str(inspection.get("measurement_time") or ""),
            str(inspection.get("created_at") or ""),
        )
        current_marker = (
            str(current.get("measurement_date") or ""),
            str(current.get("measurement_time") or ""),
            str(current.get("created_at") or ""),
        ) if current else ("", "", "")
        if current is None or marker > current_marker:
            latest_by_bay[bay_id] = inspection

    rows: list[dict[str, Any]] = []
    for bay in eligible_bays:
        bay_id = str(bay["bay_flc"])
        inspection = latest_by_bay.get(bay_id)
        rows.append(
            {
                "ULTG": bay.get("ultg_name"),
                "Gardu Induk": bay.get("gi_name"),
                "Bay": bay.get("bay_name"),
                "Bay FLC": bay_id,
                "Fungsi": bay.get("bay_function_name") or bay.get("bay_function_code"),
                "Tegangan": bay.get("voltage_code"),
                "Status upload": "SUDAH UPLOAD" if inspection else "BELUM UPLOAD",
                "Tanggal pelaksanaan": inspection.get("measurement_date") if inspection else None,
                "Pukul": inspection.get("measurement_time") if inspection else None,
                "Inspection ID": inspection.get("inspection_id") if inspection else None,
            }
        )
    return rows
