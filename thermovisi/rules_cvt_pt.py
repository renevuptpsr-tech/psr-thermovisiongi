from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .rules_neta import classify_over_ambient_delta, classify_similar_component_delta


RULE_SET_CODE = "THERMOVISI_CVT_PT_V1"

SUPPORTED_COMPONENTS = {
    "CLAMP_CONDUCTOR": "Klem/Konduktor",
    "CLAMP_MAIN_TERMINAL": "Klem Terminal Utama",
    "INSULATOR": "Isolator",
    "HOUSING": "Housing",
    "SECONDARY_BOX": "Box Sekunder",
}


@dataclass(frozen=True, slots=True)
class CvtPtRuleResult:
    rule_code: str
    method: str
    component_code: str
    condition: str
    recommendation: str
    severity: int
    delta_t1_c: float
    delta_t2_c: float
    delta_t1_condition: str
    delta_t2_condition: str
    governing_basis: str


def evaluate_cvt_pt_component(
    component_code: str,
    phase_temperatures_c: Mapping[str, float],
    ambient_temperature_c: float,
) -> CvtPtRuleResult:
    """Evaluasi satu titik CVT/PT yang sama pada minimal dua fasa."""
    component = component_code.strip().upper()
    if component not in SUPPORTED_COMPONENTS:
        raise ValueError(
            "component_code harus salah satu: " + ", ".join(sorted(SUPPORTED_COMPONENTS))
        )
    values = [float(value) for value in phase_temperatures_c.values()]
    if len(values) < 2:
        raise ValueError("Evaluasi CVT/PT membutuhkan minimal dua nilai suhu fasa.")

    delta_t1_c = max(values) - min(values)
    delta_t2_c = max(values) - float(ambient_temperature_c)
    delta_t1 = classify_similar_component_delta(delta_t1_c)
    delta_t2 = classify_over_ambient_delta(delta_t2_c)

    # Tabel khusus CVT/PT menempatkan ΔT1 mayor pada Kondisi IV.
    delta_t1_condition = "Kondisi IV" if delta_t1.severity == 4 else delta_t1.condition
    if delta_t2.severity > delta_t1.severity:
        governing = delta_t2
        condition = delta_t2.condition
        basis = "DELTA_T2_OVER_AMBIENT"
    else:
        governing = delta_t1
        condition = delta_t1_condition
        basis = "DELTA_T1_INTERPHASE"

    return CvtPtRuleResult(
        "CVT_PT_COMPONENT_THERMAL",
        f"{SUPPORTED_COMPONENTS[component].upper()} · ANTAR FASA + TERHADAP AMBIENT",
        component,
        condition,
        governing.recommendation,
        governing.severity,
        delta_t1_c,
        delta_t2_c,
        delta_t1_condition,
        delta_t2.condition,
        basis,
    )
