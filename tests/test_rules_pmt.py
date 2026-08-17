import pytest

from thermovisi.rules_pmt import (
    RULE_SET_CODE,
    evaluate_grading_capacitor,
    evaluate_interrupter_chamber,
    evaluate_pmt_clamp_delta,
)


def test_rule_set_is_versioned():
    assert RULE_SET_CODE == "THERMOVISI_PMT_V1"


@pytest.mark.parametrize(
    ("delta", "expected"),
    [(0.9, "Normal"), (1.0, "Kondisi I"), (3.9, "Kondisi I"),
     (4.0, "Kondisi II"), (15.0, "Kondisi II"), (15.1, "Kondisi III")],
)
def test_clamp_uses_actual_delta_without_load_correction(delta, expected):
    result = evaluate_pmt_clamp_delta(40 + delta, 40, reference_role="CONDUCTOR")
    assert result.condition == expected
    assert result.evaluated_value_c == pytest.approx(delta)
    assert result.evaluation_basis == "ACTUAL_DELTA_CONDUCTOR"


def test_grading_capacitor_recommends_capacitance_measurement():
    result = evaluate_grading_capacitor({"R": 40, "S": 42, "T": 40.5})
    assert result.condition == "Kondisi I"
    assert result.evaluated_value_c == 2
    assert "kapasitansi" in result.recommendation


@pytest.mark.parametrize(
    ("maximum", "expected"),
    [(30.9, "Normal"), (31, "Kondisi I"), (40.9, "Kondisi I"),
     (41, "Kondisi II"), (50.9, "Kondisi II"), (51, "Kondisi III"),
     (70, "Kondisi III"), (70.1, "Kondisi IV")],
)
def test_interrupter_ambient_neta_ranges(maximum, expected):
    result = evaluate_interrupter_chamber({"R": maximum, "S": maximum, "T": maximum}, 30)
    assert result.ambient_condition == expected


def test_interrupter_uses_the_more_critical_result():
    result = evaluate_interrupter_chamber({"R": 40, "S": 58, "T": 41}, 30)
    assert result.interphase_condition == "Kondisi III"
    assert result.ambient_condition == "Kondisi III"
    assert result.condition == "Kondisi III"
    assert result.governing_basis == "DELTA_INTERPHASE"


def test_interrupter_rejects_single_phase():
    with pytest.raises(ValueError, match="minimal dua"):
        evaluate_interrupter_chamber({"R": 40}, 30)
