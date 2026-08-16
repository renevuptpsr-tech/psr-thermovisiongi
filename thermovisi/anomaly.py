from __future__ import annotations

import uuid
from typing import Any


def prepare_anomaly_rows(
    *,
    inspection_id: str,
    evaluation_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Simpan hanya evaluasi yang memerlukan perhatian sebagai anomali."""
    result: list[dict[str, Any]] = []
    for evaluation in evaluation_rows:
        severity = int(evaluation.get("severity") or 0)
        if severity <= 0:
            continue
        result.append(
            {
                "anomaly_id": str(uuid.uuid4()),
                "evaluation_id": evaluation["evaluation_id"],
                "inspection_id": inspection_id,
                "equipment_group_code": evaluation.get("equipment_group_code"),
                "point_code": evaluation.get("point_code"),
                "condition_label": evaluation.get("condition_label") or "Anomali",
                "recommendation": evaluation.get("recommendation") or "Perlu evaluasi lanjutan.",
                "analyzed_delta_c": evaluation.get("analyzed_delta_c"),
                "maximum_temperature_c": evaluation.get("maximum_temperature_c"),
                "severity": severity,
                "ahi_score": evaluation.get("ahi_score"),
                "ahi_category": evaluation.get("ahi_category"),
                "anomaly_status": "OPEN",
                "notification_status": "PENDING",
            }
        )
    return result


def build_telegram_anomaly_message(
    *,
    ultg_name: str,
    gi_name: str,
    bay_name: str,
    bay_functloc_id: str,
    measurement_date: Any,
    work_type: str,
    stage_code: str,
    anomalies: list[dict[str, Any]],
    max_length: int = 3900,
) -> str:
    lines = [
        "ANOMALI THERMOVISI GI",
        "",
        f"ULTG: {ultg_name}",
        f"GI: {gi_name}",
        f"Bay: {bay_name}",
        f"FLC: {bay_functloc_id}",
        f"Pelaksanaan: {measurement_date}",
        f"Pekerjaan: {work_type} / {stage_code}",
        f"Jumlah anomali: {len(anomalies)}",
        "",
    ]
    for number, anomaly in enumerate(
        sorted(anomalies, key=lambda row: int(row.get("severity") or 0), reverse=True),
        start=1,
    ):
        delta = anomaly.get("analyzed_delta_c")
        delta_text = f"{float(delta):.1f} °C" if delta is not None else "-"
        lines.extend(
            [
                f"{number}. {anomaly.get('equipment_group_code') or '-'} / {anomaly.get('point_code') or '-'}",
                f"   Kondisi: {anomaly.get('condition_label') or '-'}",
                f"   Delta T: {delta_text}",
                f"   AHI: {anomaly.get('ahi_score') or '-'} ({anomaly.get('ahi_category') or '-'})",
                f"   Rekomendasi: {anomaly.get('recommendation') or '-'}",
                "",
            ]
        )
    message = "\n".join(lines).strip()
    if len(message) <= max_length:
        return message
    suffix = "\n\nPesan dipotong. Lihat detail lengkap pada aplikasi Thermovisi."
    return message[: max_length - len(suffix)].rstrip() + suffix
