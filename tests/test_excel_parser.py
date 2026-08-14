from io import BytesIO

from openpyxl import Workbook

from thermovisi.excel_parser import parse_workbook


def workbook_bytes() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "BAY1"
    ws["B15"] = "Titik A"
    ws["J15"] = 40
    ws["K15"] = "41,5"
    ws["L15"] = 42
    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def test_parse_phase_and_delta():
    items = [{
        "template_item_id": 1, "form_section_code": "MAIN", "sequence_no": 1,
        "source_sheet_pattern": r"^BAY\d+$", "source_row_no": 15, "source_occurrence_no": 1,
        "raw_point_label": "Titik A", "equipment_group_code": "PMT", "point_code": "POINT_A",
        "measurement_mode_code": "PHASE", "phase_codes": ["R", "S", "T"],
        "source_value_map": {"R": "J", "S": "K", "T": "L"}, "is_required": True,
    }]
    sheets, warnings = parse_workbook(workbook_bytes(), items, 30.0)
    assert warnings == []
    assert sheets[0].numeric_count == 3
    assert [m.temperature_c for m in sheets[0].measurements] == [40.0, 41.5, 42.0]
    assert [m.delta_ambient_c for m in sheets[0].measurements] == [10.0, 11.5, 12.0]


def test_label_search_single_value():
    wb = Workbook()
    ws = wb.active
    ws.title = "A. CUSTOM"
    ws["D20"] = "Suhu NGR Atas"
    ws["E20"] = 37.25
    buffer = BytesIO()
    wb.save(buffer)
    items = [{
        "template_item_id": 9, "form_section_code": "A", "sequence_no": 1,
        "source_sheet_pattern": r"^A\.", "source_row_no": None, "source_occurrence_no": 1,
        "raw_point_label": "Suhu NGR Atas", "equipment_group_code": "NGR", "point_code": "NGR_TOP",
        "measurement_mode_code": "SINGLE", "phase_codes": [],
        "source_value_map": {"VALUE": "E"}, "is_required": True,
    }]
    sheets, _ = parse_workbook(buffer.getvalue(), items, 30.0)
    assert sheets[0].measurements[0].source_cell_address == "E20"
    assert sheets[0].measurements[0].delta_ambient_c == 7.25
