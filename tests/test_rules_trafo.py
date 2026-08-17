import pytest

from thermovisi.rules_trafo import (
    RULE_SET_CODE,
    evaluate_bushing_ambient,
    evaluate_bushing_head,
    evaluate_bushing_interphase,
    evaluate_clamp_conductor,
    evaluate_vertical_gradient,
)


def test_rule_set_is_versioned():
    assert RULE_SET_CODE == "THERMOVISI_TRAFO_V1"


@pytest.mark.parametrize(
    ("delta", "condition"),
    [(0, "Normal"), (3.999, "Normal"), (4, "Defisiensi"), (15.999, "Defisiensi"), (16, "Ketidaknormalan mayor")],
)
def test_bushing_interphase_boundaries(delta, condition):
    assert evaluate_bushing_interphase(delta).condition == condition


def test_bushing_ambient_and_head_boundaries():
    assert evaluate_bushing_ambient(64.9, 30).condition == "Normal"
    assert evaluate_bushing_ambient(65, 30).condition == "Tidak normal"
    assert evaluate_bushing_head(90).condition == "Normal"
    assert evaluate_bushing_head(90.01).condition == "Tidak normal"


@pytest.mark.parametrize(
    ("delta", "condition"),
    [
        (9.99, "Normal"),
        (10, "Perlu pemantauan"),
        (25, "Perlu perbaikan terencana"),
        (40, "Perlu perbaikan segera"),
        (70, "Perlu perbaikan segera"),
        (70.01, "Darurat"),
    ],
)
def test_clamp_boundaries(delta, condition):
    result = evaluate_clamp_conductor(
        delta,
        0,
        measurement_current_a=100,
        highest_current_a=100,
    )
    assert result.evaluated_value_c == pytest.approx(delta)
    assert result.condition == condition


def test_clamp_zero_load_uses_raw_delta():
    result = evaluate_clamp_conductor(
        50,
        30,
        measurement_current_a=0,
        highest_current_a=200,
    )
    assert result.evaluated_value_c == 20
    assert result.evaluation_basis == "RAW_DELTA_ZERO_LOAD"


def test_gradient_is_observation_only_at_zero_load():
    result = evaluate_vertical_gradient(
        52,
        46,
        39,
        equipment_group_code="TRF_MAIN_TANK",
        measurement_current_a=0,
    )
    assert result.condition == "Observasi tanpa beban"
    assert result.pattern_code == "TOP_TO_BOTTOM_DESCENDING"
    assert result.evaluation_basis == "OBSERVATION_ONLY_ZERO_LOAD"
