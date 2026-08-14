from __future__ import annotations

import os
import re
from datetime import date, datetime
from typing import Any

import pandas as pd
import streamlit as st

from thermovisi.excel_parser import parse_workbook, preview_rows
from thermovisi.supabase_service import (
    fetch_bays,
    fetch_gi,
    fetch_template_items,
    fetch_templates,
    fetch_ultg,
    file_sha256,
    make_client,
    save_import,
    sign_in,
)


st.set_page_config(page_title="Thermovision GI", page_icon="🌡️", layout="wide")
st.markdown(
    """
    <style>
      .block-container {padding-top: 2rem; padding-bottom: 3rem; max-width: 1500px;}
      h1, h2, h3 {letter-spacing: -0.02em;}
      [data-testid="stMetric"] {background: #f5f9fa; border: 1px solid #dbe8eb; padding: 0.8rem 1rem; border-radius: 0.75rem;}
    </style>
    """,
    unsafe_allow_html=True,
)
st.title("Thermovision Gardu Induk")
st.caption("Impor hasil pengukuran · validasi Python · penyimpanan terstruktur Supabase")


def secret(name: str, default: str = "") -> str:
    return os.getenv(name) or st.secrets.get(name, default)


def authenticated_client():
    cached_client = st.session_state.get("supabase_client")
    if cached_client is not None:
        return cached_client
    auth = st.session_state.get("auth") or {}
    client = make_client(
        secret("SUPABASE_URL"),
        secret("SUPABASE_KEY"),
        auth.get("access_token"),
        auth.get("refresh_token"),
    )
    session = client.auth.get_session()
    if session:
        st.session_state.auth.update(
            {"access_token": session.access_token, "refresh_token": session.refresh_token}
        )
    st.session_state.supabase_client = client
    return client


def stop_for_reference_error(error: Exception) -> None:
    st.error(f"Koneksi ke Supabase terputus saat membaca referensi: {error}")
    st.caption(
        "Proyek Supabase terdeteksi aktif. Gangguan ini biasanya bersifat sementara atau berasal dari jaringan/proxy lokal."
    )
    if st.button("Coba baca ulang", type="primary"):
        st.session_state.supabase_client = None
        st.session_state.reference_cache = {
            "gi": {}, "bays": {}, "template_items": {}
        }
        st.rerun()
    st.stop()


def bay_label(row: dict[str, Any]) -> str:
    short_name = (row.get("bay_short_name") or row.get("bay_name") or "Bay").strip()
    return f"{short_name} — {row['bay_flc']}"


def normalise_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def metadata_from_editor(frame: pd.DataFrame) -> tuple[dict[str, dict[str, Any]], list[str]]:
    result: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for _, row in frame.iterrows():
        bay_id = str(row["bay_flc"])
        name = str(row["Bay"])
        required = [
            "Tanggal pelaksanaan",
            "Pukul pelaksanaan",
            "Beban pengukuran (A)",
            "Beban tertinggi bulan (A)",
            "Suhu lingkungan (°C)",
        ]
        if any(pd.isna(row[field]) for field in required):
            errors.append(f"Metadata {name} belum lengkap.")
            continue
        try:
            current_a = float(row["Beban pengukuran (A)"])
            peak_a = float(row["Beban tertinggi bulan (A)"])
            ambient_c = float(row["Suhu lingkungan (°C)"])
        except (TypeError, ValueError):
            errors.append(f"Beban atau suhu {name} bukan angka yang valid.")
            continue
        if current_a <= 0 or peak_a <= 0:
            errors.append(f"Beban {name} harus lebih besar dari 0 A.")
        if peak_a < current_a:
            errors.append(f"Beban tertinggi {name} lebih kecil dari beban pengukuran.")
        if not -50 <= ambient_c <= 100:
            errors.append(f"Suhu lingkungan {name} harus berada pada -50 sampai 100 °C.")
        result[bay_id] = {
            "measurement_date": row["Tanggal pelaksanaan"],
            "measurement_time": row["Pukul pelaksanaan"],
            "measurement_current_a": current_a,
            "monthly_peak_current_a": peak_a,
            "ambient_temperature_c": ambient_c,
        }
    return result, errors


def suggested_bay_label(sheet_name: str, selected_rows: list[dict[str, Any]]) -> str | None:
    if len(selected_rows) == 1:
        return bay_label(selected_rows[0])
    sheet_key = normalise_key(sheet_name)
    for row in selected_rows:
        candidates = [row["bay_flc"], row.get("bay_short_name") or "", row.get("bay_name") or ""]
        for candidate in candidates:
            candidate_key = normalise_key(candidate)
            if candidate_key and (candidate_key in sheet_key or sheet_key in candidate_key):
                return bay_label(row)
    return None


for key, value in {
    "auth": None,
    "supabase_client": None,
    "reference_cache": {"gi": {}, "bays": {}, "template_items": {}},
    "parsed": None,
    "parse_warnings": [],
    "parse_signature": None,
}.items():
    st.session_state.setdefault(key, value)

if not secret("SUPABASE_URL") or not secret("SUPABASE_KEY"):
    st.error("SUPABASE_URL dan SUPABASE_KEY belum dikonfigurasi.")
    st.stop()

with st.sidebar:
    st.markdown("### PLN UPT Pematang Siantar")
    st.caption("Modul inspeksi Thermovisi")
    st.divider()
    if st.session_state.auth:
        st.caption("Pengguna aktif")
        st.write(st.session_state.auth["email"])
        if st.button("Keluar", use_container_width=True):
            st.session_state.supabase_client = None
            st.session_state.reference_cache = {"gi": {}, "bays": {}, "template_items": {}}
            st.session_state.auth = None
            st.session_state.parsed = None
            st.rerun()
    else:
        st.markdown("#### Masuk")
        with st.form("login"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Masuk", use_container_width=True, type="primary")
        if submitted:
            try:
                login_client = make_client(secret("SUPABASE_URL"), secret("SUPABASE_KEY"))
                st.session_state.auth = sign_in(login_client, email, password)
                st.session_state.supabase_client = login_client
                st.session_state.reference_cache = {"gi": {}, "bays": {}, "template_items": {}}
                st.rerun()
            except Exception:
                st.error("Login gagal. Periksa email dan password.")

if not st.session_state.auth:
    st.info("Silakan masuk menggunakan akun Supabase untuk memulai inspeksi.")
    st.stop()

try:
    client = authenticated_client()
except Exception as exc:
    st.error(f"Sesi Supabase tidak dapat dipulihkan: {exc}")
    if st.button("Masuk ulang", type="primary"):
        st.session_state.auth = None
        st.session_state.supabase_client = None
        st.session_state.reference_cache = {"gi": {}, "bays": {}, "template_items": {}}
        st.rerun()
    st.stop()
reference_cache = st.session_state.reference_cache
reference_cache.setdefault("gi", {})
reference_cache.setdefault("bays", {})
reference_cache.setdefault("template_items", {})
try:
    if "ultg" not in reference_cache:
        reference_cache["ultg"] = fetch_ultg(client)
    if "templates" not in reference_cache:
        reference_cache["templates"] = fetch_templates(client)
    ultg_rows = reference_cache["ultg"]
    templates = reference_cache["templates"]
except Exception as exc:
    stop_for_reference_error(exc)

with st.container(border=True):
    st.markdown("### 1 · Pilih lokasi dan Bay")
    st.caption("Pilih satu GI, kemudian tentukan satu atau beberapa Bay yang terdapat dalam file Excel.")
    location_1, location_2, location_3 = st.columns([2, 2, 1])

    ultg_options = {f"{row['ultg_name']} — {row['ultg_flc']}": row["ultg_flc"] for row in ultg_rows}
    with location_1:
        ultg_choice = st.selectbox(
            "ULTG", list(ultg_options), index=None, placeholder="Pilih wilayah kerja ULTG", key="ultg_choice"
        )
    ultg_flc = ultg_options.get(ultg_choice)

    gi_rows = []
    if ultg_flc:
        try:
            if ultg_flc not in reference_cache["gi"]:
                reference_cache["gi"][ultg_flc] = fetch_gi(client, ultg_flc)
            gi_rows = reference_cache["gi"][ultg_flc]
        except Exception as exc:
            stop_for_reference_error(exc)
    gi_options = {f"{row['gi_name']} — {row['gi_flc']}": row["gi_flc"] for row in gi_rows}
    with location_2:
        gi_choice = st.selectbox(
            "Gardu Induk",
            list(gi_options),
            index=None,
            placeholder="Pilih Gardu Induk",
            disabled=not ultg_flc,
            key="gi_choice",
        )
    gi_flc = gi_options.get(gi_choice)

    bay_rows = []
    if ultg_flc and gi_flc:
        bay_cache_key = f"{ultg_flc}|{gi_flc}"
        try:
            if bay_cache_key not in reference_cache["bays"]:
                reference_cache["bays"][bay_cache_key] = fetch_bays(client, ultg_flc, gi_flc)
            bay_rows = reference_cache["bays"][bay_cache_key]
        except Exception as exc:
            stop_for_reference_error(exc)
    with location_3:
        st.metric("Bay tersedia", len(bay_rows))

    all_bay_labels = [bay_label(row) for row in bay_rows]
    selected_labels = st.multiselect(
        "Bay yang akan diimpor",
        all_bay_labels,
        placeholder="Pilih satu atau beberapa Bay",
        disabled=not bay_rows,
        help="Daftar ini membatasi Bay tujuan pada tahap pemetaan sheet.",
        key=f"selected_bays_{gi_flc}",
    )

selected_label_set = set(selected_labels)
selected_bay_rows = [row for row in bay_rows if bay_label(row) in selected_label_set]
selected_bay_ids = [row["bay_flc"] for row in selected_bay_rows]

if not selected_bay_rows:
    st.info("Pilih ULTG, Gardu Induk, dan minimal satu Bay untuk melanjutkan.")
    st.stop()

with st.container(border=True):
    st.markdown("### 2 · Lengkapi metadata setiap Bay")
    st.caption(
        "Setiap baris mewakili satu Bay. Nilai dapat diketik, ditempel, atau disalin ke beberapa baris seperti spreadsheet."
    )
    now = datetime.now().replace(second=0, microsecond=0)
    metadata_seed = pd.DataFrame(
        [
            {
                "bay_flc": row["bay_flc"],
                "Bay": bay_label(row),
                "Tanggal pelaksanaan": date.today(),
                "Pukul pelaksanaan": now.time(),
                "Beban pengukuran (A)": 1.0,
                "Beban tertinggi bulan (A)": 1.0,
                "Suhu lingkungan (°C)": 30.0,
            }
            for row in selected_bay_rows
        ]
    )
    metadata_editor = st.data_editor(
        metadata_seed,
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        disabled=["bay_flc", "Bay"],
        column_config={
            "bay_flc": None,
            "Bay": st.column_config.TextColumn("Bay", width="large"),
            "Tanggal pelaksanaan": st.column_config.DateColumn("Tanggal pelaksanaan", format="DD/MM/YYYY"),
            "Pukul pelaksanaan": st.column_config.TimeColumn("Pukul", format="HH:mm"),
            "Beban pengukuran (A)": st.column_config.NumberColumn(
                "Beban ukur (A)", min_value=0.01, step=1.0, format="%.2f"
            ),
            "Beban tertinggi bulan (A)": st.column_config.NumberColumn(
                "Beban tertinggi (A)", min_value=0.01, step=1.0, format="%.2f"
            ),
            "Suhu lingkungan (°C)": st.column_config.NumberColumn(
                "Suhu lingkungan (°C)", min_value=-50.0, max_value=100.0, step=0.1, format="%.1f"
            ),
        },
        key=f"metadata_editor_{gi_flc}_{'_'.join(selected_bay_ids)}",
    )
    metadata_by_bay, metadata_errors = metadata_from_editor(metadata_editor)
    for message in metadata_errors:
        st.error(message)

selected_pairs = {(row.get("bay_function_code"), row.get("voltage_code")) for row in selected_bay_rows}
pair_compatible_templates = [
    template
    for template in templates
    if all(
        (template.get("function_code"), template.get("voltage_code")) == pair
        for pair in selected_pairs
    )
]

with st.container(border=True):
    st.markdown("### 3 · Pilih template dan unggah Excel")
    show_custom = st.toggle(
        "Tampilkan template custom",
        value=False,
        help="Aktifkan hanya untuk GI/peralatan yang memiliki format khusus.",
    )
    compatible_templates = [
        template for template in pair_compatible_templates if template["is_default"] or show_custom
    ]
    template_col, upload_col = st.columns([2, 3])
    template_options = {
        f"{'Standar' if row['is_default'] else 'Custom'} · {row['template_name']}": row["template_code"]
        for row in compatible_templates
    }
    with template_col:
        template_choice = st.selectbox(
            "Template pengukuran",
            list(template_options),
            index=None,
            placeholder="Pilih template yang sesuai",
            disabled=not compatible_templates,
        )
        template_code = template_options.get(template_choice)
        template_meta = next((row for row in templates if row["template_code"] == template_code), None)
    with upload_col:
        uploaded = st.file_uploader(
            "File hasil pengukuran",
            type=["xlsx", "xlsm"],
            accept_multiple_files=False,
            help="Satu file boleh berisi beberapa sheet dan beberapa Bay yang telah dipilih.",
        )

    if len(selected_pairs) > 1:
        st.error("Bay yang dipilih memiliki fungsi/tegangan berbeda. Pilih Bay dengan jenis template yang sama.")
    elif not pair_compatible_templates:
        st.error("Belum ada template aktif untuk fungsi dan tegangan Bay yang dipilih.")

    digest = file_sha256(uploaded.getvalue()) if uploaded else None
    parse_signature = (digest, template_code)
    if parse_signature != st.session_state.parse_signature:
        st.session_state.parsed = None
        st.session_state.parse_signature = parse_signature

    parse_disabled = not (uploaded and template_code and not metadata_errors)
    if st.button("Baca dan validasi Excel", type="primary", disabled=parse_disabled):
        try:
            if template_code not in reference_cache["template_items"]:
                reference_cache["template_items"][template_code] = fetch_template_items(client, template_code)
            items = reference_cache["template_items"][template_code]
            parsed, warnings = parse_workbook(uploaded.getvalue(), items)
            st.session_state.parsed = parsed
            st.session_state.parse_warnings = warnings
        except Exception as exc:
            st.session_state.parsed = None
            st.error(f"Excel tidak dapat diproses: {exc}")

parsed = st.session_state.parsed
if parsed is None:
    st.stop()

for warning in st.session_state.parse_warnings:
    st.warning(warning)
if not parsed:
    st.error("Tidak ada sheet berisi hasil pengukuran yang dapat diproses.")
    st.stop()

with st.container(border=True):
    st.markdown("### 4 · Petakan sheet ke Bay")
    st.caption("Setiap sheet hanya dapat diarahkan ke Bay yang telah dipilih pada langkah pertama.")
    mapping_seed = pd.DataFrame(
        [
            {
                "Sheet Excel": parsed_sheet.sheet_name,
                "Jumlah nilai": parsed_sheet.numeric_count,
                "Bay tujuan": suggested_bay_label(parsed_sheet.sheet_name, selected_bay_rows),
            }
            for parsed_sheet in parsed
        ]
    )
    mapping_editor = st.data_editor(
        mapping_seed,
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        disabled=["Sheet Excel", "Jumlah nilai"],
        column_config={
            "Sheet Excel": st.column_config.TextColumn("Sheet Excel", width="large"),
            "Jumlah nilai": st.column_config.NumberColumn("Jumlah nilai", width="small"),
            "Bay tujuan": st.column_config.SelectboxColumn(
                "Bay tujuan", options=selected_labels, width="large"
            ),
        },
        key=f"mapping_editor_{digest}_{'_'.join(selected_bay_ids)}",
    )
    label_to_bay = {bay_label(row): row["bay_flc"] for row in selected_bay_rows}
    sheet_to_bay: dict[str, str] = {}
    for _, row in mapping_editor.iterrows():
        destination = row["Bay tujuan"]
        if isinstance(destination, str) and destination in label_to_bay:
            sheet_to_bay[str(row["Sheet Excel"])] = label_to_bay[destination]
    mapping_complete = len(sheet_to_bay) == len(parsed)
    if not mapping_complete:
        st.warning("Pilih Bay tujuan untuk seluruh sheet sebelum menyimpan.")

ambient_by_sheet = {
    sheet_name: float(metadata_by_bay[bay_id]["ambient_temperature_c"])
    for sheet_name, bay_id in sheet_to_bay.items()
    if bay_id in metadata_by_bay
}
rows = preview_rows(parsed, ambient_by_sheet)
total_invalid = sum(row["data_quality_status"] == "INVALID" for row in rows)
total_warning = sum(row["data_quality_status"] == "WARNING" for row in rows)
numeric_count = sum(row["temperature_c"] is not None for row in rows)

with st.container(border=True):
    st.markdown("### 5 · Review dan simpan")
    metric_1, metric_2, metric_3, metric_4 = st.columns(4)
    metric_1.metric("Bay dipilih", len(selected_bay_rows))
    metric_2.metric("Nilai suhu", numeric_count)
    metric_3.metric("Warning", total_warning)
    metric_4.metric("Invalid", total_invalid)

    preview_df = pd.DataFrame(rows).rename(
        columns={
            "sheet_name": "Sheet",
            "equipment_group_code": "Peralatan",
            "point_label": "Titik ukur",
            "phase_code": "Fasa",
            "temperature_c": "Suhu °C",
            "delta_ambient_c": "ΔT ambient °C",
            "source_cell_address": "Sel",
            "data_quality_status": "Status",
            "validation_message": "Pesan",
        }
    )
    st.dataframe(
        preview_df[
            ["Sheet", "Peralatan", "Titik ukur", "Fasa", "Suhu °C", "ΔT ambient °C", "Sel", "Status", "Pesan"]
        ],
        use_container_width=True,
        height=420,
        hide_index=True,
    )

    detail_1, detail_2 = st.columns(2)
    with detail_1:
        executor = st.text_input("Pelaksana", placeholder="Nama petugas/pelaksana")
    with detail_2:
        notes = st.text_input("Catatan (opsional)", placeholder="Catatan umum untuk file ini")

    drive_info = st.secrets.get("google_drive", {})
    drive_folder_id = str(drive_info.get("folder_id", "")) if drive_info else ""
    service_account = dict(st.secrets.get("google_service_account", {}))
    if total_invalid:
        st.error("Penyimpanan diblokir karena masih ada data INVALID. Perbaiki Excel atau template lalu validasi ulang.")
    if not service_account or not drive_folder_id:
        st.warning("Konfigurasi Google Drive belum lengkap pada secrets.toml.")

    ready = (
        mapping_complete
        and not metadata_errors
        and total_invalid == 0
        and bool(service_account)
        and bool(drive_folder_id)
        and bool(template_meta)
    )
    if st.button("Simpan inspeksi Thermovisi", type="primary", disabled=not ready, use_container_width=True):
        with st.spinner("Mengunggah file dan menyimpan hasil inspeksi..."):
            try:
                upload_id = save_import(
                    client,
                    file_bytes=uploaded.getvalue(),
                    filename=uploaded.name,
                    mime_type=uploaded.type
                    or "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    folder_id=drive_folder_id,
                    service_account_info=service_account,
                    template_code=template_code,
                    parsed_sheets=parsed,
                    sheet_to_bay=sheet_to_bay,
                    metadata_by_bay=metadata_by_bay,
                    executor=executor,
                    notes=notes,
                    user_id=st.session_state.auth["user_id"],
                )
                st.success(f"Import selesai. Upload ID: {upload_id}")
                st.session_state.parsed = None
            except Exception as exc:
                st.error(f"Import dihentikan karena terjadi kesalahan: {exc}")
