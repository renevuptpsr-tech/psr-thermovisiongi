from __future__ import annotations

import os
from datetime import date, datetime
from typing import Any

import pandas as pd
import streamlit as st

from thermovisi.ahi import aggregate_ahi
from thermovisi.excel_parser import parse_workbook
from thermovisi.mapping import (
    TRAFO_TWO_SHEET_MODE,
    mapping_mode_from_template,
    sheet_mapping_from_bays,
    trafo_sheet_mapping_from_bays,
)
from thermovisi.review import build_sheet_review, compact_review_rows, style_compact_review
from thermovisi.review_validator import validate_bay_review, validation_summary_row
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
            "Beban tertinggi pernah dicapai (A)",
            "Suhu lingkungan (°C)",
        ]
        if any(pd.isna(row[field]) for field in required):
            errors.append(f"Metadata {name} belum lengkap.")
            continue
        try:
            current_a = float(row["Beban pengukuran (A)"])
            peak_a = float(row["Beban tertinggi pernah dicapai (A)"])
            ambient_c = float(row["Suhu lingkungan (°C)"])
        except (TypeError, ValueError):
            errors.append(f"Beban atau suhu {name} bukan angka yang valid.")
            continue
        if current_a < 0 or peak_a < 0:
            errors.append(f"Beban {name} tidak boleh negatif.")
        if current_a > 0 and peak_a < current_a:
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


for key, value in {
    "auth": None,
    "supabase_client": None,
    "reference_cache": {"gi": {}, "bays": {}, "template_items": {}},
    "parsed": None,
    "parse_warnings": [],
    "parse_signature": None,
    "review_validation_signature": None,
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
        if st.button("Keluar", width="stretch"):
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
            submitted = st.form_submit_button("Masuk", width="stretch", type="primary")
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
                "Beban tertinggi pernah dicapai (A)": 1.0,
                "Suhu lingkungan (°C)": 30.0,
            }
            for row in selected_bay_rows
        ]
    )
    metadata_editor = st.data_editor(
        metadata_seed,
        hide_index=True,
        width="stretch",
        num_rows="fixed",
        disabled=["bay_flc", "Bay"],
        column_config={
            "bay_flc": None,
            "Bay": st.column_config.TextColumn("Bay", width="large"),
            "Tanggal pelaksanaan": st.column_config.DateColumn("Tanggal pelaksanaan", format="DD/MM/YYYY"),
            "Pukul pelaksanaan": st.column_config.TimeColumn("Pukul", format="HH:mm"),
            "Beban pengukuran (A)": st.column_config.NumberColumn(
                "Beban ukur (A)", min_value=0.0, step=1.0, format="%.2f"
            ),
            "Beban tertinggi pernah dicapai (A)": st.column_config.NumberColumn(
                "Beban tertinggi pernah dicapai (A)", min_value=0.0, step=1.0, format="%.2f"
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
    template_items = reference_cache["template_items"][template_code]
    mapping_mode = mapping_mode_from_template(template_meta, template_items)
    is_trafo_two_sheet = mapping_mode == TRAFO_TWO_SHEET_MODE
    st.markdown(
        "### 4 · Pasangkan dua sheet untuk setiap Bay Trafo"
        if is_trafo_two_sheet
        else "### 4 · Pasangkan sheet ke Bay"
    )
    st.caption(
        (
            "Template Trafo menggunakan Sheet Trafo dan Sheet Bay untuk setiap Bay. "
            "Nama sheet bebas; aplikasi memvalidasi bagian form dari isi titik ukurnya."
        )
        if is_trafo_two_sheet
        else (
            "Template non-Trafo menggunakan satu sheet untuk setiap Bay. "
            "Pilih sheet tujuan tanpa harus menyeragamkan nama sheet."
        )
    )
    sheet_names = [parsed_sheet.sheet_name for parsed_sheet in parsed]
    sheet_sections = {
        parsed_sheet.sheet_name: {
            measurement.form_section_code for measurement in parsed_sheet.measurements
        }
        for parsed_sheet in parsed
    }
    if is_trafo_two_sheet:
        mapping_seed = pd.DataFrame(
            [
                {
                    "bay_flc": row["bay_flc"],
                    "Bay": bay_label(row),
                    "Sheet Trafo": None,
                    "Sheet Bay": None,
                }
                for row in selected_bay_rows
            ]
        )
        mapping_editor = st.data_editor(
            mapping_seed,
            hide_index=True,
            width="stretch",
            num_rows="fixed",
            disabled=["bay_flc", "Bay"],
            column_config={
                "bay_flc": None,
                "Bay": st.column_config.TextColumn("Bay tujuan", width="large"),
                "Sheet Trafo": st.column_config.SelectboxColumn(
                    "Sheet Trafo", options=sheet_names, width="large", required=True
                ),
                "Sheet Bay": st.column_config.SelectboxColumn(
                    "Sheet Bay", options=sheet_names, width="large", required=True
                ),
            },
            key=f"bay_sheet_mapping_trafo_{digest}_{'_'.join(selected_bay_ids)}",
        )
        sheet_assignments, mapping_errors = trafo_sheet_mapping_from_bays(
            mapping_editor.to_dict("records"),
            expected_bay_ids=selected_bay_ids,
            valid_sheet_names=sheet_names,
            sheet_sections=sheet_sections,
        )
    else:
        mapping_seed = pd.DataFrame(
            [
                {"bay_flc": row["bay_flc"], "Bay": bay_label(row), "Sheet Excel": None}
                for row in selected_bay_rows
            ]
        )
        mapping_editor = st.data_editor(
            mapping_seed,
            hide_index=True,
            width="stretch",
            num_rows="fixed",
            disabled=["bay_flc", "Bay"],
            column_config={
                "bay_flc": None,
                "Bay": st.column_config.TextColumn("Bay tujuan", width="large"),
                "Sheet Excel": st.column_config.SelectboxColumn(
                    "Sheet hasil pengukuran", options=sheet_names, width="large", required=True
                ),
            },
            key=f"bay_sheet_mapping_single_{digest}_{'_'.join(selected_bay_ids)}",
        )
        single_mapping, mapping_errors = sheet_mapping_from_bays(
            mapping_editor.to_dict("records"),
            expected_bay_ids=selected_bay_ids,
            valid_sheet_names=sheet_names,
        )
        sheet_assignments = {
            sheet_name: {
                "bay_flc": bay_id,
                "sheet_role": "MAIN",
                "form_section_code": next(iter(sheet_sections.get(sheet_name, {"MAIN"}))),
            }
            for sheet_name, bay_id in single_mapping.items()
        }
    for message in mapping_errors:
        st.warning(message)
    mapping_complete = not mapping_errors

    parsed_by_name = {item.sheet_name: item for item in parsed}
    sheet_to_bay = {
        sheet_name: assignment["bay_flc"]
        for sheet_name, assignment in sheet_assignments.items()
    }
    assignments_by_bay: dict[str, dict[str, str]] = {}
    for sheet_name, assignment in sheet_assignments.items():
        assignments_by_bay.setdefault(assignment["bay_flc"], {})[
            assignment["sheet_role"]
        ] = sheet_name
    mapped_parsed = [parsed_by_name[name] for name in sheet_to_bay if name in parsed_by_name]
    if mapping_complete:
        if is_trafo_two_sheet:
            confirmation_rows = [
                {
                    "Bay": bay_label(row),
                    "Sheet Trafo": assignments_by_bay[row["bay_flc"]]["TRAFO"],
                    "Nilai Trafo": parsed_by_name[
                        assignments_by_bay[row["bay_flc"]]["TRAFO"]
                    ].numeric_count,
                    "Sheet Bay": assignments_by_bay[row["bay_flc"]]["BAY"],
                    "Nilai Bay": parsed_by_name[
                        assignments_by_bay[row["bay_flc"]]["BAY"]
                    ].numeric_count,
                }
                for row in selected_bay_rows
            ]
            st.success("Pemetaan dua sheet Trafo lengkap. Periksa kembali pasangan Bay.")
        else:
            confirmation_rows = [
                {
                    "Bay": bay_label(row),
                    "Sheet Excel": assignments_by_bay[row["bay_flc"]]["MAIN"],
                    "Nilai suhu": parsed_by_name[
                        assignments_by_bay[row["bay_flc"]]["MAIN"]
                    ].numeric_count,
                }
                for row in selected_bay_rows
            ]
            st.success("Pemetaan satu sheet per Bay lengkap. Periksa kembali sebelum review.")
        st.dataframe(pd.DataFrame(confirmation_rows), hide_index=True, width="stretch")

    ignored_sheets = [name for name in sheet_names if name not in sheet_to_bay]
    if ignored_sheets:
        st.info(f"Sheet yang tidak dipilih tidak akan diimpor: {', '.join(ignored_sheets)}")

total_invalid = sum(sheet.invalid_count for sheet in mapped_parsed)

with st.container(border=True):
    st.markdown("### 5 · Review hasil dan analisa")
    st.caption(
        (
            "Pilih satu Bay. Sheet Trafo dan Sheet Bay ditampilkan pada tab terpisah."
            if is_trafo_two_sheet
            else "Pilih satu Bay untuk menampilkan sheet hasil pengukurannya."
        )
    )

    selected_bay_by_id = {row["bay_flc"]: row for row in selected_bay_rows}
    review_options = {
        bay_label(selected_bay_by_id[bay_id]): bay_id
        for bay_id in assignments_by_bay
        if bay_id in selected_bay_by_id
        and (
            {"TRAFO", "BAY"}.issubset(assignments_by_bay[bay_id])
            if is_trafo_two_sheet
            else "MAIN" in assignments_by_bay[bay_id]
        )
    }
    review_choice = st.selectbox(
        "Bay yang direview",
        list(review_options),
        index=0 if review_options else None,
        placeholder="Pilih Bay",
        disabled=not review_options,
    )

    review_rows_by_bay: dict[str, list[dict[str, Any]]] = {}
    template_items = reference_cache["template_items"][template_code]
    for bay_id in review_options.values():
        bay_rows: list[dict[str, Any]] = []
        roles = ("TRAFO", "BAY") if is_trafo_two_sheet else ("MAIN",)
        for role in roles:
            review_sheet = parsed_by_name[assignments_by_bay[bay_id][role]]
            review_metadata = metadata_by_bay[bay_id]
            bay_rows.extend(
                build_sheet_review(
                    review_sheet,
                    template_items,
                    measurement_current_a=float(review_metadata["measurement_current_a"]),
                    monthly_peak_current_a=float(review_metadata["monthly_peak_current_a"]),
                    ambient_temperature_c=float(review_metadata["ambient_temperature_c"]),
                )
            )
        review_rows_by_bay[bay_id] = bay_rows

    all_review_rows: list[dict[str, Any]] = []
    if review_choice:
        review_bay_id = review_options[review_choice]
        review_metadata = metadata_by_bay[review_bay_id]

        info_1, info_2, info_3 = st.columns(3)
        info_1.metric("Beban ukur", f"{review_metadata['measurement_current_a']:.2f} A")
        info_2.metric("Beban tertinggi", f"{review_metadata['monthly_peak_current_a']:.2f} A")
        info_3.metric("Suhu lingkungan", f"{review_metadata['ambient_temperature_c']:.1f} °C")

        if is_trafo_two_sheet:
            tabs = st.tabs(["Trafo Utama", "Bay Trafo"])
            role_config = ((tabs[0], "TRAFO", "Sheet Trafo"), (tabs[1], "BAY", "Sheet Bay"))
        else:
            role_config = ((st.container(), "MAIN", "Sheet hasil pengukuran"),)
        for tab, role, role_label in role_config:
            with tab:
                review_sheet_name = assignments_by_bay[review_bay_id][role]
                review_sheet = parsed_by_name[review_sheet_name]
                sheet_item_ids = {
                    measurement.template_item_id for measurement in review_sheet.measurements
                }
                review_rows = [
                    row for row in review_rows_by_bay[review_bay_id]
                    if row.get("Template item ID") in sheet_item_ids
                ]
                all_review_rows.extend(review_rows)
                st.caption(
                    f"{role_label}: {review_sheet_name} · "
                    f"{review_sheet.numeric_count} nilai suhu terbaca"
                )
                review_df = pd.DataFrame(compact_review_rows(review_rows))
                st.dataframe(
                    style_compact_review(review_df),
                    width="stretch",
                    height=560,
                    hide_index=True,
                    column_config={
                        "No.": st.column_config.NumberColumn("No.", width="small", format="%d"),
                        "Peralatan": st.column_config.TextColumn("Peralatan", width="medium"),
                        "Titik yang diperiksa": st.column_config.TextColumn(
                            "Titik yang diperiksa", width="large"
                        ),
                        "Pengukuran": st.column_config.TextColumn(
                            "Pengukuran", width="medium"
                        ),
                        "Delta T": st.column_config.TextColumn(
                            "Delta T", width="large"
                        ),
                        "Kondisi": st.column_config.TextColumn("Kondisi", width="medium"),
                        "AHI Thermovisi": st.column_config.TextColumn(
                            "AHI Thermovisi", width="medium"
                        ),
                        "Kesimpulan / Rekomendasi": st.column_config.TextColumn(
                            "Kesimpulan / Rekomendasi", width="large"
                        ),
                        "Status Data": st.column_config.TextColumn(
                            "Status Data", width="small"
                        ),
                        "Status Analisa": st.column_config.TextColumn(
                            "Status Analisa", width="medium"
                        ),
                    },
                )
                with st.expander("Lihat detail teknis lengkap"):
                    st.dataframe(
                        pd.DataFrame(review_rows),
                        width="stretch",
                        height=420,
                        hide_index=True,
                    )

        abnormal_count = sum(
            int(row.get("Tingkat perhatian") or 0) > 0 for row in all_review_rows
        )
        invalid_review = sum(row["Status data"] == "INVALID" for row in all_review_rows)
        bay_ahi = aggregate_ahi(row.get("AHI Thermovisi") for row in all_review_rows)
        summary_1, summary_2, summary_3, summary_4 = st.columns(4)
        summary_1.metric("Total baris review", len(all_review_rows))
        summary_2.metric("Perlu perhatian", abnormal_count)
        summary_3.metric("Data invalid", invalid_review)
        summary_4.metric(
            "AHI Bay Thermovisi",
            bay_ahi.display if bay_ahi else "Tidak dapat dievaluasi",
        )

    st.divider()
    st.markdown("#### Validasi sebelum penyimpanan")
    initial_validations = {
        bay_id: validate_bay_review(rows)
        for bay_id, rows in review_rows_by_bay.items()
    }
    incomplete_total = sum(item.incomplete_rows for item in initial_validations.values())
    accept_incomplete = st.checkbox(
        "Saya memahami dan menyetujui penyimpanan titik dengan data tidak lengkap.",
        value=False,
        disabled=incomplete_total == 0,
        help="Tidak diperlukan untuk titik NOT_MEASURED atau NOT_APPLICABLE.",
    )
    validations = {
        bay_id: validate_bay_review(rows, accept_incomplete=accept_incomplete)
        for bay_id, rows in review_rows_by_bay.items()
    }
    summary_rows = [
        validation_summary_row(
            bay_label(selected_bay_by_id[bay_id]), validation
        )
        for bay_id, validation in validations.items()
    ]
    if summary_rows:
        st.dataframe(pd.DataFrame(summary_rows), hide_index=True, width="stretch")

    all_bays_ready = bool(validations) and all(item.ready for item in validations.values())
    validation_signature = repr(
        (
            parse_signature,
            template_code,
            assignments_by_bay,
            metadata_by_bay,
            accept_incomplete,
        )
    )
    if st.button(
        "Validasi seluruh Bay",
        type="secondary",
        disabled=not mapping_complete or not all_bays_ready,
        width="stretch",
    ):
        st.session_state.review_validation_signature = validation_signature
        st.success("Seluruh Bay lolos validasi dan siap untuk persetujuan akhir.")
    validation_approved = (
        st.session_state.review_validation_signature == validation_signature
    )
    if not all_bays_ready:
        st.error("Masih ada Bay yang diblokir atau memerlukan konfirmasi data tidak lengkap.")

    review_confirmed = st.checkbox(
        "Saya telah memeriksa seluruh pasangan Bay–Sheet, hasil pengukuran, dan analisa.",
        value=False,
        disabled=not validation_approved,
    )
    if not review_confirmed:
        st.info("Penyimpanan masih dikunci. Selesaikan review seluruh sheet terlebih dahulu.")

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

    storage_model_ready = not is_trafo_two_sheet
    if is_trafo_two_sheet:
        st.warning(
            "Penyimpanan Bay Trafo sementara dikunci karena satu inspeksi menggunakan dua sheet, "
            "sedangkan transaksi saat ini masih mempunyai satu source_sheet_name."
        )

    ready = (
        storage_model_ready
        and
        mapping_complete
        and validation_approved
        and review_confirmed
        and not metadata_errors
        and total_invalid == 0
        and bool(service_account)
        and bool(drive_folder_id)
        and bool(template_meta)
    )
    if st.button("Simpan inspeksi Thermovisi", type="primary", disabled=not ready, width="stretch"):
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
                    parsed_sheets=mapped_parsed,
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
