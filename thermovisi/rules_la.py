from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .rules_neta import classify_over_ambient_delta, classify_similar_component_delta


RULE_SET_CODE = "THERMOVISI_LA_NORMALIZED_V1"
REFERENCE_BASIS = "NETA_GENERIC_NORMALIZATION"

_COMPONENT_LABELS = {
    "BODY": "Body LA",
    "CLAMP": "Klem LA",
    "CONNECTION": "Koneksi LA",
}


@dataclass(frozen=True, slots=True)
class LaNormalizedResult:
    rule_code: str
    method: str
    component_code: str
    stack_no: int | None
    position_code: str | None
    condition: str
    recommendation: str
    severity: int
    delta_t1_c: float
    delta_t2_c: float
    delta_t1_condition: str
    delta_t2_condition: str
    governing_basis: str
    reference_basis: str = REFERENCE_BASIS


def evaluate_la_normalized(
    component_code: str,
    phase_temperatures_c: Mapping[str, float],
    ambient_temperature_c: float,
    *,
    stack_no: int | None = None,
    position_code: str | None = None,
) -> LaNormalizedResult:
    """Normalisasi satu titik homolog LA antar-fasa dan terhadap ambient."""
    component = component_code.strip().upper()
    if component not in _COMPONENT_LABELS:
        raise ValueError("component_code harus BODY, CLAMP, atau CONNECTION.")

    position = position_code.strip().upper() if position_code else None
    if component == "BODY":
        if stack_no is None or int(stack_no) <= 0:
            raise ValueError("Body LA harus mempunyai stack_no lebih besar dari nol.")
        if position not in {"TOP", "MIDDLE", "BOTTOM"}:
            raise ValueError("Body LA harus mempunyai position_code TOP, MIDDLE, atau BOTTOM.")
        stack_no = int(stack_no)
    elif stack_no is not None and int(stack_no) <= 0:
        raise ValueError("stack_no harus lebih besar dari nol jika diisi.")

    values = [float(value) for value in phase_temperatures_c.values()]
    if len(values) < 2:
        raise ValueError("Normalisasi LA membutuhkan minimal dua nilai suhu fasa.")

    delta_t1_c = max(values) - min(values)
    delta_t2_c = max(values) - float(ambient_temperature_c)
    delta_t1 = classify_similar_component_delta(delta_t1_c)
    delta_t2 = classify_over_ambient_delta(delta_t2_c)
    delta_t1_condition = "Kondisi IV" if delta_t1.severity == 4 else delta_t1.condition

    if delta_t2.severity > delta_t1.severity:
        governing = delta_t2
        condition = delta_t2.condition
        basis = "DELTA_T2_OVER_AMBIENT"
    else:
        governing = delta_t1
        condition = delta_t1_condition
        basis = "DELTA_T1_INTERPHASE"

    if governing.severity == 0:
        recommendation = "Lanjutkan inspeksi rutin."
    elif governing.severity == 1:
        recommendation = "Lakukan investigasi lanjutan."
    elif governing.severity == 2:
        recommendation = "Jadwalkan pemeriksaan dan perbaikan."
    elif governing.severity == 3:
        recommendation = "Lakukan monitoring sampai dilakukan tindak lanjut."
    else:
        recommendation = "Ketidaknormalan mayor; lakukan pemeriksaan dan tindak lanjut segera."

    identity = _COMPONENT_LABELS[component]
    if component == "BODY":
        identity += f" · Stack {stack_no} · {position.title()}"
    return LaNormalizedResult(
        "LA_NORMALIZED_THERMAL",
        f"{identity.upper()} · ANTAR FASA + TERHADAP AMBIENT",
        component,
        stack_no,
        position,
        condition,
        recommendation,
        governing.severity,
        delta_t1_c,
        delta_t2_c,
        delta_t1_condition,
        delta_t2.condition,
        basis,
    )
