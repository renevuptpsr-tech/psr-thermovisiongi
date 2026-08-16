from __future__ import annotations

from dataclasses import dataclass


RULE_SET_CODE = "THERMOVISI_TRAFO_V1"
DEFAULT_GRADIENT_TOLERANCE_C = 1.0


@dataclass(frozen=True, slots=True)
class RuleResult:
    rule_code: str
    method: str
    condition: str
    recommendation: str
    severity: int
    evaluated_value_c: float | None = None
    evaluation_basis: str | None = None
    pattern_code: str | None = None


def evaluate_bushing_interphase(delta_c: float) -> RuleResult:
    """Evaluasi selisih terbesar suhu bushing antarfasa."""
    if delta_c < 0:
        raise ValueError("Delta antarfasa tidak boleh negatif.")
    if delta_c < 4:
        return RuleResult(
            "BUSHING_INTERPHASE",
            "BUSHING · PERBANDINGAN ANTAR FASA",
            "Normal",
            "Tidak ada tindakan; lanjutkan inspeksi rutin.",
            0,
            delta_c,
        )
    if delta_c < 16:
        return RuleResult(
            "BUSHING_INTERPHASE",
            "BUSHING · PERBANDINGAN ANTAR FASA",
            "Defisiensi",
            "Jadwalkan pemeriksaan dan perbaikan.",
            2,
            delta_c,
        )
    return RuleResult(
        "BUSHING_INTERPHASE",
        "BUSHING · PERBANDINGAN ANTAR FASA",
        "Ketidaknormalan mayor",
        "Lakukan pemeriksaan dan perbaikan segera.",
        3,
        delta_c,
    )


def evaluate_bushing_head(maximum_temperature_c: float) -> RuleResult:
    """Batas SKDIR bersifat ketat: baru memicu ketika suhu > 90 °C."""
    if maximum_temperature_c > 90:
        return RuleResult(
            "BUSHING_HEAD_MAX",
            "BUSHING · SUHU MAKSIMUM KEPALA",
            "Tidak normal",
            "Lakukan investigasi penyebab.",
            2,
            maximum_temperature_c,
        )
    return RuleResult(
        "BUSHING_HEAD_MAX",
        "BUSHING · SUHU MAKSIMUM KEPALA",
        "Normal",
        "Suhu maksimum kepala bushing tidak melebihi 90 °C.",
        0,
        maximum_temperature_c,
    )


def evaluate_bushing_ambient(temperature_c: float, ambient_temperature_c: float) -> RuleResult:
    """Nilai yang dinilai adalah kenaikan suhu, bukan nilai absolut."""
    rise_c = temperature_c - ambient_temperature_c
    if rise_c >= 35:
        return RuleResult(
            "BUSHING_AMBIENT_RISE",
            "BUSHING · KENAIKAN TERHADAP LINGKUNGAN",
            "Tidak normal",
            "Lakukan investigasi penyebab.",
            2,
            rise_c,
        )
    return RuleResult(
        "BUSHING_AMBIENT_RISE",
        "BUSHING · KENAIKAN TERHADAP LINGKUNGAN",
        "Normal",
        "Kenaikan suhu terhadap lingkungan masih di bawah 35 °C.",
        0,
        rise_c,
    )


def evaluate_clamp_conductor(
    clamp_temperature_c: float,
    conductor_temperature_c: float,
    *,
    measurement_current_a: float,
    highest_current_a: float,
) -> RuleResult:
    """Evaluasi klem; pada beban nol gunakan delta aktual tanpa pembagian."""
    if measurement_current_a < 0 or highest_current_a < 0:
        raise ValueError("Beban tidak boleh negatif.")
    if measurement_current_a > 0 and highest_current_a < measurement_current_a:
        raise ValueError("Beban tertinggi tidak boleh lebih kecil dari beban pengukuran.")

    raw_delta = abs(clamp_temperature_c - conductor_temperature_c)
    if measurement_current_a == 0:
        evaluated_delta = raw_delta
        basis = "RAW_DELTA_ZERO_LOAD"
        method = "KLEM–KONDUKTOR · ΔT AKTUAL (BEBAN 0 A)"
        limited_note = (
            " Evaluasi menggunakan ΔT aktual tanpa koreksi beban dan tidak merepresentasikan "
            "kondisi termal pada beban maksimum."
        )
    else:
        evaluated_delta = (highest_current_a / measurement_current_a) ** 2 * raw_delta
        basis = "LOAD_CORRECTED"
        method = "KLEM–KONDUKTOR · KOREKSI BEBAN"
        limited_note = ""

    if evaluated_delta < 10:
        condition = "Normal"
        recommendation = "Pengukuran berikutnya dilakukan sesuai jadwal."
        severity = 0
    elif evaluated_delta < 25:
        condition = "Perlu pemantauan"
        recommendation = "Lakukan pengukuran ulang satu bulan lagi."
        severity = 1
    elif evaluated_delta < 40:
        condition = "Perlu perbaikan terencana"
        recommendation = "Rencanakan pekerjaan perbaikan."
        severity = 2
    elif evaluated_delta <= 70:
        condition = "Perlu perbaikan segera"
        recommendation = "Lakukan perbaikan segera."
        severity = 3
    else:
        condition = "Darurat"
        recommendation = "Kondisi darurat; lakukan tindakan segera."
        severity = 4

    return RuleResult(
        "CLAMP_CONDUCTOR_DELTA",
        method,
        condition,
        recommendation + limited_note,
        severity,
        evaluated_delta,
        basis,
    )


_GRADIENT_RECOMMENDATIONS = {
    "TRF_MAIN_TANK": "Lakukan Uji DGA.",
    "OLTC_MAIN_TANK": "Lakukan Uji DGA dan review desain/operasi OLTC.",
    "TRF_RADIATOR": "Periksa kebersihan sirip, valve radiator, dan lakukan venting.",
    "TRF_CONSERVATOR": "Periksa Oil Level Indicator dan rubber bag.",
    "NGR_ACTIVE_PART": "Lakukan pemeriksaan elemen NGR.",
}


def evaluate_vertical_gradient(
    top_c: float,
    middle_c: float,
    bottom_c: float,
    *,
    equipment_group_code: str,
    measurement_current_a: float,
    tolerance_c: float = DEFAULT_GRADIENT_TOLERANCE_C,
) -> RuleResult:
    """Karakterisasi pola suhu vertikal Atas–Tengah–Bawah."""
    if tolerance_c < 0:
        raise ValueError("Toleransi gradien tidak boleh negatif.")
    if measurement_current_a < 0:
        raise ValueError("Beban tidak boleh negatif.")

    values = (top_c, middle_c, bottom_c)
    spread = max(values) - min(values)
    if spread <= tolerance_c:
        pattern = "UNIFORM"
    elif top_c >= middle_c - tolerance_c and middle_c >= bottom_c - tolerance_c:
        pattern = "TOP_TO_BOTTOM_DESCENDING"
    elif middle_c > top_c + tolerance_c and middle_c > bottom_c + tolerance_c:
        pattern = "MIDDLE_HOTSPOT"
    elif bottom_c > top_c + tolerance_c and bottom_c > middle_c + tolerance_c:
        pattern = "BOTTOM_HOTSPOT"
    elif top_c > middle_c + tolerance_c and bottom_c > middle_c + tolerance_c:
        pattern = "MIDDLE_COLDSPOT"
    else:
        pattern = "IRREGULAR"

    basis = "VERTICAL_THREE_POINT"
    if measurement_current_a == 0:
        return RuleResult(
            "VERTICAL_GRADIENT",
            "GRADASI SUHU ATAS–TENGAH–BAWAH",
            "Observasi tanpa beban",
            "Pola tetap dicatat, tetapi tidak merepresentasikan kondisi termal saat operasi.",
            1,
            spread,
            "OBSERVATION_ONLY_ZERO_LOAD",
            pattern,
        )
    if pattern == "TOP_TO_BOTTOM_DESCENDING":
        return RuleResult(
            "VERTICAL_GRADIENT",
            "GRADASI SUHU ATAS–TENGAH–BAWAH",
            "Gradasi normal",
            "Tidak ada tindakan; lanjutkan inspeksi rutin.",
            0,
            spread,
            basis,
            pattern,
        )
    if pattern == "UNIFORM":
        return RuleResult(
            "VERTICAL_GRADIENT",
            "GRADASI SUHU ATAS–TENGAH–BAWAH",
            "Perlu review",
            "Pola relatif seragam; verifikasi kondisi operasi dan citra termal.",
            1,
            spread,
            basis,
            pattern,
        )
    return RuleResult(
        "VERTICAL_GRADIENT",
        "GRADASI SUHU ATAS–TENGAH–BAWAH",
        "Tidak normal",
        _GRADIENT_RECOMMENDATIONS.get(
            equipment_group_code,
            "Lakukan pemeriksaan lanjutan sesuai jenis peralatan.",
        ),
        2,
        spread,
        basis,
        pattern,
    )

