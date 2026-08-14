from __future__ import annotations

import os
from datetime import datetime

import pandas as pd
import streamlit as st

from thermovisi.excel_parser import parse_workbook, preview_rows
from thermovisi.supabase_service import (
    fetch_bays, fetch_gi, fetch_template_items, fetch_templates, fetch_ultg,
    file_sha256, make_client, save_import, sign_in,
)


st.set_page_config(page_title="PLN Thermovisi Importer", page_icon="🌡️", layout="wide")
st.title("🌡️ PLN Thermovisi Importer")
st.caption("Excel → validasi Python → Google Drive + Supabase")


def secret(name: str, default=""):
    return os.getenv(name) or st.secrets.get(name, default)


def authenticated_client():
    auth = st.session_state.get("auth") or {}
    client = make_client(secret("SUPABASE_URL"), secret("SUPABASE_KEY"), auth.get("access_token"), auth.get("refresh_token"))
    session = client.auth.get_session()
    if session:
        st.session_state.auth.update({
            "access_token": session.access_token,
            "refresh_token": session.refresh_token,
        })
    return client


for key, value in {"auth": None, "parsed": None, "parse_warnings": [], "parse_signature": None}.items():
    st.session_state.setdefault(key, value)

if not secret("SUPABASE_URL") or not secret("SUPABASE_KEY"):
    st.error("SUPABASE_URL dan SUPABASE_KEY belum dikonfigurasi.")
    st.stop()

with st.sidebar:
    st.header("Akses pengguna")
    if st.session_state.auth:
        st.success(st.session_state.auth["email"])
        if st.button("Keluar", use_container_width=True):
            st.session_state.auth = None
            st.session_state.parsed = None
            st.rerun()
    else:
        with st.form("login"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Masuk", use_container_width=True)
        if submitted:
            try:
                st.session_state.auth = sign_in(make_client(secret("SUPABASE_URL"), secret("SUPABASE_KEY")), email, password)
                st.rerun()
            except Exception:
                st.error("Login gagal. Periksa email dan password.")

if not st.session_state.auth:
    st.info("Silakan login untuk memulai impor Thermovisi.")
    st.stop()

client = authenticated_client()

try:
    ultg_rows = fetch_ultg(client)
    templates = fetch_templates(client)
except Exception as exc:
    st.error(f"Tidak dapat membaca referensi Supabase: {exc}")
    st.stop()

st.subheader("1. Lokasi dan metadata inspeksi")
c1, c2, c3 = st.columns(3)
ultg_options = {f"{x['ultg_name']} — {x['ultg_flc']}": x["ultg_flc"] for x in ultg_rows}
with c1:
    ultg_label = st.selectbox("ULTG", list(ultg_options), index=None, placeholder="Pilih ULTG")
ultg_flc = ultg_options.get(ultg_label)

gi_rows = fetch_gi(client, ultg_flc) if ultg_flc else []
gi_options = {f"{x['gi_name']} — {x['gi_flc']}": x["gi_flc"] for x in gi_rows}
with c2:
    gi_label = st.selectbox("GI", list(gi_options), index=None, placeholder="Pilih GI", disabled=not ultg_flc)
gi_flc = gi_options.get(gi_label)

bay_rows = fetch_bays(client, ultg_flc, gi_flc) if ultg_flc and gi_flc else []
with c3:
    st.metric("Bay tersedia", len(bay_rows))

m1, m2, m3, m4, m5 = st.columns(5)
with m1:
    measurement_date = st.date_input("Tanggal pelaksanaan")
with m2:
    measurement_time = st.time_input("Pukul pelaksanaan", value=datetime.now().time().replace(second=0, microsecond=0))
with m3:
    current_a = st.number_input("Beban pengukuran (A)", min_value=0.01, value=1.0, step=1.0)
with m4:
    peak_a = st.number_input("Beban tertinggi bulan (A)", min_value=0.01, value=1.0, step=1.0)
with m5:
    ambient_c = st.number_input("Suhu lingkungan (°C)", min_value=-50.0, max_value=100.0, value=30.0, step=0.1)

if peak_a < current_a:
    st.error("Beban tertinggi bulan berjalan tidak boleh lebih kecil dari beban pengukuran.")

st.subheader("2. Template dan file Excel")
template_options = {
    f"{'Standar' if x['is_default'] else 'Custom'} · {x['template_name']}": x["template_code"] for x in templates
}
t1, t2 = st.columns([2, 3])
with t1:
    template_label = st.selectbox("Template", list(template_options), index=None, placeholder="Pilih template")
    template_code = template_options.get(template_label)
    template_meta = next((x for x in templates if x["template_code"] == template_code), None)
with t2:
    uploaded = st.file_uploader("File hasil pengukuran", type=["xlsx", "xlsm"])

digest = file_sha256(uploaded.getvalue()) if uploaded else None
parse_signature = (digest, template_code, float(ambient_c), gi_flc)
if parse_signature != st.session_state.parse_signature:
    st.session_state.parsed = None
    st.session_state.parse_signature = parse_signature

if st.button("Baca dan validasi Excel", type="primary", disabled=not (uploaded and template_code and gi_flc)):
    try:
        items = fetch_template_items(client, template_code)
        parsed, warnings = parse_workbook(uploaded.getvalue(), items, float(ambient_c))
        st.session_state.parsed = parsed
        st.session_state.parse_warnings = warnings
    except Exception as exc:
        st.session_state.parsed = None
        st.error(f"Excel tidak dapat diproses: {exc}")

parsed = st.session_state.parsed
if parsed is not None:
    for warning in st.session_state.parse_warnings:
        st.warning(warning)
    if not parsed:
        st.error("Tidak ada sheet berisi hasil pengukuran yang dapat diproses.")
        st.stop()

    rows = preview_rows(parsed)
    total_invalid = sum(r["data_quality_status"] == "INVALID" for r in rows)
    total_warning = sum(r["data_quality_status"] == "WARNING" for r in rows)
    a, b, c, d = st.columns(4)
    a.metric("Sheet terisi", len(parsed))
    b.metric("Nilai suhu", sum(r["temperature_c"] is not None for r in rows))
    c.metric("Invalid", total_invalid)
    d.metric("Warning", total_warning)

    st.subheader("3. Pemetaan sheet ke Bay")
    bay_options = {f"{x['bay_name']} — {x['bay_flc']}": x["bay_flc"] for x in bay_rows}
    sheet_to_bay = {}
    for parsed_sheet in parsed:
        labels = list(bay_options)
        source_key = parsed_sheet.sheet_name.casefold().replace(" ", "")
        default_index = None
        for idx, label in enumerate(labels):
            bay = bay_options[label].casefold().replace(" ", "")
            short = next((x.get("bay_short_name") or "" for x in bay_rows if x["bay_flc"] == bay_options[label]), "").casefold().replace(" ", "")
            if source_key in bay or bay in source_key or (short and short in source_key):
                default_index = idx
                break
        selected = st.selectbox(
            f"{parsed_sheet.sheet_name} · {parsed_sheet.numeric_count} nilai",
            labels,
            index=default_index,
            placeholder="Pilih Bay tujuan",
            key=f"bay_{digest}_{parsed_sheet.sheet_name}",
        )
        if selected:
            sheet_to_bay[parsed_sheet.sheet_name] = bay_options[selected]

    bay_by_id = {x["bay_flc"]: x for x in bay_rows}
    incompatible = []
    if template_meta:
        for sheet_name, bay_id in sheet_to_bay.items():
            bay = bay_by_id[bay_id]
            if (
                bay.get("bay_function_code") != template_meta.get("function_code")
                or bay.get("voltage_code") != template_meta.get("voltage_code")
            ):
                incompatible.append(sheet_name)
    if incompatible:
        st.error(
            "Template tidak sesuai dengan function_code/voltage_code Bay pada sheet: "
            + ", ".join(incompatible)
        )

    st.subheader("4. Preview hasil olah Python")
    preview_df = pd.DataFrame(rows).rename(columns={
        "sheet_name": "Sheet", "equipment_group_code": "Peralatan", "point_label": "Titik ukur",
        "phase_code": "Fasa", "temperature_c": "Suhu °C", "delta_ambient_c": "ΔT ambient °C",
        "source_cell_address": "Sel", "data_quality_status": "Status", "validation_message": "Pesan",
    })
    st.dataframe(preview_df[["Sheet", "Peralatan", "Titik ukur", "Fasa", "Suhu °C", "ΔT ambient °C", "Sel", "Status", "Pesan"]], use_container_width=True, height=420)

    executor = st.text_input("Pelaksana")
    notes = st.text_area("Catatan (opsional)")
    drive_info = st.secrets.get("google_drive", {})
    drive_folder_id = str(drive_info.get("folder_id", "")) if drive_info else ""
    service_account = dict(st.secrets.get("google_service_account", {}))
    ready = (
        len(sheet_to_bay) == len(parsed)
        and total_invalid == 0
        and not incompatible
        and peak_a >= current_a
        and bool(service_account)
        and bool(drive_folder_id)
    )
    if total_invalid:
        st.error("Simpan diblokir karena masih ada data INVALID. Perbaiki Excel atau template lalu validasi ulang.")
    if not service_account or not drive_folder_id:
        st.warning("Konfigurasi Google Drive belum lengkap pada secrets.toml.")

    if st.button("Simpan ke Google Drive dan Supabase", type="primary", disabled=not ready):
        with st.spinner("Mengunggah file dan menyimpan hasil pengukuran..."):
            try:
                upload_id = save_import(
                    client,
                    file_bytes=uploaded.getvalue(), filename=uploaded.name,
                    mime_type=uploaded.type or "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    folder_id=drive_folder_id, service_account_info=service_account,
                    template_code=template_code, parsed_sheets=parsed, sheet_to_bay=sheet_to_bay,
                    measurement_date=measurement_date, measurement_time=measurement_time,
                    measurement_current_a=float(current_a), monthly_peak_current_a=float(peak_a),
                    ambient_temperature_c=float(ambient_c), executor=executor, notes=notes,
                    user_id=st.session_state.auth["user_id"],
                )
                st.success(f"Import selesai. upload_id: {upload_id}")
                st.session_state.parsed = None
            except Exception as exc:
                st.error(f"Import dihentikan karena terjadi kesalahan: {exc}")
