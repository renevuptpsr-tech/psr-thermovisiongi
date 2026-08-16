from thermovisi.excel_parser import ParsedMeasurement, ParsedSheet
from thermovisi.review import build_sheet_review, compact_review_row_style, compact_review_rows


def measurement(item_id, point, phase, temperature):
    return ParsedMeasurement(
        sheet_name="SHEET-A",
        form_section_code="MAIN",
        sequence_no=item_id,
        template_item_id=item_id,
        equipment_group_code="LA",
        point_code=point,
        point_label=point,
        phase_code=phase,
        temperature_c=temperature,
        delta_ambient_c=None,
        source_cell_address=None,
        source_value_raw=str(temperature),
        data_quality_status="VALID",
        validation_message=None,
    )


def item(
    item_id,
    label,
    role=None,
    group=None,
    *,
    point_code="GENERIC",
    equipment="LA",
    position=None,
    instance=None,
):
    return {
        "template_item_id": item_id,
        "form_section_code": "MAIN",
        "sequence_no": item_id,
        "raw_equipment_label": "LA",
        "raw_point_label": label,
        "equipment_group_code": equipment,
        "point_code": point_code,
        "position_code": position,
        "instance_no": instance,
        "comparison_group_code": group,
        "comparison_role": role,
    }


def test_review_is_wide_and_calculates_interphase_analysis():
    sheet = ParsedSheet(
        sheet_name="SHEET-A",
        measurements=[
            measurement(1, "ISOLATOR", "R", 30.0),
            measurement(1, "ISOLATOR", "S", 32.0),
            measurement(1, "ISOLATOR", "T", 31.0),
        ],
        numeric_count=3,
        invalid_count=0,
        warning_count=0,
    )

    rows = build_sheet_review(
        sheet,
        [
            item(
                1,
                "Bushing Primer - Atas",
                point_code="TRF_BUSHING",
                equipment="TRF_BUSHING_PRIMARY",
                position="TOP",
            )
        ],
        measurement_current_a=100,
        monthly_peak_current_a=100,
        ambient_temperature_c=28,
    )

    assert len(rows) == 1
    assert rows[0]["Suhu R (°C)"] == 30.0
    assert rows[0]["ΔT R-S (°C)"] == 2.0
    assert rows[0]["ΔT analisa (°C)"] == 2.0
    assert "PERBANDINGAN ANTAR FASA" in rows[0]["Metode analisa"]
    assert rows[0]["Kondisi"] == "Normal"
    assert rows[0]["Rule set"] == "THERMOVISI_TRAFO_V1"


def test_clamp_conductor_delta_is_corrected_by_load():
    measurements = []
    for phase, clamp, conductor in (("R", 40, 30), ("S", 38, 30), ("T", 36, 30)):
        measurements.extend(
            [measurement(1, "CLAMP", phase, clamp), measurement(2, "CONDUCTOR", phase, conductor)]
        )
    sheet = ParsedSheet("SHEET-A", measurements, 6, 0, 0)

    rows = build_sheet_review(
        sheet,
        [
            item(1, "Klem LA", "CLAMP", "LA_TERMINAL"),
            item(2, "Konduktor LA", "CONDUCTOR", "LA_TERMINAL"),
        ],
        measurement_current_a=100,
        monthly_peak_current_a=200,
        ambient_temperature_c=28,
    )

    assert rows[0]["ΔT aktual R (°C)"] == 10.0
    assert rows[0]["ΔT evaluasi R (°C)"] == 40.0
    assert rows[0]["ΔT analisa (°C)"] == 40.0
    assert rows[0]["Kondisi"] == "Perlu perbaikan segera"
    assert rows[1]["Metode analisa"] == "REFERENSI KLEM–KONDUKTOR"


def test_single_bushing_measurement_uses_signed_ambient_rise():
    single = measurement(1, "BUSHING_TOP", None, 31.0)
    sheet = ParsedSheet("SHEET-A", [single], 1, 0, 0)

    rows = build_sheet_review(
        sheet,
        [
            item(
                1,
                "Bushing Tersier - Atas",
                point_code="TRF_BUSHING",
                equipment="TRF_BUSHING_TERTIARY",
                position="TOP",
            )
        ],
        measurement_current_a=100,
        monthly_peak_current_a=100,
        ambient_temperature_c=32.0,
    )

    assert rows[0]["Suhu (°C)"] == 31.0
    assert rows[0]["Kenaikan maks. terhadap lingkungan (°C)"] == -1.0
    assert "KENAIKAN TERHADAP LINGKUNGAN" in rows[0]["Metode analisa"]


def test_clamp_conductor_uses_raw_delta_when_current_is_zero():
    sheet = ParsedSheet(
        "SHEET-A",
        [measurement(1, "CLAMP", "R", 50), measurement(2, "CONDUCTOR", "R", 30)],
        2,
        0,
        0,
    )
    rows = build_sheet_review(
        sheet,
        [
            item(1, "Klem LA", "CLAMP", "LA_TERMINAL"),
            item(2, "Konduktor LA", "CONDUCTOR", "LA_TERMINAL"),
        ],
        measurement_current_a=0,
        monthly_peak_current_a=200,
        ambient_temperature_c=28,
    )

    assert rows[0]["ΔT aktual R (°C)"] == 20.0
    assert rows[0]["ΔT evaluasi R (°C)"] == 20.0
    assert rows[0]["Basis evaluasi"] == "RAW_DELTA_ZERO_LOAD"
    assert rows[0]["Kondisi"] == "Perlu pemantauan"


def test_review_evaluates_three_point_transformer_gradient():
    sheet = ParsedSheet(
        "SHEET-A",
        [
            measurement(1, "MAIN_TOP", None, 52),
            measurement(2, "MAIN_MIDDLE", None, 46),
            measurement(3, "MAIN_BOTTOM", None, 39),
        ],
        3,
        0,
        0,
    )
    items = [
        item(1, "Maintank Atas", equipment="TRF_MAIN_TANK", position="TOP"),
        item(2, "Maintank Tengah", equipment="TRF_MAIN_TANK", position="MIDDLE"),
        item(3, "Maintank Bawah", equipment="TRF_MAIN_TANK", position="BOTTOM"),
    ]
    rows = build_sheet_review(
        sheet,
        items,
        measurement_current_a=100,
        monthly_peak_current_a=100,
        ambient_temperature_c=30,
    )

    assert rows[0]["Pola gradasi"] == "TOP_TO_BOTTOM_DESCENDING"
    assert rows[0]["Kondisi"] == "Gradasi normal"
    assert rows[0]["ΔT analisa (°C)"] == 13.0


def test_compact_review_uses_one_measurement_column_for_phase_and_single_values():
    rows = [
        {
            "No.": 1, "Bagian": "A", "Peralatan": "Bushing",
            "Titik peralatan yang diperiksa": "Bushing Primer",
            "Suhu R (°C)": 31.0, "Suhu S (°C)": 32.0, "Suhu T (°C)": 33.0,
            "Suhu (°C)": None, "ΔT analisa (°C)": 2.0,
            "Suhu maksimum (°C)": 33.0,
            "Kenaikan maks. terhadap lingkungan (°C)": 3.0,
            "Pola gradasi": None, "Kondisi": "Normal",
            "AHI Thermovisi": 1, "Kategori AHI": "Very Good",
            "Kesimpulan / rekomendasi": "Inspeksi rutin.",
            "Status data": "VALID", "Status analisa": "TEREVALUASI",
        },
        {
            "No.": 2, "Bagian": "A", "Peralatan": "Radiator",
            "Titik peralatan yang diperiksa": "Radiator No. 1 Atas",
            "Suhu R (°C)": None, "Suhu S (°C)": None, "Suhu T (°C)": None,
            "Suhu (°C)": 45.5, "ΔT analisa (°C)": None,
            "Suhu maksimum (°C)": None,
            "Kenaikan maks. terhadap lingkungan (°C)": None,
            "Pola gradasi": None, "Kondisi": "",
            "AHI Thermovisi": None, "Kategori AHI": None,
            "Kesimpulan / rekomendasi": "", "Status data": "VALID",
            "Status analisa": "BELUM DIEVALUASI",
        },
    ]

    compact = compact_review_rows(rows)

    assert compact[0]["Pengukuran"] == "R 31,0 | S 32,0 | T 33,0 °C"
    assert compact[1]["Pengukuran"] == "45,5 °C"
    assert set(compact[0]) == {
        "No.", "Peralatan", "Titik yang diperiksa", "Pengukuran",
        "Delta T", "Kondisi", "AHI Thermovisi",
        "Kesimpulan / Rekomendasi", "Status Data",
    }


def test_invalid_compact_review_row_is_colored_red():
    import pandas as pd

    row = pd.Series(
        {
            "No.": 1, "Peralatan": "Bushing", "Titik yang diperiksa": "Primer",
            "Pengukuran": "—", "Delta T": "—", "Kondisi": "—",
            "AHI Thermovisi": "Tidak dapat dievaluasi",
            "Kesimpulan / Rekomendasi": "Nilai wajib kosong", "Status Data": "INVALID",
        }
    )
    styles = compact_review_row_style(row)

    assert len(styles) == len(row)
    assert "#FEE2E2" in styles[row.index.get_loc("Pengukuran")]
    assert "#FEE2E2" in styles[row.index.get_loc("Status Data")]
    assert styles[row.index.get_loc("Peralatan")] == ""


def test_not_measured_review_row_has_no_ahi_and_is_colored_blue():
    import pandas as pd

    row = pd.Series(
        {
            "No.": 1, "Peralatan": "LA", "Titik yang diperiksa": "Body Atas",
            "Pengukuran": "—", "Delta T": "—", "Kondisi": "—",
            "AHI Thermovisi": "Tidak diukur",
            "Kesimpulan / Rekomendasi": "Pengukuran tidak dilakukan",
            "Status Data": "NOT_MEASURED",
        }
    )
    styles = compact_review_row_style(row)
    assert "#E0F2FE" in styles[row.index.get_loc("Pengukuran")]
    assert "#E0F2FE" in styles[row.index.get_loc("Status Data")]
