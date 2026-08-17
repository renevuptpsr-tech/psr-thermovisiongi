from __future__ import annotations

import uuid
from typing import Any

from .excel_parser import ParsedSheet
from .inspection import build_inspection_row


def _max_numeric(values: list[Any]) -> float | None:
    numeric = [float(value) for value in values if value is not None]
    return max(numeric) if numeric else None


def prepare_evaluation_rows(
    *,
    inspection_id: str,
    inspection_sheet_id: str,
    review_rows: list[dict[str, Any]],
    sheet_template_item_ids: set[int],
    metadata: dict[str, Any],
) -> list[dict[str, Any]]:
    """Ubah hasil review final menjadi record evaluasi yang dapat diaudit."""
    result: list[dict[str, Any]] = []
    for row in review_rows:
        item_id = int(row.get("Template item ID") or 0)
        if (
            item_id not in sheet_template_item_ids
            or str(row.get("Status analisa") or "").upper() != "TEREVALUASI"
        ):
            continue
        phase_delta = _max_numeric(
            [
                row.get("ΔT R-S (°C)"),
                row.get("ΔT S-T (°C)"),
                row.get("ΔT T-R (°C)"),
            ]
        )
        corrected_delta = _max_numeric(
            [
                row.get("ΔT evaluasi R (°C)"),
                row.get("ΔT evaluasi S (°C)"),
                row.get("ΔT evaluasi T (°C)"),
            ]
        )
        comparison_group = str(row.get("Comparison group code") or "").strip() or None
        if row.get("Pola gradasi"):
            scope = "GRADIENT"
        elif comparison_group:
            scope = "PAIR"
        elif phase_delta is not None:
            scope = "PHASE_GROUP"
        else:
            scope = "POINT"
        input_snapshot = {
            "temperature_r_c": row.get("Suhu R (°C)"),
            "temperature_s_c": row.get("Suhu S (°C)"),
            "temperature_t_c": row.get("Suhu T (°C)"),
            "temperature_c": row.get("Suhu (°C)"),
            "measurement_current_a": float(metadata["measurement_current_a"]),
            "highest_current_a": float(metadata["monthly_peak_current_a"]),
            "ambient_temperature_c": float(metadata["ambient_temperature_c"]),
            "delta_actual_r_c": row.get("ΔT aktual R (°C)"),
            "delta_actual_s_c": row.get("ΔT aktual S (°C)"),
            "delta_actual_t_c": row.get("ΔT aktual T (°C)"),
        }
        result.append(
            {
                "evaluation_id": str(uuid.uuid4()),
                "inspection_id": inspection_id,
                "inspection_sheet_id": inspection_sheet_id,
                "target_template_item_id": item_id,
                "point_code": row.get("Point code"),
                "equipment_group_code": row.get("Equipment group code"),
                "comparison_group_code": comparison_group,
                "evaluation_scope_code": scope,
                "rule_set_code": row.get("Rule set"),
                "rule_code": row.get("Kode aturan"),
                "rule_version": "1.0",
                "method": row.get("Metode analisa"),
                "evaluation_basis": row.get("Basis evaluasi"),
                "phase_delta_c": phase_delta,
                "ambient_delta_c": row.get("Kenaikan maks. terhadap lingkungan (°C)"),
                "corrected_delta_c": corrected_delta,
                "analyzed_delta_c": row.get("ΔT analisa (°C)"),
                "maximum_temperature_c": row.get("Suhu maksimum (°C)"),
                "gradient_pattern_code": row.get("Pola gradasi"),
                "condition_label": row.get("Kondisi"),
                "recommendation": row.get("Kesimpulan / rekomendasi"),
                "severity": int(row.get("Tingkat perhatian") or 0),
                "ahi_score": row.get("AHI Thermovisi"),
                "ahi_category": row.get("Kategori AHI"),
                "data_quality_status": row.get("Status data"),
                "analysis_status": row.get("Status analisa"),
                "input_snapshot": input_snapshot,
            }
        )
    return result


def prepare_inspection_groups(
    *,
    upload_id: str,
    template_code: str,
    parsed_sheets: list[ParsedSheet],
    sheet_assignments: dict[str, dict[str, str]],
    metadata_by_bay: dict[str, dict[str, Any]],
    executor: str | None,
    notes: str | None,
    user_id: str,
    work_type: str = "ROUTINE",
    stage_code: str = "TAHAP_1",
) -> list[dict[str, Any]]:
    """Satu Bay menjadi satu inspeksi dengan satu atau beberapa sheet sumber."""
    parsed_by_name = {sheet.sheet_name: sheet for sheet in parsed_sheets}
    missing = sorted(set(parsed_by_name) - set(sheet_assignments))
    if missing:
        raise ValueError("Sheet belum mempunyai penugasan Bay: " + ", ".join(missing))

    sheets_by_bay: dict[str, list[dict[str, Any]]] = {}
    for sheet_name, parsed in parsed_by_name.items():
        assignment = sheet_assignments[sheet_name]
        bay_id = str(assignment.get("bay_flc") or "").strip()
        role = str(assignment.get("sheet_role") or "").strip().upper()
        if not bay_id or role not in {"MAIN", "TRAFO", "BAY"}:
            raise ValueError(f"Penugasan sheet {sheet_name} tidak valid.")
        sheets_by_bay.setdefault(bay_id, []).append(
            {
                "parsed": parsed,
                "sheet_role_code": role,
                "form_section_code": assignment.get("form_section_code") or None,
            }
        )

    groups: list[dict[str, Any]] = []
    role_priority = {"MAIN": 0, "TRAFO": 1, "BAY": 2}
    for bay_id, sheets in sheets_by_bay.items():
        if bay_id not in metadata_by_bay:
            raise ValueError(f"Metadata untuk Bay {bay_id} belum tersedia.")
        roles = [sheet["sheet_role_code"] for sheet in sheets]
        if len(roles) != len(set(roles)):
            raise ValueError(f"Bay {bay_id} mempunyai peran sheet yang duplikat.")
        sheets.sort(key=lambda sheet: role_priority[sheet["sheet_role_code"]])
        primary_sheet = sheets[0]["parsed"].sheet_name
        inspection = build_inspection_row(
            inspection_id=str(uuid.uuid4()),
            upload_id=upload_id,
            target_functloc_id=bay_id,
            source_sheet_name=primary_sheet,
            template_code=template_code,
            metadata=metadata_by_bay[bay_id],
            executor=executor,
            notes=notes,
            user_id=user_id,
        )
        inspection["work_type"] = work_type
        inspection["stage_code"] = stage_code
        groups.append(
            {
                "bay_id": bay_id,
                "inspection": inspection,
                "ambient_temperature_c": float(
                    metadata_by_bay[bay_id]["ambient_temperature_c"]
                ),
                "sheets": sheets,
            }
        )
    return groups
