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
        c1, c2, c3, c4, c5 = st.columns([1, 1.3, 2, 1.4, 1.3])
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
        with c4:
            work_type = st.selectbox(
                "Jenis pekerjaan", ["ROUTINE", "FOLLOW_UP", "URGENT"],
                key="monitor_work_type",
            )
        with c5:
            stage_code = st.selectbox(
                "Tahap",
                ["TAHAP_1", "TAHAP_2"] if work_type == "ROUTINE" else ["ADHOC"],
                key=f"monitor_stage_{work_type}",
            )

    period_start = date(year, month, 1)
    period_end = _next_month(period_start)
    try:
        eligible = fetch_eligible_bays(client, ultg_flc=ultg_flc)
        inspections = fetch_inspection_completions(
            client,
            period_start=period_start,
            period_end=period_end,
            work_type=work_type,
            stage_code=stage_code,
        )
    except Exception as exc:
        st.error(f"Data monitoring tidak dapat dibaca: {exc}")
        return

    rows = build_upload_monitoring_rows(eligible, inspections)
    completed = sum(row["Status upload"] == "SUDAH UPLOAD" for row in rows)
    outstanding = len(rows) - completed
    percent = 100.0 * completed / len(rows) if rows else 0.0
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Bay wajib rutin", len(rows))
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
        .groupby(["ULTG", "Gardu Induk"], as_index=False)
        .agg(**{"Total Bay": ("Bay", "count"), "Sudah upload": ("Selesai", "sum"), "Belum upload": ("Belum", "sum")})
    )
    summary["Realisasi (%)"] = (
        100.0 * summary["Sudah upload"] / summary["Total Bay"]
    ).round(2)

    tab_missing, tab_gi, tab_all = st.tabs(
        ["Bay belum upload", "Ringkasan per GI", "Seluruh Bay"]
    )
    visible = [
        "ULTG", "Gardu Induk", "Bay", "Fungsi", "Tegangan",
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
        f"Periode {MONTH_NAMES[month]} {year} · {work_type} · {stage_code} · "
        f"{calendar.monthrange(year, month)[1]} hari kalender"
    )
