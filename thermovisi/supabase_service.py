from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable

from supabase import Client, create_client

from .excel_parser import ParsedSheet
from .google_drive import upload_excel
from .inspection import build_inspection_row
from .retry import retry_read


def make_client(url: str, publishable_key: str, access_token: str | None = None, refresh_token: str | None = None) -> Client:
    client = create_client(url, publishable_key)
    if access_token and refresh_token:
        client.auth.set_session(access_token, refresh_token)
    return client


def sign_in(client: Client, email: str, password: str) -> dict[str, Any]:
    response = client.auth.sign_in_with_password({"email": email, "password": password})
    return {
        "user_id": str(response.user.id),
        "email": response.user.email,
        "access_token": response.session.access_token,
        "refresh_token": response.session.refresh_token,
    }


def fetch_templates(client: Client) -> list[dict[str, Any]]:
    return retry_read(
        lambda: (
            client.table("ref_thermovisi_template")
            .select("template_code,template_name,function_code,voltage_code,is_default,description")
            .eq("is_active", True)
            .order("template_name")
            .execute()
            .data
        )
    )


def fetch_template_items(client: Client, template_code: str) -> list[dict[str, Any]]:
    fields = (
        "template_item_id,form_section_code,sequence_no,source_sheet_pattern,source_row_no,"
        "source_occurrence_no,raw_equipment_label,raw_point_label,equipment_group_code,point_code,"
        "measurement_mode_code,phase_codes,source_value_map,is_required"
    )
    return retry_read(
        lambda: (
            client.table("ref_thermovisi_template_item")
            .select(fields)
            .eq("template_code", template_code)
            .eq("is_active", True)
            .order("form_section_code")
            .order("sequence_no")
            .execute()
            .data
        )
    )


def fetch_ultg(client: Client) -> list[dict[str, Any]]:
    return retry_read(
        lambda: client.table("v_dropdown_ultg")
        .select("ultg_flc,ultg_name")
        .order("ultg_name")
        .execute()
        .data
    )


def fetch_gi(client: Client, ultg_flc: str) -> list[dict[str, Any]]:
    return retry_read(
        lambda: client.table("v_dropdown_gi")
        .select("ultg_flc,gi_flc,gi_name")
        .eq("ultg_flc", ultg_flc)
        .order("gi_name")
        .execute()
        .data
    )


def fetch_bays(client: Client, ultg_flc: str, gi_flc: str) -> list[dict[str, Any]]:
    return retry_read(
        lambda: client.table("v_dropdown_bay")
        .select("ultg_flc,gi_flc,bay_flc,bay_name,bay_short_name,bay_function_code,voltage_code")
        .eq("ultg_flc", ultg_flc)
        .eq("gi_flc", gi_flc)
        .order("bay_name")
        .execute()
        .data
    )


def file_sha256(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()


def duplicate_upload(client: Client, file_hash: str) -> dict[str, Any] | None:
    rows = retry_read(
        lambda: client.table("trx_thermovisi_upload")
        .select("upload_id,original_filename,processing_status,created_at")
        .eq("file_hash", file_hash)
        .limit(1)
        .execute()
        .data
    )
    return rows[0] if rows else None


def _chunks(values: list[dict[str, Any]], size: int = 500) -> Iterable[list[dict[str, Any]]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


def save_import(
    client: Client,
    *,
    file_bytes: bytes,
    filename: str,
    mime_type: str,
    folder_id: str,
    service_account_info: dict[str, Any],
    template_code: str,
    parsed_sheets: list[ParsedSheet],
    sheet_to_bay: dict[str, str],
    metadata_by_bay: dict[str, dict[str, Any]],
    executor: str | None,
    notes: str | None,
    user_id: str,
) -> str:
    digest = file_sha256(file_bytes)
    duplicate = duplicate_upload(client, digest)
    if duplicate:
        raise ValueError(f"File sudah pernah diunggah (status {duplicate['processing_status']}, upload_id {duplicate['upload_id']}).")

    upload_id = str(uuid.uuid4())
    prepared_inspections: list[tuple[ParsedSheet, dict[str, Any], float]] = []
    for parsed in parsed_sheets:
        target_bay = sheet_to_bay[parsed.sheet_name]
        if target_bay not in metadata_by_bay:
            raise ValueError(f"Metadata untuk Bay {target_bay} belum tersedia.")
        metadata = metadata_by_bay[target_bay]
        inspection = build_inspection_row(
            inspection_id=str(uuid.uuid4()),
            upload_id=upload_id,
            target_functloc_id=target_bay,
            source_sheet_name=parsed.sheet_name,
            template_code=template_code,
            metadata=metadata,
            executor=executor,
            notes=notes,
            user_id=user_id,
        )
        prepared_inspections.append((parsed, inspection, float(metadata["ambient_temperature_c"])))

    drive = upload_excel(file_bytes, filename, mime_type, folder_id, service_account_info)
    upload_row = {
        "upload_id": upload_id,
        "file_provider": "GOOGLE_DRIVE",
        "drive_file_id": drive["drive_file_id"],
        "drive_folder_id": folder_id or None,
        "drive_web_view_link": drive["drive_web_view_link"],
        "original_filename": filename,
        "file_hash": digest,
        "file_size_bytes": len(file_bytes),
        "mime_type": mime_type,
        "template_type": template_code,
        "processing_status": "PROCESSING",
        "total_sheets": len(parsed_sheets),
        "uploaded_by": user_id,
    }
    client.table("trx_thermovisi_upload").insert(upload_row).execute()

    try:
        total_measurements = 0
        for parsed, inspection, ambient_c in prepared_inspections:
            inspection_id = inspection["inspection_id"]
            client.table("trx_thermovisi_inspection").insert(inspection).execute()

            rows = []
            for measurement in parsed.measurements:
                if measurement.temperature_c is None:
                    continue
                rows.append({
                    "inspection_id": inspection_id,
                    "template_item_id": measurement.template_item_id,
                    "point_code": measurement.point_code,
                    "equipment_group_code": measurement.equipment_group_code,
                    "phase_code": measurement.phase_code,
                    "temperature_c": measurement.temperature_c,
                    "source_cell_address": measurement.source_cell_address,
                    "source_value_raw": measurement.source_value_raw,
                    "delta_ambient_c": round(measurement.temperature_c - ambient_c, 3),
                    "data_quality_status": measurement.data_quality_status,
                    "validation_message": measurement.validation_message,
                })
            for batch in _chunks(rows):
                client.table("trx_thermovisi_measurement").insert(batch).execute()
            total_measurements += len(rows)

        client.table("trx_thermovisi_upload").update({
            "processing_status": "COMPLETED",
            "processing_message": "Import berhasil",
            "processed_sheets": len(parsed_sheets),
            "total_measurements": total_measurements,
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }).eq("upload_id", upload_id).execute()
        return upload_id
    except Exception as exc:
        client.table("trx_thermovisi_upload").update({
            "processing_status": "FAILED",
            "processing_message": str(exc)[:1000],
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }).eq("upload_id", upload_id).execute()
        raise
