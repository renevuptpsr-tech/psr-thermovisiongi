from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class NetaCondition:
    condition: str
    recommendation: str
    severity: int


def classify_similar_component_delta(delta_c: float) -> NetaCondition:
    """ΔT antar-komponen serupa/antar-fasa, dibuat kontinu untuk nilai desimal."""
    if delta_c < 0:
        raise ValueError("Delta suhu tidak boleh negatif.")
    if delta_c < 1:
        return NetaCondition("Normal", "Lanjutkan inspeksi rutin.", 0)
    if delta_c < 4:
        return NetaCondition(
            "Kondisi I", "Dimungkinkan ada ketidaknormalan; lakukan investigasi lanjutan.", 1
        )
    if delta_c <= 15:
        return NetaCondition(
            "Kondisi II", "Mengindikasikan adanya defisiensi; jadwalkan perbaikan.", 2
        )
    return NetaCondition(
        "Kondisi III", "Ketidaknormalan mayor; lakukan perbaikan segera.", 4
    )


def classify_over_ambient_delta(delta_c: float) -> NetaCondition:
    """ΔT di atas suhu lingkungan menurut kategori NETA MTS-1997."""
    if delta_c < 1:
        return NetaCondition("Normal", "Lanjutkan inspeksi rutin.", 0)
    if delta_c < 11:
        return NetaCondition(
            "Kondisi I", "Dimungkinkan ada ketidaknormalan; lakukan investigasi lanjutan.", 1
        )
    if delta_c < 21:
        return NetaCondition(
            "Kondisi II", "Mengindikasikan adanya defisiensi; jadwalkan perbaikan.", 2
        )
    if delta_c <= 40:
        return NetaCondition(
            "Kondisi III", "Lakukan monitoring kontinu sampai dilakukan perbaikan.", 3
        )
    return NetaCondition(
        "Kondisi IV", "Ketidaknormalan mayor; lakukan perbaikan segera.", 4
    )
