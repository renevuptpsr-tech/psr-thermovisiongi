import pytest

from thermovisi.rules_ct import (
    RULE_SET_CODE,
    evaluate_ct_clamp,
    evaluate_ct_insulator_housing,
)


def test_rule_set_is_versioned():
    assert RULE_SET_CODE == "THERMOVISI_CT_V1"


def test_ct_clamp_uses_load_correction():
    result = evaluate_ct_clamp(42, 40, measurement_current_a=100, highest_current_a=200)
    assert result.raw_delta_c == 2
    assert result.evaluated_delta_c == 8
    assert result.condition == "Normal"
    assert result.evaluation_basis == "LOAD_CORRECTED"


@pytest.mark.parametrize(
    ("delta", "expected"),
    [(9.9, "Normal"), (10, "Perlu pengukuran ulang"), (24.9, "Perlu pengukuran ulang"),
     (25, "Perlu perbaikan terencana"), (39.9, "Perlu perbaikan terencana"),
     (40, "Perlu perbaikan segera"), (70, "Perlu perbaikan segera"), (70.1, "Darurat")],
)
def test_ct_clamp_boundaries(delta, expected):
    result = evaluate_ct_clamp(40 + delta, 40, measurement_current_a=100, highest_current_a=100)
    assert result.condition == expected


def test_ct_clamp_zero_load_uses_raw_delta_with_limitation():
    result = evaluate_ct_clamp(52, 40, measurement_current_a=0, highest_current_a=200)
    assert result.evaluated_delta_c == 12
    assert result.evaluation_basis == "RAW_DELTA_ZERO_LOAD"
    assert "tidak mewakili" in result.recommendation


def test_ct_housing_uses_more_critical_ambient_result():
    result = evaluate_ct_insulator_housing("HOUSING", {"R": 40, "S": 42, "T": 41}, 30)
    assert result.delta_t1_c == 2
    assert result.delta_t2_c == 12
    assert result.delta_t1_condition == "Kondisi I"
    assert result.delta_t2_condition == "Kondisi II"
    assert result.condition == "Kondisi II"
    assert result.governing_basis == "DELTA_T2_OVER_AMBIENT"


def test_ct_insulator_major_condition_requires_immediate_action():
    result = evaluate_ct_insulator_housing("INSULATOR", {"R": 40, "S": 56, "T": 41}, 30)
    assert result.severity == 4
    assert result.condition == "Ketidaknormalan mayor"
    assert "segera" in result.recommendation


def test_ct_body_requires_two_phases():
    with pytest.raises(ValueError, match="minimal dua"):
        evaluate_ct_insulator_housing("HOUSING", {"R": 40}, 30)
