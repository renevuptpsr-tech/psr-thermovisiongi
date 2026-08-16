from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .rules_neta import classify_over_ambient_delta, classify_similar_component_delta


@dataclass(frozen=True, slots=True)
class InsulatorRuleResult:
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


def evaluate_insulator_neta(
    equipment_code: str,
    phase_temperatures_c: Mapping[str, float],
    ambient_temperature_c: float,
) -> InsulatorRuleResult:
    """Normalisasi isolator antar-fasa dan terhadap ambient berbasis NETA."""
    equipment = equipment_code.strip().upper()
    if equipment not in {"PMT", "PMS"}:
        raise ValueError("equipment_code harus PMT atau PMS.")
    values = [float(value) for value in phase_temperatures_c.values()]
    if len(values) < 2:
        raise ValueError("Evaluasi isolator membutuhkan minimal dua nilai suhu fasa.")

    delta_t1_c = max(values) - min(values)
    delta_t2_c = max(values) - float(ambient_temperature_c)
    delta_t1 = classify_similar_component_delta(delta_t1_c)
    delta_t2 = classify_over_ambient_delta(delta_t2_c)
    if delta_t2.severity > delta_t1.severity:
        governing = delta_t2
        basis = "DELTA_T2_OVER_AMBIENT"
    else:
        governing = delta_t1
        basis = "DELTA_T1_INTERPHASE"

    if governing.severity == 0:
        recommendation = "Lanjutkan inspeksi rutin."
    elif governing.severity == 1:
        recommendation = "Lakukan investigasi lanjutan dan verifikasi citra termal."
    elif governing.severity == 2:
        recommendation = "Jadwalkan pemeriksaan dan perbaikan."
    elif governing.severity == 3:
        recommendation = "Lakukan monitoring kontinu sampai dilakukan perbaikan."
    else:
        recommendation = "Ketidaknormalan mayor; lakukan perbaikan atau penggantian segera."

    return InsulatorRuleResult(
        f"{equipment}_INSULATOR_NETA",
        f"ISOLATOR {equipment} · ΔT1 ANTAR FASA + ΔT2 TERHADAP AMBIENT",
        governing.condition,
        recommendation,
        governing.severity,
        delta_t1_c,
        delta_t2_c,
        delta_t1.condition,
        delta_t2.condition,
        basis,
    )
