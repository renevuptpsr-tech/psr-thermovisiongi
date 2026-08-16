from __future__ import annotations

import hashlib
import unicodedata
import uuid
from datetime import date, datetime, timezone
from typing import Any, Iterable

from supabase import Client, create_client

from .excel_parser import ParsedSheet
from .anomaly import build_telegram_anomaly_message, prepare_anomaly_rows
from .google_drive import upload_excel
from .retry import retry_read
from .storage_model import prepare_evaluation_rows, prepare_inspection_groups
from .telegram import send_telegram_message


def make_client(url: str, publishable_key: str, access_token: str | None = None, refresh_token: str | None = None) -> Client:
    client = create_client(url, publishable_key)
    if access_token and refresh_token:
        # set_session memanggil Auth /user. Pada jaringan Windows/proxy yang
        # tidak stabil, panggilan baca ini aman untuk dicoba ulang.
        retry_read(
            lambda: client.auth.set_session(access_token, refresh_token),
            attempts=3,
            initial_delay_seconds=0.75,
        )
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
        "measurement_mode_code,phase_codes,source_value_map,section_code,terminal_side_code,"
        "position_code,instance_no,winding_code,terminal_voltage_kv,comparison_group_code,"
        "comparison_role,analysis_rule_code,is_required"
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
        lambda: client.table("v_thermovisi_eligible_bay")
        .select(
            "ultg_flc,ultg_name,gi_flc,gi_name,bay_flc,bay_name,bay_short_name,"
            "bay_function_code,bay_function_name,voltage_code,is_routine_required,"
            "monitoring_category"
        )
        .eq("ultg_flc", ultg_flc)
        .eq("gi_flc", gi_flc)
        .order("bay_name")
        .execute()
        .data
    )


def fetch_eligible_bays(
    client: Client,
    *,
    ultg_flc: str | None = None,
    gi_flc: str | None = None,
    required_only: bool = False,
) -> list[dict[str, Any]]:
    def read():
        query = client.table("v_thermovisi_eligible_bay").select("*")
        if ultg_flc:
            query = query.eq("ultg_flc", ultg_flc)
        if gi_flc:
            query = query.eq("gi_flc", gi_flc)
        if required_only:
            query = query.eq("is_routine_required", True)
        return query.order("gi_name").order("bay_name").execute().data

    return retry_read(read)


def fetch_inspection_completions(
    client: Client,
    *,
    period_start: date,
    period_end: date,
    work_type: str,
    stage_code: str,
) -> list[dict[str, Any]]:
    return retry_read(
        lambda: client.table("trx_thermovisi_inspection")
        .select(
            "inspection_id,target_functloc_id,measurement_date,measurement_time,"
            "inspection_status,work_type,stage_code,created_at"
        )
        .gte("measurement_date", period_start.isoformat())
        .lt("measurement_date", period_end.isoformat())
        .eq("work_type", work_type)
        .eq("stage_code", stage_code)
        .order("measurement_date", desc=True)
        .execute()
        .data
    )


def file_sha256(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()


def duplicate_upload(client: Client, file_hash: str) -> dict[str, Any] | None:
    rows = retry_read(
        lambda: client.table("trx_thermovisi_upload")
        .select(
            "upload_id,original_filename,processing_status,template_type,total_sheets,"
            "processed_sheets,total_measurements,drive_file_id,drive_folder_id,"
            "drive_web_view_link,created_at"
        )
        .eq("file_hash", file_hash)
        .limit(1)
        .execute()
        .data
    )
    return rows[0] if rows else None


def _sheet_key(value: Any) -> str:
    return unicodedata.normalize("NFKC", str(value or "")).strip().casefold()


def _existing_import_details(
    client: Client,
    upload_id: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    inspections = retry_read(
        lambda: client.table("trx_thermovisi_inspection")
        .select(
            "inspection_id,target_functloc_id,measurement_date,work_type,stage_code,"
            "source_sheet_name"
        )
        .eq("upload_id", upload_id)
        .execute()
        .data
    )
    inspection_ids = [row["inspection_id"] for row in inspections]
    if not inspection_ids:
        return inspections, []

    sheets: list[dict[str, Any]] = []
    for id_batch in _value_chunks(inspection_ids):
        sheets.extend(
            retry_read(
                lambda batch=id_batch: client.table("trx_thermovisi_inspection_sheet")
                .select("inspection_id,source_sheet_name,sheet_role_code")
                .in_("inspection_id", batch)
                .execute()
                .data
            )
        )
    return inspections, sheets


def _validate_incremental_import(
    *,
    existing_upload: dict[str, Any],
    existing_inspections: list[dict[str, Any]],
    existing_sheets: list[dict[str, Any]],
    template_code: str,
    selected_sheet_names: set[str],
    destination_year: int,
    destination_month: int,
    work_type: str,
    stage_code: str,
) -> None:
    if existing_upload.get("processing_status") == "PROCESSING":
        raise ValueError(
            f"Workbook ini sedang diproses (upload_id {existing_upload['upload_id']}). "
            "Tunggu proses sebelumnya selesai."
        )
    if str(existing_upload.get("template_type") or "") != template_code:
        raise ValueError(
            "Workbook yang sama sudah terdaftar dengan template "
            f"{existing_upload.get('template_type') or '-'}, bukan {template_code}."
        )

    existing_sheet_by_key = {
        _sheet_key(row.get("source_sheet_name")): str(row.get("source_sheet_name") or "")
        for row in existing_sheets
    }
    reused = sorted(
        existing_sheet_by_key[_sheet_key(sheet_name)]
        for sheet_name in selected_sheet_names
        if _sheet_key(sheet_name) in existing_sheet_by_key
    )
    if reused:
        raise ValueError(
            "Sheet berikut sudah pernah diimpor dari workbook ini: "
            + ", ".join(reused)
            + ". Pilih hanya sheet yang belum diproses."
        )

    for inspection in existing_inspections:
        measurement_date = date.fromisoformat(str(inspection["measurement_date"]))
        if (measurement_date.year, measurement_date.month) != (
            destination_year,
            destination_month,
        ):
            raise ValueError(
                "Workbook yang sama sudah digunakan untuk periode "
                f"{measurement_date.month:02d}/{measurement_date.year}. "
                "Impor lanjutan harus memakai bulan dan tahun yang sama."
            )
        if (
            str(inspection.get("work_type") or "") != work_type
            or str(inspection.get("stage_code") or "") != stage_code
        ):
            raise ValueError(
                "Workbook yang sama sudah digunakan untuk jenis pekerjaan/tahap "
                f"{inspection.get('work_type')} · {inspection.get('stage_code')}."
            )


def _routine_duplicate_bays(
    client: Client,
    *,
    bay_ids: list[str],
    destination_year: int,
    destination_month: int,
    stage_code: str,
) -> list[str]:
    period_start = date(destination_year, destination_month, 1)
    period_end = (
        date(destination_year + 1, 1, 1)
        if destination_month == 12
        else date(destination_year, destination_month + 1, 1)
    )
    rows: list[dict[str, Any]] = []
    for bay_batch in _value_chunks(bay_ids):
        rows.extend(
            retry_read(
                lambda batch=bay_batch: client.table("trx_thermovisi_inspection")
                .select("target_functloc_id")
                .in_("target_functloc_id", batch)
                .gte("measurement_date", period_start.isoformat())
                .lt("measurement_date", period_end.isoformat())
                .eq("work_type", "ROUTINE")
                .eq("stage_code", stage_code)
                .execute()
                .data
            )
        )
    return sorted({str(row["target_functloc_id"]) for row in rows})


def _chunks(values: list[dict[str, Any]], size: int = 500) -> Iterable[list[dict[str, Any]]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


def _value_chunks(values: list[str], size: int = 100) -> Iterable[list[str]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


def save_import(
    client: Client,
    *,
    file_bytes: bytes,
    filename: str,
    mime_type: str,
    folder_id: str,
    drive_web_app_url: str,
    drive_shared_secret: str,
    drive_gi_name: str,
    template_code: str,
    parsed_sheets: list[ParsedSheet],
    sheet_assignments: dict[str, dict[str, str]],
    metadata_by_bay: dict[str, dict[str, Any]],
    review_rows_by_bay: dict[str, list[dict[str, Any]]],
    executor: str | None,
    notes: str | None,
    user_id: str,
    work_type: str,
    stage_code: str,
    telegram_bot_token: str = "",
    telegram_chat_id: str = "",
    location_by_bay: dict[str, dict[str, str]] | None = None,
    workbook_sheet_count: int | None = None,
) -> str:
    digest = file_sha256(file_bytes)
    periods = {
        (
            int(metadata["measurement_date"].year),
            int(metadata["measurement_date"].month),
        )
        for metadata in metadata_by_bay.values()
    }
    if len(periods) != 1:
        raise ValueError(
            "Semua Bay dalam satu file harus memiliki bulan dan tahun pelaksanaan yang sama."
        )
    destination_year, destination_month = next(iter(periods))
    source_upload = duplicate_upload(client, digest)
    is_incremental = source_upload is not None
    if source_upload:
        upload_id = str(source_upload["upload_id"])
        existing_inspections, existing_sheets = _existing_import_details(client, upload_id)
        _validate_incremental_import(
            existing_upload=source_upload,
            existing_inspections=existing_inspections,
            existing_sheets=existing_sheets,
            template_code=template_code,
            selected_sheet_names=set(sheet_assignments),
            destination_year=destination_year,
            destination_month=destination_month,
            work_type=work_type,
            stage_code=stage_code,
        )
    else:
        upload_id = str(uuid.uuid4())

    bay_ids = sorted(metadata_by_bay)
    if work_type == "ROUTINE":
        duplicate_bays = _routine_duplicate_bays(
            client,
            bay_ids=bay_ids,
            destination_year=destination_year,
            destination_month=destination_month,
            stage_code=stage_code,
        )
        if duplicate_bays:
            raise ValueError(
                "Inspeksi rutin sudah tersimpan untuk Bay/periode/tahap yang sama: "
                + ", ".join(duplicate_bays)
            )

    prepared_inspections = prepare_inspection_groups(
        upload_id=upload_id,
        template_code=template_code,
        parsed_sheets=parsed_sheets,
        sheet_assignments=sheet_assignments,
        metadata_by_bay=metadata_by_bay,
        executor=executor,
        notes=notes,
        user_id=user_id,
        work_type=work_type,
        stage_code=stage_code,
    )

    if not source_upload:
        drive = upload_excel(
            file_bytes,
            filename,
            mime_type,
            folder_id,
            destination_year=destination_year,
            destination_gi=drive_gi_name,
            destination_month=destination_month,
            web_app_url=drive_web_app_url,
            shared_secret=drive_shared_secret,
        )
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
            "total_sheets": workbook_sheet_count or len(parsed_sheets),
            "uploaded_by": user_id,
        }
        client.table("trx_thermovisi_upload").insert(upload_row).execute()

    try:
        total_measurements = 0
        total_evaluations = 0
        anomalies_by_inspection: dict[str, list[dict[str, Any]]] = {}
        prepared_by_inspection: dict[str, dict[str, Any]] = {}
        for prepared in prepared_inspections:
            inspection = prepared["inspection"]
            ambient_c = prepared["ambient_temperature_c"]
            inspection_id = inspection["inspection_id"]
            prepared_by_inspection[inspection_id] = prepared
            client.table("trx_thermovisi_inspection").insert(inspection).execute()
            for sheet in prepared["sheets"]:
                parsed = sheet["parsed"]
                inspection_sheet_id = str(uuid.uuid4())
                client.table("trx_thermovisi_inspection_sheet").insert({
                    "inspection_sheet_id": inspection_sheet_id,
                    "inspection_id": inspection_id,
                    "sheet_role_code": sheet["sheet_role_code"],
                    "source_sheet_name": parsed.sheet_name,
                    "form_section_code": sheet["form_section_code"],
                    "numeric_count": parsed.numeric_count,
                    "invalid_count": parsed.invalid_count,
                    "warning_count": parsed.warning_count,
                    "not_measured_count": parsed.not_measured_count,
                    "not_applicable_count": parsed.not_applicable_count,
                }).execute()

                rows = []
                for measurement in parsed.measurements:
                    if measurement.temperature_c is None:
                        continue
                    rows.append({
                        "inspection_id": inspection_id,
                        "inspection_sheet_id": inspection_sheet_id,
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

                sheet_item_ids = {
                    int(measurement.template_item_id)
                    for measurement in parsed.measurements
                }
                evaluation_rows = prepare_evaluation_rows(
                    inspection_id=inspection_id,
                    inspection_sheet_id=inspection_sheet_id,
                    review_rows=review_rows_by_bay.get(prepared["bay_id"], []),
                    sheet_template_item_ids=sheet_item_ids,
                    metadata=metadata_by_bay[prepared["bay_id"]],
                )
                for batch in _chunks(evaluation_rows):
                    client.table("trx_thermovisi_evaluation").insert(batch).execute()
                total_evaluations += len(evaluation_rows)
                anomaly_rows = prepare_anomaly_rows(
                    inspection_id=inspection_id,
                    evaluation_rows=evaluation_rows,
                )
                for batch in _chunks(anomaly_rows):
                    client.table("trx_thermovisi_anomaly").insert(batch).execute()
                anomalies_by_inspection.setdefault(inspection_id, []).extend(anomaly_rows)

        previous_processed_sheets = int((source_upload or {}).get("processed_sheets") or 0)
        previous_measurements = int((source_upload or {}).get("total_measurements") or 0)
        known_total_sheets = max(
            int((source_upload or {}).get("total_sheets") or 0),
            int(workbook_sheet_count or 0),
            previous_processed_sheets + len(parsed_sheets),
        )
        cumulative_processed_sheets = previous_processed_sheets + len(parsed_sheets)
        cumulative_measurements = previous_measurements + total_measurements
        client.table("trx_thermovisi_upload").update({
            "processing_status": "COMPLETED",
            "processing_message": (
                f"Import {'lanjutan' if is_incremental else 'awal'} berhasil: "
                f"{len(parsed_sheets)} sheet, {total_measurements} pengukuran, "
                f"{total_evaluations} evaluasi. Total diproses: "
                f"{cumulative_processed_sheets}/{known_total_sheets} sheet."
            ),
            "total_sheets": known_total_sheets,
            "processed_sheets": cumulative_processed_sheets,
            "total_measurements": cumulative_measurements,
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }).eq("upload_id", upload_id).execute()

        if telegram_bot_token.strip() and telegram_chat_id.strip():
            for inspection_id, anomaly_rows in anomalies_by_inspection.items():
                if not anomaly_rows:
                    continue
                prepared = prepared_by_inspection[inspection_id]
                bay_id = prepared["bay_id"]
                location = (location_by_bay or {}).get(bay_id, {})
                anomaly_ids = [row["anomaly_id"] for row in anomaly_rows]
                try:
                    message = build_telegram_anomaly_message(
                        ultg_name=location.get("ultg_name") or "-",
                        gi_name=location.get("gi_name") or drive_gi_name,
                        bay_name=location.get("bay_name") or bay_id,
                        bay_functloc_id=bay_id,
                        measurement_date=metadata_by_bay[bay_id]["measurement_date"],
                        work_type=work_type,
                        stage_code=stage_code,
                        anomalies=anomaly_rows,
                    )
                    sent = send_telegram_message(
                        bot_token=telegram_bot_token,
                        chat_id=telegram_chat_id,
                        text=message,
                    )
                    client.table("trx_thermovisi_anomaly").update({
                        "notification_status": "SENT",
                        "telegram_chat_id": sent["chat_id"],
                        "telegram_message_id": sent["message_id"],
                        "notification_attempts": 1,
                        "notification_error": None,
                        "notified_at": datetime.now(timezone.utc).isoformat(),
                    }).in_("anomaly_id", anomaly_ids).execute()
                except Exception as notification_error:
                    try:
                        client.table("trx_thermovisi_anomaly").update({
                            "notification_status": "FAILED",
                            "telegram_chat_id": telegram_chat_id,
                            "notification_attempts": 1,
                            "notification_error": str(notification_error)[:1000],
                        }).in_("anomaly_id", anomaly_ids).execute()
                    except Exception:
                        # Gangguan pencatatan notifikasi tidak boleh membatalkan
                        # inspeksi dan hasil evaluasi yang sudah tersimpan.
                        pass
        return upload_id
    except Exception as exc:
        if not is_incremental:
            client.table("trx_thermovisi_upload").update({
                "processing_status": "FAILED",
                "processing_message": str(exc)[:1000],
                "processed_at": datetime.now(timezone.utc).isoformat(),
            }).eq("upload_id", upload_id).execute()
        raise
