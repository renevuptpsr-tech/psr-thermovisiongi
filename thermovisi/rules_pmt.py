from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .rules_neta import classify_over_ambient_delta, classify_similar_component_delta


RULE_SET_CODE = "THERMOVISI_PMT_V1"


@dataclass(frozen=True, slots=True)
class PmtRuleResult:
    rule_code: str
    method: str
    condition: str
    recommendation: str
    severity: int
    evaluated_value_c: float
    evaluation_basis: str


@dataclass(frozen=True, slots=True)
class InterrupterResult:
    rule_code: str
    method: str
    condition: str
    recommendation: str
    severity: int
    delta_interphase_c: float
    delta_over_ambient_c: float
    interphase_condition: str
    ambient_condition: str
    governing_basis: str


def _validate_temperatures(phase_temperatures_c: Mapping[str, float]) -> list[float]:
    values = [float(value) for value in phase_temperatures_c.values()]
    if len(values) < 2:
        raise ValueError("Evaluasi antar-fasa membutuhkan minimal dua nilai suhu.")
    return values


def evaluate_pmt_clamp_delta(
    clamp_temperature_c: float,
    reference_temperature_c: float,
    *,
    reference_role: str,
) -> PmtRuleResult:
    """Evaluasi ΔT aktual klem terhadap konduktor atau terminal utama."""
    role = reference_role.strip().upper()
    if role not in {"CONDUCTOR", "MAIN_TERMINAL"}:
        raise ValueError("reference_role harus CONDUCTOR atau MAIN_TERMINAL.")
    delta_c = abs(float(clamp_temperature_c) - float(reference_temperature_c))
    classification = classify_similar_component_delta(delta_c)
    condition, severity = classification.condition, classification.severity
    if condition == "Normal":
        recommendation = "Lanjutkan pengujian rutin tiga bulanan."
    elif condition == "Kondisi I":
        recommendation = "Lanjutkan pengujian rutin tiga bulanan."
    elif condition == "Kondisi II":
        recommendation = "Jadwalkan perbaikan atau penggantian seperlunya."
    else:
        recommendation = "Lakukan perbaikan atau penggantian secepatnya."
    label = "KONDUKTOR" if role == "CONDUCTOR" else "TERMINAL UTAMA"
    return PmtRuleResult(
        "PMT_CLAMP_DELTA",
        f"KLEM–{label} · ΔT AKTUAL",
        condition,
        recommendation,
        severity,
        delta_c,
        f"ACTUAL_DELTA_{role}",
    )


def evaluate_grading_capacitor(
    phase_temperatures_c: Mapping[str, float],
) -> PmtRuleResult:
    """Evaluasi perbedaan suhu antar-fasa grading kapasitor."""
    values = _validate_temperatures(phase_temperatures_c)
    delta_c = max(values) - min(values)
    classification = classify_similar_component_delta(delta_c)
    condition, severity = classification.condition, classification.severity
    if condition == "Normal":
        recommendation = "Tidak ditemukan perbedaan suhu antar-fasa yang signifikan."
    else:
        recommendation = "Lakukan investigasi lebih lanjut dan pengukuran nilai kapasitansi."
    return PmtRuleResult(
        "PMT_GRADING_CAPACITOR_INTERPHASE",
        "GRADING KAPASITOR · PERBEDAAN SUHU ANTAR FASA",
        condition,
        recommendation,
        severity,
        delta_c,
        "SIMILAR_COMPONENT_INTERPHASE",
    )


def evaluate_interrupter_chamber(
    phase_temperatures_c: Mapping[str, float],
    ambient_temperature_c: float,
) -> InterrupterResult:
    """Evaluasi ΔT1 antar-fasa dan ΔT2 suhu maksimum terhadap ambient."""
    values = _validate_temperatures(phase_temperatures_c)
    delta_interphase = max(values) - min(values)
    delta_ambient = max(values) - float(ambient_temperature_c)
    interphase = classify_similar_component_delta(delta_interphase)
    ambient = classify_over_ambient_delta(delta_ambient)
    inter_condition, inter_recommendation, inter_severity = (
        interphase.condition, interphase.recommendation, interphase.severity
    )
    ambient_condition, ambient_recommendation, ambient_severity = (
        ambient.condition, ambient.recommendation, ambient.severity
    )

    if ambient_severity > inter_severity:
        condition = ambient_condition
        recommendation = ambient_recommendation
        severity = ambient_severity
        basis = "DELTA_OVER_AMBIENT"
    else:
        condition = inter_condition
        recommendation = inter_recommendation
        severity = inter_severity
        basis = "DELTA_INTERPHASE"

    return InterrupterResult(
        "PMT_INTERRUPTER_CHAMBER",
        "INTERRUPTER CHAMBER · ΔT1 ANTAR FASA + ΔT2 TERHADAP AMBIENT",
        condition,
        recommendation,
        severity,
        delta_interphase,
        delta_ambient,
        inter_condition,
        ambient_condition,
        basis,
    )
