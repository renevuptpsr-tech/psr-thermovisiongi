from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .rules_neta import classify_over_ambient_delta, classify_similar_component_delta


RULE_SET_CODE = "THERMOVISI_PMS_V1"


@dataclass(frozen=True, slots=True)
class PmsRuleResult:
    rule_code: str
    method: str
    condition: str
    recommendation: str
    severity: int
    delta_t1_c: float
    delta_t2_c: float
    delta_t1_condition: str
    delta_t2_condition: str
    governing_basis: str


def _governing_result(
    *,
    rule_code: str,
    method: str,
    delta_t1_c: float,
    delta_t2_c: float,
) -> PmsRuleResult:
    delta_t1 = classify_similar_component_delta(delta_t1_c)
    delta_t2 = classify_over_ambient_delta(delta_t2_c)
    if delta_t2.severity > delta_t1.severity:
        governing, basis = delta_t2, "DELTA_T2_OVER_AMBIENT"
    else:
        governing, basis = delta_t1, "DELTA_T1_COMPARISON"
    return PmsRuleResult(
        rule_code,
        method,
        governing.condition,
        governing.recommendation,
        governing.severity,
        delta_t1_c,
        delta_t2_c,
        delta_t1.condition,
        delta_t2.condition,
        basis,
    )


def evaluate_pms_main_terminal(
    clamp_temperature_c: float,
    conductor_temperature_c: float,
    ambient_temperature_c: float,
) -> PmsRuleResult:
    """Terminal utama: ΔT1 aktual klem–konduktor dan ΔT2 titik terpanas–ambient."""
    clamp = float(clamp_temperature_c)
    conductor = float(conductor_temperature_c)
    delta_t1 = abs(clamp - conductor)
    delta_t2 = max(clamp, conductor) - float(ambient_temperature_c)
    return _governing_result(
        rule_code="PMS_MAIN_TERMINAL",
        method="TERMINAL UTAMA · KLEM–KONDUKTOR",
        delta_t1_c=delta_t1,
        delta_t2_c=delta_t2,
    )


def evaluate_pms_blade(
    phase_temperatures_c: Mapping[str, float],
    ambient_temperature_c: float,
) -> PmsRuleResult:
    """Pisau PMS: ΔT1 maksimum antar-fasa dan ΔT2 fasa terpanas–ambient."""
    values = [float(value) for value in phase_temperatures_c.values()]
    if len(values) < 2:
        raise ValueError("Evaluasi pisau PMS membutuhkan minimal dua nilai suhu fasa.")
    delta_t1 = max(values) - min(values)
    delta_t2 = max(values) - float(ambient_temperature_c)
    return _governing_result(
        rule_code="PMS_BLADE_INTERPHASE",
        method="PISAU PMS · PERBANDINGAN ANTAR FASA",
        delta_t1_c=delta_t1,
        delta_t2_c=delta_t2,
    )
