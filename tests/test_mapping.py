from thermovisi.mapping import (
    SINGLE_SHEET_MODE,
    TRAFO_TWO_SHEET_MODE,
    mapping_mode_from_template,
    sheet_mapping_from_bays,
    trafo_sheet_mapping_from_bays,
)


def test_only_trafo_template_requires_two_sheets():
    mode = mapping_mode_from_template(
        {"template_code": "THERMOVISI_TRAFO_V1", "template_name": "Trafo Daya"},
        [{"form_section_code": "A"}, {"form_section_code": "B"}],
    )
    assert mode == TRAFO_TWO_SHEET_MODE


def test_non_trafo_template_uses_one_sheet():
    mode = mapping_mode_from_template(
        {"template_code": "THERMOVISI_PHT_150_V1", "template_name": "PHT 150 kV"},
        [{"form_section_code": "MAIN"}],
    )
    assert mode == SINGLE_SHEET_MODE


def test_mapping_is_defined_from_each_bay():
    mapping, errors = sheet_mapping_from_bays(
        [
            {"bay_flc": "BAY-01", "Sheet Excel": "PHT PORSEA"},
            {"bay_flc": "BAY-02", "Sheet Excel": "PHT LAGUBOTI"},
        ],
        expected_bay_ids=["BAY-01", "BAY-02"],
        valid_sheet_names=["PHT PORSEA", "PHT LAGUBOTI", "CATATAN"],
    )

    assert errors == []
    assert mapping == {"PHT PORSEA": "BAY-01", "PHT LAGUBOTI": "BAY-02"}


def test_same_sheet_cannot_target_two_bays():
    mapping, errors = sheet_mapping_from_bays(
        [
            {"bay_flc": "BAY-01", "Sheet Excel": "SHEET-1"},
            {"bay_flc": "BAY-02", "Sheet Excel": "SHEET-1"},
        ],
        expected_bay_ids=["BAY-01", "BAY-02"],
        valid_sheet_names=["SHEET-1"],
    )

    assert mapping == {"SHEET-1": "BAY-01"}
    assert any("Satu sheet hanya boleh digunakan untuk satu Bay" in error for error in errors)
    assert any("BAY-02" in error for error in errors)


def test_every_selected_bay_must_choose_a_sheet():
    mapping, errors = sheet_mapping_from_bays(
        [{"bay_flc": "BAY-01", "Sheet Excel": "SHEET-1"}],
        expected_bay_ids=["BAY-01", "BAY-02"],
        valid_sheet_names=["SHEET-1", "SHEET-2"],
    )

    assert mapping == {"SHEET-1": "BAY-01"}
    assert any("BAY-02" in error for error in errors)


def test_trafo_bay_requires_two_different_sheets():
    mapping, errors = trafo_sheet_mapping_from_bays(
        [{"bay_flc": "BAY-01", "Sheet Trafo": "TD 1 TRAFO", "Sheet Bay": "TD 1"}],
        expected_bay_ids=["BAY-01"],
        valid_sheet_names=["TD 1 TRAFO", "TD 1"],
        sheet_sections={"TD 1 TRAFO": {"A"}, "TD 1": {"B"}},
    )

    assert errors == []
    assert mapping == {
        "TD 1 TRAFO": {"bay_flc": "BAY-01", "sheet_role": "TRAFO", "form_section_code": "A"},
        "TD 1": {"bay_flc": "BAY-01", "sheet_role": "BAY", "form_section_code": "B"},
    }


def test_trafo_and_bay_sheet_cannot_be_swapped():
    _, errors = trafo_sheet_mapping_from_bays(
        [{"bay_flc": "BAY-01", "Sheet Trafo": "BAGIAN-B", "Sheet Bay": "BAGIAN-A"}],
        expected_bay_ids=["BAY-01"],
        valid_sheet_names=["BAGIAN-A", "BAGIAN-B"],
        sheet_sections={"BAGIAN-A": {"A"}, "BAGIAN-B": {"B"}},
    )

    assert any("Sheet Trafo" in error and "bagian B" in error for error in errors)
    assert any("Sheet Bay" in error and "bagian A" in error for error in errors)
