from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Iterable

from .ahi import ahi_from_severity
from .rule_router import route_for_item
from .rules_ct import evaluate_ct_clamp, evaluate_ct_insulator_housing
from .rules_cvt_pt import evaluate_cvt_pt_component
from .rules_la import evaluate_la_normalized
from .rules_insulator import evaluate_insulator_neta
from .rules_general import evaluate_general_clamp_conductor, evaluate_general_phase
from .rules_pms import evaluate_pms_blade, evaluate_pms_main_terminal
from .rules_pmt import (
    evaluate_grading_capacitor,
    evaluate_interrupter_chamber,
    evaluate_pmt_clamp_delta,
)


_TRAFO_RULES = {"TRAFO_BUSHING", "TRAFO_CLAMP", "TRAFO_GRADIENT"}
_PAIR_RULES = {"PMT_CLAMP", "PMS_MAIN_TERMINAL", "CT_CLAMP", "GENERAL_CLAMP_CONDUCTOR"}


@dataclass(frozen=True, slots=True)
class EvaluationPatch:
    target_item_id: int
    covered_item_ids: tuple[int, ...]
    values: dict[str, Any]


def _temperatures(measurements: Iterable[Any]) -> dict[str, float]:
    return {
        str(measurement.phase_code or "VALUE").upper(): float(measurement.temperature_c)
        for measurement in measurements
        if measurement.temperature_c is not None
    }


def _result_values(result: Any, rule_set_code: str) -> dict[str, Any]:
    delta_t1 = getattr(result, "delta_t1_c", None)
    delta_t2 = getattr(result, "delta_t2_c", None)
    evaluated = getattr(result, "evaluated_value_c", None)
    if evaluated is None:
        evaluated = getattr(result, "evaluated_delta_c", None)
    if evaluated is None:
        evaluated = delta_t1
    basis = (
        getattr(result, "evaluation_basis", None)
        or getattr(result, "governing_basis", None)
        or "DIRECT_TEMPERATURE"
    )
    ahi = ahi_from_severity(int(result.severity), evaluable=True)
    values = {
        "Rule set": rule_set_code,
        "Kode aturan": result.rule_code,
        "Metode analisa": result.method,
        "Kondisi": result.condition,
        "Kesimpulan / rekomendasi": result.recommendation,
        "Basis evaluasi": basis,
        "Tingkat perhatian": int(result.severity),
        "AHI Thermovisi": ahi.score if ahi else None,
        "Kategori AHI": ahi.label if ahi else None,
        "Basis AHI": rule_set_code if ahi else None,
        "Status analisa": "TEREVALUASI",
        "ΔT analisa (°C)": None if evaluated is None else round(float(evaluated), 2),
    }
    if delta_t2 is not None:
        values["Kenaikan maks. terhadap lingkungan (°C)"] = round(float(delta_t2), 2)
    return values


def _component_for_cvt(item: dict[str, Any]) -> str:
    point = str(item.get("point_code") or "").upper()
    if "INSULATOR" in point:
        return "INSULATOR"
    if "BODY" in point or "HOUSING" in point:
        return "HOUSING"
    if "CLAMP" in point or "CONDUCTOR" in point:
        return "CLAMP_CONDUCTOR"
    raise ValueError(f"Komponen CVT/PT belum dipetakan untuk point_code {point or '-'}.")


def _component_for_la(item: dict[str, Any]) -> str:
    point = str(item.get("point_code") or "").upper()
    if "INSULATOR" in point:
        return "BODY"
    if "CLAMP" in point:
        return "CLAMP"
    return "CONNECTION"


def _phase_result(
    code: str,
    item: dict[str, Any],
    temperatures: dict[str, float],
    ambient_temperature_c: float,
) -> Any:
    if code == "PMT_GRADING_CAPACITOR":
        return evaluate_grading_capacitor(temperatures)
    if code == "PMT_INTERRUPTER":
        return evaluate_interrupter_chamber(temperatures, ambient_temperature_c)
    if code == "PMS_BLADE":
        return evaluate_pms_blade(temperatures, ambient_temperature_c)
    if code == "PMT_INSULATOR":
        return evaluate_insulator_neta("PMT", temperatures, ambient_temperature_c)
    if code == "PMS_INSULATOR":
        return evaluate_insulator_neta("PMS", temperatures, ambient_temperature_c)
    if code == "GENERAL_NETA_PHASE":
        return evaluate_general_phase(temperatures, ambient_temperature_c)
    if code == "CVT_PT_COMPONENT":
        return evaluate_cvt_pt_component(
            _component_for_cvt(item), temperatures, ambient_temperature_c
        )
    if code == "CT_INSULATOR_HOUSING":
        component = "INSULATOR" if "BUSHING" in str(item.get("point_code") or "").upper() else "HOUSING"
        return evaluate_ct_insulator_housing(component, temperatures, ambient_temperature_c)
    if code == "LA_NORMALIZED":
        component = _component_for_la(item)
        position = item.get("position_code")
        stack_no = item.get("instance_no")
        if component == "BODY":
            stack_no = int(stack_no or 1)
        return evaluate_la_normalized(
            component,
            temperatures,
            ambient_temperature_c,
            stack_no=stack_no,
            position_code=position,
        )
    raise ValueError(f"Rule fase belum memiliki evaluator: {code}")


def build_evaluation_patches(
    template_items: list[dict[str, Any]],
    measurements: Iterable[Any],
    *,
    measurement_current_a: float,
    monthly_peak_current_a: float,
    ambient_temperature_c: float,
) -> tuple[list[EvaluationPatch], dict[int, str]]:
    """Evaluate configured non-Trafo rules without writing to the database."""
    items = {int(item["template_item_id"]): item for item in template_items}
    grouped_measurements: dict[int, list[Any]] = defaultdict(list)
    for measurement in measurements:
        grouped_measurements[int(measurement.template_item_id)].append(measurement)
    temperatures = {
        item_id: _temperatures(values) for item_id, values in grouped_measurements.items()
    }

    patches: list[EvaluationPatch] = []
    statuses: dict[int, str] = {}
    pair_groups: dict[tuple[str, str], list[int]] = defaultdict(list)

    for item_id in grouped_measurements:
        item = items[item_id]
        route = route_for_item(item)
        if route is None:
            statuses[item_id] = "RULE_NOT_CONFIGURED"
            continue
        code = route.analysis_rule_code
        if code in _TRAFO_RULES:
            continue
        if code in _PAIR_RULES:
            group = str(item.get("comparison_group_code") or "").strip()
            if not group:
                statuses[item_id] = "INCOMPLETE_PAIR"
            else:
                pair_groups[(code, group)].append(item_id)
            continue
        if len(temperatures.get(item_id, {})) < 2:
            statuses[item_id] = "DATA TIDAK LENGKAP"
            continue
        try:
            result = _phase_result(code, item, temperatures[item_id], ambient_temperature_c)
        except ValueError as exc:
            statuses[item_id] = f"CONFIGURATION_ERROR: {exc}"
            continue
        patches.append(EvaluationPatch(item_id, (), _result_values(result, route.rule_set_code)))

    for (code, _group), item_ids in pair_groups.items():
        clamp_ids = [
            item_id for item_id in item_ids
            if str(items[item_id].get("comparison_role") or "").upper() == "CLAMP"
        ]
        reference_ids = [
            item_id for item_id in item_ids
            if str(items[item_id].get("comparison_role") or "").upper() in {"CONDUCTOR", "MAIN_TERMINAL"}
        ]
        if len(clamp_ids) != 1 or len(reference_ids) != 1:
            for item_id in item_ids:
                statuses[item_id] = "INCOMPLETE_PAIR"
            continue
        clamp_id, reference_id = clamp_ids[0], reference_ids[0]
        common = [phase for phase in ("R", "S", "T", "VALUE") if phase in temperatures[clamp_id] and phase in temperatures[reference_id]]
        if not common:
            statuses[clamp_id] = "DATA PASANGAN TIDAK LENGKAP"
            statuses[reference_id] = "DATA PASANGAN TIDAK LENGKAP"
            continue
        results = []
        for phase in common:
            clamp = temperatures[clamp_id][phase]
            reference = temperatures[reference_id][phase]
            if code == "PMT_CLAMP":
                role = str(items[reference_id].get("comparison_role") or "CONDUCTOR").upper()
                results.append(evaluate_pmt_clamp_delta(clamp, reference, reference_role=role))
            elif code == "PMS_MAIN_TERMINAL":
                results.append(evaluate_pms_main_terminal(clamp, reference, ambient_temperature_c))
            elif code == "CT_CLAMP":
                results.append(
                    evaluate_ct_clamp(
                        clamp,
                        reference,
                        measurement_current_a=measurement_current_a,
                        highest_current_a=monthly_peak_current_a,
                    )
                )
            else:
                results.append(
                    evaluate_general_clamp_conductor(
                        clamp,
                        reference,
                        measurement_current_a=measurement_current_a,
                        highest_current_a=monthly_peak_current_a,
                    )
                )
        governing = max(results, key=lambda result: int(result.severity))
        route = route_for_item(items[clamp_id])
        assert route is not None
        patches.append(
            EvaluationPatch(
                clamp_id,
                (reference_id,),
                _result_values(governing, route.rule_set_code),
            )
        )
    return patches, statuses
