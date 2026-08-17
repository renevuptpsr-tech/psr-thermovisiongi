from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .rules_neta import classify_over_ambient_delta, classify_similar_component_delta


RULE_SET_CODE = "THERMOVISI_CT_V1"


@dataclass(frozen=True, slots=True)
class CtClampResult:
    rule_code: str
    method: str
    condition: str
    recommendation: str
    severity: int
    raw_delta_c: float
    evaluated_delta_c: float
    evaluation_basis: str


@dataclass(frozen=True, slots=True)
class CtBodyResult:
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


def evaluate_ct_clamp(
    clamp_temperature_c: float,
    conductor_temperature_c: float,
    *,
    measurement_current_a: float,
    highest_current_a: float,
) -> CtClampResult:
    """Evaluasi klem CT dengan koreksi beban; beban nol menjadi observasi ΔT aktual."""
    current = float(measurement_current_a)
    highest = float(highest_current_a)
    if current < 0 or highest < 0:
        raise ValueError("Beban tidak boleh negatif.")
    if current > 0 and highest < current:
        raise ValueError("Beban tertinggi tidak boleh lebih kecil dari beban pengukuran.")

    raw_delta = abs(float(clamp_temperature_c) - float(conductor_temperature_c))
    if current == 0:
        evaluated_delta = raw_delta
        basis = "RAW_DELTA_ZERO_LOAD"
        method = "KLEM CT–KONDUKTOR · ΔT AKTUAL (BEBAN 0 A)"
        limitation = (
            " Evaluasi memakai ΔT aktual tanpa koreksi beban dan tidak mewakili kondisi pada arus maksimum."
        )
    else:
        evaluated_delta = (highest / current) ** 2 * raw_delta
        basis = "LOAD_CORRECTED"
        method = "KLEM CT–KONDUKTOR · KOREKSI BEBAN"
        limitation = ""

    if evaluated_delta < 10:
        condition, severity = "Normal", 0
        recommendation = "Pengukuran berikutnya dilakukan sesuai jadwal."
    elif evaluated_delta < 25:
        condition, severity = "Perlu pengukuran ulang", 1
        recommendation = "Lakukan pengukuran ulang dua minggu lagi."
    elif evaluated_delta < 40:
        condition, severity = "Perlu perbaikan terencana", 2
        recommendation = (
            "Lakukan pengukuran ulang satu minggu lagi dan rencanakan perbaikan paling lambat dua minggu."
        )
    elif evaluated_delta <= 70:
        condition, severity = "Perlu perbaikan segera", 3
        recommendation = (
            "Lakukan pengukuran harian dan perbaikan segera paling lambat tiga hari."
        )
    else:
        condition, severity = "Darurat", 4
        recommendation = "Kondisi darurat; lakukan tindakan segera."

    return CtClampResult(
        "CT_CLAMP_LOAD_CORRECTED",
        method,
        condition,
        recommendation + limitation,
        severity,
        raw_delta,
        evaluated_delta,
        basis,
    )


def evaluate_ct_insulator_housing(
    component_code: str,
    phase_temperatures_c: Mapping[str, float],
    ambient_temperature_c: float,
) -> CtBodyResult:
    """Evaluasi isolator/housing CT secara serentak pada minimal dua fasa."""
    component = component_code.strip().upper()
    if component not in {"INSULATOR", "HOUSING"}:
        raise ValueError("component_code harus INSULATOR atau HOUSING.")
    values = [float(value) for value in phase_temperatures_c.values()]
    if len(values) < 2:
        raise ValueError("Evaluasi isolator/housing CT membutuhkan minimal dua nilai suhu fasa.")

    delta_t1_c = max(values) - min(values)
    delta_t2_c = max(values) - float(ambient_temperature_c)
    delta_t1 = classify_similar_component_delta(delta_t1_c)
    delta_t2 = classify_over_ambient_delta(delta_t2_c)

    if delta_t2.severity > delta_t1.severity:
        governing, basis = delta_t2, "DELTA_T2_OVER_AMBIENT"
    else:
        governing, basis = delta_t1, "DELTA_T1_INTERPHASE"

    if governing.severity == 0:
        condition = "Normal"
        recommendation = "Lanjutkan inspeksi rutin."
    elif governing.severity == 1:
        condition = "Kondisi I"
        recommendation = "Potensi ketidaknormalan; lakukan investigasi lanjutan."
    elif governing.severity == 2:
        condition = "Kondisi II"
        recommendation = "Mengindikasikan defisiensi; jadwalkan perbaikan."
    elif governing.severity == 3:
        condition = "Kondisi III"
        recommendation = "Lakukan pengukuran harian sampai dilakukan perbaikan."
    else:
        condition = "Ketidaknormalan mayor"
        recommendation = "Lakukan perbaikan atau penggantian segera."

    return CtBodyResult(
        "CT_INSULATOR_HOUSING",
        f"{component} CT · ANTAR FASA + TERHADAP AMBIENT",
        component,
        condition,
        recommendation,
        governing.severity,
        delta_t1_c,
        delta_t2_c,
        delta_t1.condition,
        delta_t2.condition,
        basis,
    )
