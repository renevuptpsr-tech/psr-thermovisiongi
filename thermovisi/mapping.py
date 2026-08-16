from __future__ import annotations

from collections.abc import Iterable
from typing import Any


SINGLE_SHEET_MODE = "SINGLE_SHEET"
TRAFO_TWO_SHEET_MODE = "TRAFO_TWO_SHEET"


def mapping_mode_from_template(
    template_meta: dict[str, Any] | None,
    template_items: Iterable[dict[str, Any]],
) -> str:
    """Tentukan kebutuhan sheet dari template, tanpa bergantung pada nama sheet Excel."""
    meta = template_meta or {}
    identity = " ".join(
        str(meta.get(key) or "")
        for key in ("template_code", "template_name", "description")
    ).upper()
    sections = {
        str(item.get("form_section_code") or "").strip().upper()
        for item in template_items
    }
    is_trafo = "TRAFO" in identity or "IBT" in identity or {"A", "B"}.issubset(sections)
    return TRAFO_TWO_SHEET_MODE if is_trafo else SINGLE_SHEET_MODE


def sheet_mapping_from_bays(
    rows: Iterable[dict[str, Any]],
    *,
    expected_bay_ids: list[str],
    valid_sheet_names: list[str],
) -> tuple[dict[str, str], list[str]]:
    """Ubah pilihan Bay -> sheet menjadi mapping sheet -> Bay untuk proses simpan."""
    expected = set(expected_bay_ids)
    valid_sheets = set(valid_sheet_names)
    bay_to_sheet: dict[str, str] = {}
    sheet_to_bay: dict[str, str] = {}
    errors: list[str] = []

    for row in rows:
        bay_id = str(row.get("bay_flc") or "").strip()
        raw_sheet_name = row.get("Sheet Excel")
        sheet_name = str(raw_sheet_name or "").strip()
        if sheet_name.casefold() in {"nan", "none", "<na>"}:
            sheet_name = ""
        if bay_id not in expected or not sheet_name:
            continue
        if sheet_name not in valid_sheets:
            errors.append(f"Sheet '{sheet_name}' tidak ditemukan dalam hasil validasi Excel.")
            continue
        if bay_id in bay_to_sheet:
            errors.append(f"Bay {bay_id} muncul lebih dari satu kali pada pemetaan.")
            continue
        if sheet_name in sheet_to_bay:
            errors.append(
                f"Sheet '{sheet_name}' sudah dipilih untuk Bay {sheet_to_bay[sheet_name]}. "
                "Satu sheet hanya boleh digunakan untuk satu Bay."
            )
            continue
        bay_to_sheet[bay_id] = sheet_name
        sheet_to_bay[sheet_name] = bay_id

    missing = [bay_id for bay_id in expected_bay_ids if bay_id not in bay_to_sheet]
    if missing:
        errors.append(f"Pilih sheet Excel untuk setiap Bay. Belum dipilih: {', '.join(missing)}.")

    return sheet_to_bay, errors


def trafo_sheet_mapping_from_bays(
    rows: Iterable[dict[str, Any]],
    *,
    expected_bay_ids: list[str],
    valid_sheet_names: list[str],
    sheet_sections: dict[str, set[str]] | None = None,
) -> tuple[dict[str, dict[str, str]], list[str]]:
    """Pemetaan satu Bay Trafo ke dua sheet: TRAFO (A) dan BAY (B)."""
    expected = set(expected_bay_ids)
    valid_sheets = set(valid_sheet_names)
    sections = sheet_sections or {}
    assignments: dict[str, dict[str, str]] = {}
    completed_roles: dict[str, set[str]] = {bay_id: set() for bay_id in expected_bay_ids}
    errors: list[str] = []
    role_specs = (
        ("TRAFO", "Sheet Trafo", "A"),
        ("BAY", "Sheet Bay", "B"),
    )

    for row in rows:
        bay_id = str(row.get("bay_flc") or "").strip()
        if bay_id not in expected:
            continue
        for role, column_name, expected_section in role_specs:
            raw_sheet_name = row.get(column_name)
            sheet_name = str(raw_sheet_name or "").strip()
            if sheet_name.casefold() in {"nan", "none", "<na>"}:
                sheet_name = ""
            if not sheet_name:
                continue
            if sheet_name not in valid_sheets:
                errors.append(f"Sheet '{sheet_name}' tidak ditemukan dalam hasil validasi Excel.")
                continue
            if sheet_name in assignments:
                previous = assignments[sheet_name]
                errors.append(
                    f"Sheet '{sheet_name}' sudah digunakan sebagai {previous['sheet_role']} "
                    f"untuk Bay {previous['bay_flc']}. Satu sheet hanya boleh digunakan sekali."
                )
                continue
            detected_sections = sections.get(sheet_name, set())
            if detected_sections and expected_section not in detected_sections:
                errors.append(
                    f"Sheet '{sheet_name}' dipilih sebagai {column_name}, tetapi isinya terdeteksi "
                    f"sebagai bagian {', '.join(sorted(detected_sections))}."
                )
                continue
            assignments[sheet_name] = {
                "bay_flc": bay_id,
                "sheet_role": role,
                "form_section_code": expected_section,
            }
            completed_roles[bay_id].add(role)

    for bay_id in expected_bay_ids:
        missing_roles = [role for role in ("TRAFO", "BAY") if role not in completed_roles[bay_id]]
        if missing_roles:
            labels = ", ".join("Sheet Trafo" if role == "TRAFO" else "Sheet Bay" for role in missing_roles)
            errors.append(f"Bay {bay_id} belum memilih: {labels}.")

    return assignments, errors
