from __future__ import annotations

import calendar
from datetime import date
from typing import Any

import pandas as pd
import streamlit as st

from .supabase_service import fetch_eligible_bays, fetch_inspection_completions
from .monitoring import build_upload_monitoring_rows


MONTH_NAMES = {
    1: "Januari", 2: "Februari", 3: "Maret", 4: "April",
    5: "Mei", 6: "Juni", 7: "Juli", 8: "Agustus",
    9: "September", 10: "Oktober", 11: "November", 12: "Desember",
}


def _next_month(value: date) -> date:
    if value.month == 12:
        return date(value.year + 1, 1, 1)
    return date(value.year, value.month + 1, 1)


def render_upload_monitoring_page(
    client,
    *,
    ultg_rows: list[dict[str, Any]],
) -> None:
    st.markdown("## Monitoring Realisasi Upload")
    st.caption(
        "Monitoring dihitung otomatis dengan membandingkan seluruh Bay eligible pada master "
        "terhadap hasil inspeksi yang sudah diunggah. Tidak memerlukan pembuatan rencana."
    )
    today = date.today()
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns([1, 1.3, 2, 1.3])
        with c1:
            year = int(st.number_input("Tahun", 2020, 2100, today.year, 1))
        with c2:
            month_name = st.selectbox(
                "Bulan", list(MONTH_NAMES.values()), index=today.month - 1,
                key="monitor_month",
            )
        month = next(key for key, value in MONTH_NAMES.items() if value == month_name)
        ultg_options = {"Seluruh ULTG": None} | {
            f"{row['ultg_name']} — {row['ultg_flc']}": row["ultg_flc"]
            for row in ultg_rows
        }
        with c3:
            ultg_label = st.selectbox("ULTG", list(ultg_options), key="monitor_ultg")
        ultg_flc = ultg_options[ultg_label]
        work_type = "ROUTINE"
        with c4:
            stage_filter = st.selectbox(
                "Tahap",
                ["SEMUA_TAHAP", "TAHAP_1", "TAHAP_2"],
                format_func=lambda value: {
                    "SEMUA_TAHAP": "Semua Tahap",
                    "TAHAP_1": "Tahap 1",
                    "TAHAP_2": "Tahap 2",
                }[value],
                key="monitor_routine_stage",
            )

    period_start = date(year, month, 1)
    period_end = _next_month(period_start)
    try:
        eligible = fetch_eligible_bays(
            client, ultg_flc=ultg_flc, required_only=True
        )
        selected_stages = (
            ["TAHAP_1", "TAHAP_2"]
            if stage_filter == "SEMUA_TAHAP"
            else [stage_filter]
        )
        rows: list[dict[str, Any]] = []
        for stage_code in selected_stages:
            inspections = fetch_inspection_completions(
                client,
                period_start=period_start,
                period_end=period_end,
                work_type=work_type,
                stage_code=stage_code,
            )
            stage_rows = build_upload_monitoring_rows(eligible, inspections)
            for row in stage_rows:
                row["Tahap"] = "Tahap 1" if stage_code == "TAHAP_1" else "Tahap 2"
            rows.extend(stage_rows)
    except Exception as exc:
        st.error(f"Data monitoring tidak dapat dibaca: {exc}")
        return

    completed = sum(row["Status upload"] == "SUDAH UPLOAD" for row in rows)
    outstanding = len(rows) - completed
    percent = 100.0 * completed / len(rows) if rows else 0.0
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Kewajiban inspeksi", len(rows))
    m2.metric("Sudah upload", completed)
    m3.metric("Belum upload", outstanding)
    m4.metric("Realisasi", f"{percent:.1f}%")

    detail = pd.DataFrame(rows)
    if detail.empty:
        st.info("Tidak ada Bay eligible pada cakupan yang dipilih.")
        return
    summary = (
        detail.assign(
            Selesai=(detail["Status upload"] == "SUDAH UPLOAD").astype(int),
            Belum=(detail["Status upload"] == "BELUM UPLOAD").astype(int),
        )
        .groupby(["ULTG", "Gardu Induk", "Tahap"], as_index=False)
        .agg(**{"Total Bay": ("Bay", "count"), "Sudah upload": ("Selesai", "sum"), "Belum upload": ("Belum", "sum")})
    )
    summary["Realisasi (%)"] = (
        100.0 * summary["Sudah upload"] / summary["Total Bay"]
    ).round(2)

    tab_missing, tab_gi, tab_all = st.tabs(
        ["Bay belum upload", "Ringkasan per GI", "Seluruh Bay"]
    )
    visible = [
        "ULTG", "Gardu Induk", "Bay", "Tahap", "Fungsi", "Tegangan",
        "Status upload", "Tanggal pelaksanaan", "Pukul",
    ]
    with tab_missing:
        missing = detail[detail["Status upload"] == "BELUM UPLOAD"]
        if missing.empty:
            st.success("Seluruh Bay pada cakupan ini sudah mengunggah hasil inspeksi.")
        else:
            st.dataframe(missing[visible], hide_index=True, width="stretch")
    with tab_gi:
        st.dataframe(summary, hide_index=True, width="stretch")
    with tab_all:
        st.dataframe(detail[visible], hide_index=True, width="stretch")

    st.caption(
        f"Periode {MONTH_NAMES[month]} {year} · ROUTINE · "
        f"{'Semua Tahap' if stage_filter == 'SEMUA_TAHAP' else rows[0]['Tahap'] if rows else stage_filter} · "
        f"{calendar.monthrange(year, month)[1]} hari kalender"
    )
