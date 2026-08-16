from datetime import date, time

import pytest

from thermovisi.excel_parser import ParsedSheet
from thermovisi.storage_model import prepare_inspection_groups


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
