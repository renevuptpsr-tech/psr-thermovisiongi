from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


AHI_LABELS = {
    1: "Very Good",
    2: "Good",
    3: "Fair",
    4: "Poor",
    5: "Critical",
}


@dataclass(frozen=True, slots=True)
class AhiRating:
    score: int
    label: str

    @property
    def display(self) -> str:
        return f"{self.score} — {self.label}"


def ahi_from_severity(severity: int, *, evaluable: bool = True) -> AhiRating | None:
    """Konversi severity rule 0–4 menjadi AHI Thermovisi 1–5."""
    if not evaluable:
        return None
    value = int(severity)
    if value not in range(5):
        raise ValueError("Severity harus berada pada 0 sampai 4.")
    score = value + 1
    return AhiRating(score, AHI_LABELS[score])


def aggregate_ahi(scores: Iterable[int | None]) -> AhiRating | None:
    """Agregasi konservatif: nilai AHI terburuk; None tidak dianggap Critical."""
    valid = [int(score) for score in scores if score is not None]
    if not valid:
        return None
    if any(score not in AHI_LABELS for score in valid):
        raise ValueError("Skor AHI harus berada pada 1 sampai 5.")
    score = max(valid)
    return AhiRating(score, AHI_LABELS[score])
