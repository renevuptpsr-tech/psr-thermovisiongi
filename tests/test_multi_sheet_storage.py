from datetime import date, time

import pytest

from thermovisi.excel_parser import ParsedSheet
from thermovisi.storage_model import prepare_evaluation_rows, prepare_inspection_groups


def sheet(name):
    return ParsedSheet(name, [], 0, 0, 0)


def metadata():
    return {
        "measurement_date": date(2026, 8, 16),
        "measurement_time": time(18, 0),
        "measurement_current_a": 100,
        "monthly_peak_current_a": 200,
        "ambient_temperature_c": 30,
    }


def test_two_trafo_sheets_create_one_inspection():
    groups = prepare_inspection_groups(
        upload_id="00000000-0000-0000-0000-000000000001",
        template_code="TRAFO_V1",
        parsed_sheets=[sheet("Trafo"), sheet("Bay")],
        sheet_assignments={
            "Trafo": {"bay_flc": "BAY-1", "sheet_role": "TRAFO", "form_section_code": "A"},
            "Bay": {"bay_flc": "BAY-1", "sheet_role": "BAY", "form_section_code": "B"},
        },
        metadata_by_bay={"BAY-1": metadata()},
        executor="Tester",
        notes=None,
        user_id="00000000-0000-0000-0000-000000000002",
    )
    assert len(groups) == 1
    assert groups[0]["inspection"]["source_sheet_name"] == "Trafo"
    assert [item["sheet_role_code"] for item in groups[0]["sheets"]] == ["TRAFO", "BAY"]


def test_same_role_cannot_be_assigned_twice_to_one_bay():
    with pytest.raises(ValueError, match="duplikat"):
        prepare_inspection_groups(
            upload_id="00000000-0000-0000-0000-000000000001",
            template_code="TRAFO_V1",
            parsed_sheets=[sheet("A"), sheet("B")],
            sheet_assignments={
                "A": {"bay_flc": "BAY-1", "sheet_role": "TRAFO"},
                "B": {"bay_flc": "BAY-1", "sheet_role": "TRAFO"},
            },
            metadata_by_bay={"BAY-1": metadata()},
            executor=None,
            notes=None,
            user_id="00000000-0000-0000-0000-000000000002",
        )


def test_review_evaluation_is_prepared_for_database_audit():
    rows = prepare_evaluation_rows(
        inspection_id="00000000-0000-0000-0000-000000000010",
        inspection_sheet_id="00000000-0000-0000-0000-000000000011",
        review_rows=[
            {
                "Template item ID": 101,
                "Point code": "TRF_BUSHING",
                "Equipment group code": "TRF_BUSHING_PRIMARY",
                "Comparison group code": None,
                "Status analisa": "TEREVALUASI",
                "Status data": "VALID",
                "Suhu R (°C)": 31.0,
                "Suhu S (°C)": 33.0,
                "Suhu T (°C)": 32.0,
                "Suhu (°C)": None,
                "ΔT R-S (°C)": 2.0,
                "ΔT S-T (°C)": 1.0,
                "ΔT T-R (°C)": 1.0,
                "ΔT analisa (°C)": 2.0,
                "Kenaikan maks. terhadap lingkungan (°C)": 3.0,
                "Suhu maksimum (°C)": 33.0,
                "Pola gradasi": None,
                "Rule set": "THERMOVISI_TRAFO_V1",
                "Kode aturan": "TRF_BUSHING_INTERPHASE",
                "Metode analisa": "PERBANDINGAN ANTAR FASA",
                "Basis evaluasi": "INTERPHASE_DELTA",
                "Kondisi": "Normal",
                "Kesimpulan / rekomendasi": "Inspeksi rutin.",
                "Tingkat perhatian": 0,
                "AHI Thermovisi": 1,
                "Kategori AHI": "Very Good",
            }
        ],
        sheet_template_item_ids={101},
        metadata=metadata(),
    )
    assert len(rows) == 1
    assert rows[0]["evaluation_scope_code"] == "PHASE_GROUP"
    assert rows[0]["phase_delta_c"] == 2.0
    assert rows[0]["ahi_score"] == 1
    assert rows[0]["input_snapshot"]["ambient_temperature_c"] == 30.0


def test_covered_reference_row_is_not_stored_as_duplicate_evaluation():
    rows = prepare_evaluation_rows(
        inspection_id="00000000-0000-0000-0000-000000000010",
        inspection_sheet_id="00000000-0000-0000-0000-000000000011",
        review_rows=[
            {
                "Template item ID": 102,
                "Status analisa": "TERCAKUP PADA PASANGAN",
            }
        ],
        sheet_template_item_ids={102},
        metadata=metadata(),
    )
    assert rows == []
