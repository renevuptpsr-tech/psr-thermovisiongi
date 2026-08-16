from thermovisi.rules_general import (
    evaluate_general_clamp_conductor,
    evaluate_general_phase,
)


def test_general_phase_uses_worst_neta_result():
    result = evaluate_general_phase({"R": 40, "S": 42, "T": 41}, 20)
    assert result.delta_t1_c == 2
    assert result.delta_t2_c == 22
    assert result.evaluation_basis == "DELTA_T2_OVER_AMBIENT"
    assert result.severity == 3


def test_general_pair_uses_load_correction():
    result = evaluate_general_clamp_conductor(
        42, 40, measurement_current_a=100, highest_current_a=200
    )
    assert result.evaluated_value_c == 8
    assert result.evaluation_basis == "LOAD_CORRECTED"
