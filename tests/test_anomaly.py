from thermovisi.anomaly import build_telegram_anomaly_message, prepare_anomaly_rows


def test_only_poor_and_critical_evaluations_become_anomalies():
    rows = prepare_anomaly_rows(
        inspection_id="inspection-1",
        evaluation_rows=[
            {
                "evaluation_id": "normal",
                "severity": 0,
                "condition_label": "Normal",
                "recommendation": "Rutin",
                "ahi_score": 1,
            },
            {
                "evaluation_id": "remeasure",
                "severity": 1,
                "condition_label": "Perlu pengukuran ulang",
                "recommendation": "Lakukan pengukuran ulang dua minggu lagi.",
                "ahi_score": 2,
            },
            {
                "evaluation_id": "fair",
                "severity": 2,
                "condition_label": "Kondisi II",
                "recommendation": "Jadwalkan perbaikan",
                "ahi_score": 3,
            },
            {
                "evaluation_id": "poor",
                "severity": 3,
                "condition_label": "Kondisi III",
                "recommendation": "Lakukan perbaikan segera",
                "ahi_score": 4,
            },
            {
                "evaluation_id": "critical",
                "severity": 4,
                "condition_label": "Kondisi IV",
                "recommendation": "Kondisi darurat",
                "ahi_score": 5,
            },
        ],
    )
    assert [row["evaluation_id"] for row in rows] == ["poor", "critical"]
    assert all(row["notification_status"] == "PENDING" for row in rows)


def test_evaluation_without_ahi_is_not_escalated():
    rows = prepare_anomaly_rows(
        inspection_id="inspection-1",
        evaluation_rows=[
            {
                "evaluation_id": "not-rated",
                "severity": 4,
                "condition_label": "Belum dinilai AHI",
            }
        ],
    )
    assert rows == []


def test_telegram_summary_contains_location_and_recommendation():
    message = build_telegram_anomaly_message(
        ultg_name="ULTG TOBA",
        gi_name="GI PORSEA",
        bay_name="PHT PSTAR",
        bay_functloc_id="BAY-1",
        measurement_date="2026-08-16",
        work_type="ROUTINE",
        stage_code="TAHAP_1",
        anomalies=[
            {
                "severity": 3,
                "equipment_group_code": "PMT",
                "point_code": "PMT_INSULATOR",
                "condition_label": "Kondisi II",
                "analyzed_delta_c": 12.5,
                "ahi_score": 4,
                "ahi_category": "Poor",
                "recommendation": "Lakukan perbaikan segera",
            }
        ],
    )
    assert "GI PORSEA" in message
    assert "12.5 °C" in message
    assert "Lakukan perbaikan segera" in message
