from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class AnalysisRoute:
    analysis_rule_code: str
    rule_set_code: str
    grouping_mode: str


_ROUTES = {
    "TRAFO_BUSHING": AnalysisRoute("TRAFO_BUSHING", "THERMOVISI_TRAFO_V1", "PROFILE_GROUP"),
    "TRAFO_CLAMP": AnalysisRoute("TRAFO_CLAMP", "THERMOVISI_TRAFO_V1", "COMPARISON_PAIR"),
    "TRAFO_GRADIENT": AnalysisRoute("TRAFO_GRADIENT", "THERMOVISI_TRAFO_V1", "VERTICAL_PROFILE"),
    "PMT_CLAMP": AnalysisRoute("PMT_CLAMP", "THERMOVISI_PMT_V1", "COMPARISON_PAIR"),
    "PMT_INTERRUPTER": AnalysisRoute("PMT_INTERRUPTER", "THERMOVISI_PMT_V1", "PHASE_GROUP"),
    "PMT_GRADING_CAPACITOR": AnalysisRoute("PMT_GRADING_CAPACITOR", "THERMOVISI_PMT_V1", "PHASE_GROUP"),
    "PMT_INSULATOR": AnalysisRoute("PMT_INSULATOR", "THERMOVISI_PMT_V1", "PHASE_GROUP"),
    "PMS_BLADE": AnalysisRoute("PMS_BLADE", "THERMOVISI_PMS_V1", "PHASE_GROUP"),
    "PMS_MAIN_TERMINAL": AnalysisRoute("PMS_MAIN_TERMINAL", "THERMOVISI_PMS_V1", "COMPARISON_PAIR"),
    "PMS_INSULATOR": AnalysisRoute("PMS_INSULATOR", "THERMOVISI_PMS_V1", "PHASE_GROUP"),
    "CVT_PT_COMPONENT": AnalysisRoute("CVT_PT_COMPONENT", "THERMOVISI_CVT_PT_V1", "PHASE_GROUP"),
    "CT_CLAMP": AnalysisRoute("CT_CLAMP", "THERMOVISI_CT_V1", "COMPARISON_PAIR"),
    "CT_INSULATOR_HOUSING": AnalysisRoute("CT_INSULATOR_HOUSING", "THERMOVISI_CT_V1", "PHASE_GROUP"),
    "LA_NORMALIZED": AnalysisRoute("LA_NORMALIZED", "THERMOVISI_LA_NORMALIZED_V1", "HOMOLOGOUS_PHASE_GROUP"),
}


def supported_analysis_rule_codes() -> tuple[str, ...]:
    return tuple(_ROUTES)


def route_for_item(item: dict[str, Any]) -> AnalysisRoute | None:
    raw = item.get("analysis_rule_code")
    if raw is None or not str(raw).strip():
        return None
    code = str(raw).strip().upper()
    try:
        return _ROUTES[code]
    except KeyError as exc:
        raise ValueError(f"analysis_rule_code tidak didukung: {code}") from exc


def validate_template_rule_configuration(
    template_items: list[dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    for item in template_items:
        try:
            route_for_item(item)
        except ValueError as exc:
            errors.append(
                f"Template item {item.get('template_item_id')}: {exc}"
            )
    return errors
