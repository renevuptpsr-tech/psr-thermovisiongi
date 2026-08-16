from __future__ import annotations

import uuid
from typing import Any

from .excel_parser import ParsedSheet
from .inspection import build_inspection_row


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
