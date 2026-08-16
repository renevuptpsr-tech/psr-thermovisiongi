from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd
import streamlit as st

from .supabase_service import (
    add_plan_items,
    fetch_bays,
    fetch_gi,
    fetch_or_create_plan,
    fetch_plan_gi_summary,
    fetch_plan_monitoring,
)


MONTH_NAMES = {
    1: "Januari", 2: "Februari", 3: "Maret", 4: "April",
    5: "Mei", 6: "Juni", 7: "Juli", 8: "Agustus",
    9: "September", 10: "Oktober", 11: "November", 12: "Desember",
}


def _bay_label(row: dict[str, Any]) -> str:
    name = row.get("bay_short_name") or row.get("bay_name") or "Bay"
    function_name = row.get("bay_function_name") or row.get("bay_function_code") or "-"
    return f"{name} · {function_name} — {row['bay_flc']}"


def _stage_for(work_type: str, selected: str | None = None) -> str:
    if work_type != "ROUTINE":
        return "ADHOC"
    return selected if selected in {"TAHAP_1", "TAHAP_2"} else "TAHAP_1"


def render_planning_page(
    client,
    *,
    ultg_rows: list[dict[str, Any]],
    user_id: str,
) -> None:
    st.markdown("## Rencana dan Monitoring Inspeksi")
    st.caption(
        "Susun daftar Bay wajib Thermovisi dan pantau realisasi rutin Tahap 1/Tahap 2, "
        "follow-up, maupun pekerjaan urgent."
    )

    today = date.today()
    with st.container(border=True):
        st.markdown("### 1 · Tentukan periode pekerjaan")
        c1, c2, c3, c4, c5 = st.columns([1, 1.3, 2, 1.4, 1.4])
        with c1:
            year = st.number_input("Tahun", min_value=2020, max_value=2100, value=today.year, step=1)
        with c2:
            month_name = st.selectbox(
                "Bulan", list(MONTH_NAMES.values()), index=today.month - 1
            )
        month = next(number for number, name in MONTH_NAMES.items() if name == month_name)
        period_month = date(int(year), month, 1)

        ultg_options = {
            f"{row['ultg_name']} — {row['ultg_flc']}": row["ultg_flc"]
            for row in ultg_rows
        }
        with c3:
            ultg_label = st.selectbox(
                "ULTG", list(ultg_options), index=None, placeholder="Pilih ULTG",
                key="plan_ultg",
            )
        ultg_flc = ultg_options.get(ultg_label)
        with c4:
            work_type = st.selectbox(
                "Jenis pekerjaan", ["ROUTINE", "FOLLOW_UP", "URGENT"], key="plan_work_type"
            )
        with c5:
            stage_choice = st.selectbox(
                "Tahap",
                ["TAHAP_1", "TAHAP_2"] if work_type == "ROUTINE" else ["ADHOC"],
                key=f"plan_stage_{work_type}",
            )
        stage_code = _stage_for(work_type, stage_choice)

    gi_rows: list[dict[str, Any]] = []
    if ultg_flc:
        gi_rows = fetch_gi(client, ultg_flc)

    with st.container(border=True):
        st.markdown("### 2 · Tambahkan Bay ke daftar inspeksi")
        gi_options = {
            f"{row['gi_name']} — {row['gi_flc']}": row["gi_flc"] for row in gi_rows
        }
        gi_label = st.selectbox(
            "Gardu Induk",
            list(gi_options),
            index=None,
            placeholder="Pilih Gardu Induk",
            disabled=not gi_rows,
            key=f"plan_gi_{ultg_flc}",
        )
        gi_flc = gi_options.get(gi_label)
        bay_rows = fetch_bays(client, ultg_flc, gi_flc) if ultg_flc and gi_flc else []
        bay_options = {_bay_label(row): row["bay_flc"] for row in bay_rows}
        select_all = st.checkbox(
            "Pilih seluruh Bay eligible pada GI ini",
            value=False,
            disabled=not bay_rows,
            key=f"plan_all_{period_month}_{stage_code}_{gi_flc}",
        )
        selected_labels = st.multiselect(
            "Bay yang wajib diinspeksi",
            list(bay_options),
            default=list(bay_options) if select_all else [],
            placeholder="Pilih satu atau beberapa Bay",
            disabled=not bay_rows,
            key=f"plan_bays_{period_month}_{stage_code}_{gi_flc}_{select_all}",
        )
        selected_bays = [bay_options[label] for label in selected_labels]
        notes = st.text_input(
            "Catatan rencana (opsional)",
            placeholder="Contoh: prioritas penyelesaian minggu pertama",
        )
        save_disabled = not (ultg_flc and gi_flc and selected_bays)
        if st.button(
            "Tambahkan ke rencana inspeksi",
            type="primary",
            disabled=save_disabled,
            width="stretch",
        ):
            try:
                plan = fetch_or_create_plan(
                    client,
                    period_month=period_month,
                    ultg_functloc_id=ultg_flc,
                    work_type=work_type,
                    stage_code=stage_code,
                    user_id=user_id,
                    notes=notes,
                )
                added = add_plan_items(
                    client, plan_id=plan["plan_id"], bay_ids=selected_bays
                )
                if added:
                    st.success(f"{added} Bay berhasil ditambahkan ke rencana.")
                else:
                    st.info("Seluruh Bay yang dipilih sudah berada dalam rencana ini.")
                st.rerun()
            except Exception as exc:
                st.error(f"Rencana tidak dapat disimpan: {exc}")

    with st.container(border=True):
        st.markdown("### 3 · Monitoring pelaksanaan")
        if not ultg_flc:
            st.info("Pilih ULTG untuk menampilkan progres pelaksanaan.")
            return
        try:
            rows = fetch_plan_monitoring(
                client,
                period_month=period_month,
                ultg_flc=ultg_flc,
                work_type=work_type,
                stage_code=stage_code,
            )
            summaries = fetch_plan_gi_summary(
                client,
                period_month=period_month,
                ultg_flc=ultg_flc,
                work_type=work_type,
                stage_code=stage_code,
            )
        except Exception as exc:
            st.error(f"Monitoring tidak dapat dibaca: {exc}")
            return
        if not rows:
            st.info("Belum ada Bay dalam rencana pada periode dan tahap ini.")
            return

        active = [row for row in rows if row["execution_status"] != "CANCELLED"]
        completed = sum(row["execution_status"] == "COMPLETED" for row in active)
        outstanding = sum(row["execution_status"] in {"PLANNED", "IN_PROGRESS"} for row in active)
        percent = (100.0 * completed / len(active)) if active else 0.0
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Bay direncanakan", len(active))
        m2.metric("Selesai", completed)
        m3.metric("Belum selesai", outstanding)
        m4.metric("Realisasi", f"{percent:.1f}%")

        tab_outstanding, tab_gi, tab_all = st.tabs(
            ["Belum selesai", "Ringkasan GI", "Seluruh Bay"]
        )
        display_columns = {
            "gi_name": "Gardu Induk",
            "bay_name": "Bay",
            "bay_function_code": "Fungsi",
            "voltage_code": "Tegangan",
            "execution_status": "Status",
            "measurement_date": "Tanggal realisasi",
        }
        with tab_outstanding:
            outstanding_rows = [
                row for row in rows if row["execution_status"] in {"PLANNED", "IN_PROGRESS"}
            ]
            if outstanding_rows:
                st.dataframe(
                    pd.DataFrame(outstanding_rows).rename(columns=display_columns)[list(display_columns.values())],
                    hide_index=True,
                    width="stretch",
                )
            else:
                st.success("Seluruh Bay pada rencana ini sudah selesai.")
        with tab_gi:
            summary_df = pd.DataFrame(summaries).rename(
                columns={
                    "gi_name": "Gardu Induk",
                    "total_bay": "Total Bay",
                    "completed_bay": "Selesai",
                    "outstanding_bay": "Belum selesai",
                    "completion_percent": "Realisasi (%)",
                }
            )
            st.dataframe(
                summary_df[["Gardu Induk", "Total Bay", "Selesai", "Belum selesai", "Realisasi (%)"]],
                hide_index=True,
                width="stretch",
            )
        with tab_all:
            all_df = pd.DataFrame(rows).rename(columns=display_columns)
            st.dataframe(
                all_df[list(display_columns.values())], hide_index=True, width="stretch"
            )
