from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .ahi import aggregate_ahi


_COVERED_ANALYSIS = {
    "TEREVALUASI",
    "TERCAKUP PADA PASANGAN",
    "TERCAKUP PADA GRADASI",
    "TERCAKUP PADA RINGKASAN BUSHING",
}
_INCOMPLETE_ANALYSIS = {
    "DATA TIDAK LENGKAP",
    "DATA PASANGAN TIDAK LENGKAP",
    "GRADASI TIDAK LENGKAP",
}
_EXEMPT_DATA = {"NOT_MEASURED", "NOT_APPLICABLE"}


@dataclass(frozen=True, slots=True)
class BayReviewValidation:
    total_rows: int
    evaluated_rows: int
    not_measured_rows: int
    not_applicable_rows: int
    invalid_rows: int
    incomplete_rows: int
    blocking_rows: int
    attention_rows: int
    worst_ahi_score: int | None
    worst_ahi_label: str | None
    worst_condition: str | None
    accepted_incomplete: bool
    blocking_messages: tuple[str, ...]

    @property
    def ready(self) -> bool:
        return (
            self.total_rows > 0
            and self.invalid_rows == 0
            and self.blocking_rows == 0
            and (self.incomplete_rows == 0 or self.accepted_incomplete)
        )

    @property
    def status_label(self) -> str:
        if self.ready:
            return "SIAP DISIMPAN"
        if self.invalid_rows or self.blocking_rows:
            return "DIBLOKIR"
        if self.incomplete_rows:
            return "PERLU KONFIRMASI"
        return "BELUM SIAP"


def validate_bay_review(
    rows: list[dict[str, Any]],
    *,
    accept_incomplete: bool = False,
) -> BayReviewValidation:
    invalid = incomplete = blocking = evaluated = 0
    not_measured = not_applicable = attention = 0
    messages: list[str] = []

    for row in rows:
        data_status = str(row.get("Status data") or "").upper()
        analysis_status = str(row.get("Status analisa") or "").upper()
        if data_status == "INVALID":
            invalid += 1
            continue
        if data_status == "NOT_MEASURED":
            not_measured += 1
            continue
        if data_status == "NOT_APPLICABLE":
            not_applicable += 1
            continue
        if analysis_status in _COVERED_ANALYSIS:
            evaluated += 1
        elif analysis_status in _INCOMPLETE_ANALYSIS:
            incomplete += 1
        else:
            blocking += 1
            point = row.get("Titik peralatan yang diperiksa") or "Titik tanpa nama"
            messages.append(f"{point}: {analysis_status or 'STATUS ANALISA KOSONG'}")
        if int(row.get("Tingkat perhatian") or 0) > 0:
            attention += 1

    ahi = aggregate_ahi(row.get("AHI Thermovisi") for row in rows)
    governing_rows = sorted(
        rows,
        key=lambda row: int(row.get("Tingkat perhatian") or 0),
        reverse=True,
    )
    worst_condition = next(
        (str(row.get("Kondisi")) for row in governing_rows if row.get("Kondisi")),
        None,
    )
    return BayReviewValidation(
        total_rows=len(rows),
        evaluated_rows=evaluated,
        not_measured_rows=not_measured,
        not_applicable_rows=not_applicable,
        invalid_rows=invalid,
        incomplete_rows=incomplete,
        blocking_rows=blocking,
        attention_rows=attention,
        worst_ahi_score=ahi.score if ahi else None,
        worst_ahi_label=ahi.label if ahi else None,
        worst_condition=worst_condition,
        accepted_incomplete=accept_incomplete,
        blocking_messages=tuple(messages),
    )


def validation_summary_row(
    bay_name: str,
    validation: BayReviewValidation,
) -> dict[str, Any]:
    ahi = (
        f"{validation.worst_ahi_score} — {validation.worst_ahi_label}"
        if validation.worst_ahi_score is not None
        else "—"
    )
    return {
        "Bay": bay_name,
        "Titik": validation.total_rows,
        "Tidak diukur": validation.not_measured_rows,
        "Tidak lengkap": validation.incomplete_rows,
        "Invalid": validation.invalid_rows,
        "AHI terburuk": ahi,
        "Kondisi terburuk": validation.worst_condition or "—",
        "Kesiapan": validation.status_label,
    }
