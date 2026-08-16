from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .rules_neta import classify_over_ambient_delta, classify_similar_component_delta
from .rules_trafo import evaluate_clamp_conductor


@dataclass(frozen=True, slots=True)
class GeneralRuleResult:
    rule_code: str
    method: str
    condition: str
    recommendation: str
    severity: int
    evaluated_value_c: float
    evaluation_basis: str
    delta_t1_c: float | None = None
    delta_t2_c: float | None = None


def evaluate_general_phase(
    phase_temperatures_c: Mapping[str, float],
    ambient_temperature_c: float,
) -> GeneralRuleResult:
    """Fallback NETA untuk titik fase tanpa rule peralatan yang lebih spesifik."""
    values = [float(value) for value in phase_temperatures_c.values()]
    if len(values) < 2:
        raise ValueError("Evaluasi general membutuhkan minimal dua nilai suhu fasa.")
    delta_t1 = max(values) - min(values)
    delta_t2 = max(values) - float(ambient_temperature_c)
    interphase = classify_similar_component_delta(delta_t1)
    ambient = classify_over_ambient_delta(delta_t2)
    if ambient.severity > interphase.severity:
        governing, basis, evaluated = ambient, "DELTA_T2_OVER_AMBIENT", delta_t2
    else:
        governing, basis, evaluated = interphase, "DELTA_T1_INTERPHASE", delta_t1
    recommendation = governing.recommendation
    if governing.severity == 0:
        recommendation = "Lanjutkan inspeksi rutin."
    return GeneralRuleResult(
        "GENERAL_NETA_PHASE",
        "GENERAL NETA · ΔT1 ANTAR FASA + ΔT2 TERHADAP AMBIENT",
        governing.condition,
        recommendation,
        governing.severity,
        evaluated,
        basis,
        delta_t1,
        delta_t2,
    )


def evaluate_general_clamp_conductor(
    clamp_temperature_c: float,
    conductor_temperature_c: float,
    *,
    measurement_current_a: float,
    highest_current_a: float,
) -> GeneralRuleResult:
    """Fallback pasangan klem–konduktor dengan koreksi beban yang disepakati."""
    result = evaluate_clamp_conductor(
        clamp_temperature_c,
        conductor_temperature_c,
        measurement_current_a=measurement_current_a,
        highest_current_a=highest_current_a,
    )
    return GeneralRuleResult(
        "GENERAL_CLAMP_CONDUCTOR",
        "GENERAL · " + result.method,
        result.condition,
        result.recommendation,
        result.severity,
        float(result.evaluated_value_c or 0),
        result.evaluation_basis or "DIRECT_DELTA",
    )
