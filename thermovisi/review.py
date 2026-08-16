from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

from .excel_parser import ParsedSheet
from .rules_trafo import (
    RULE_SET_CODE,
    RuleResult,
    evaluate_bushing_ambient,
    evaluate_bushing_head,
    evaluate_bushing_interphase,
    evaluate_clamp_conductor,
    evaluate_vertical_gradient,
)


_GRADIENT_EQUIPMENT = {
    "TRF_MAIN_TANK",
    "OLTC_MAIN_TANK",
    "TRF_RADIATOR",
    "TRF_CONSERVATOR",
    "NGR_ACTIVE_PART",
}


def _rounded(value: float | None) -> float | None:
    return None if value is None else round(value, 2)


def _unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _apply_results(row: dict[str, Any], results: list[RuleResult]) -> None:
    if not results:
        return
    governing = max(results, key=lambda result: result.severity)
    actionable = [result for result in results if result.severity > 0]
    recommendations = _unique(result.recommendation for result in (actionable or [governing]))
    row["Rule set"] = RULE_SET_CODE
    row["Kode aturan"] = " · ".join(_unique(result.rule_code for result in results))
    row["Metode analisa"] = " · ".join(_unique(result.method for result in results))
    row["Kondisi"] = governing.condition
    row["Kesimpulan / rekomendasi"] = " ".join(recommendations)
    row["Basis evaluasi"] = governing.evaluation_basis or "DIRECT_TEMPERATURE"
    row["Tingkat perhatian"] = governing.severity


def _temperature_map(measurements: list[Any]) -> dict[str, float]:
    return {
        (measurement.phase_code or "VALUE"): float(measurement.temperature_c)
        for measurement in measurements
        if measurement.temperature_c is not None
    }


def build_sheet_review(
    parsed_sheet: ParsedSheet,
    template_items: list[dict[str, Any]],
    *,
    measurement_current_a: float,
    monthly_peak_current_a: float,
    ambient_temperature_c: float,
) -> list[dict[str, Any]]:
    """Bangun review satu sheet menggunakan THERMOVISI_TRAFO_V1 tanpa menyimpan data."""
    if measurement_current_a < 0 or monthly_peak_current_a < 0:
        raise ValueError("Beban tidak boleh negatif.")
    if measurement_current_a > 0 and monthly_peak_current_a < measurement_current_a:
        raise ValueError("Beban tertinggi tidak boleh lebih kecil dari beban pengukuran.")

    item_by_id = {int(item["template_item_id"]): item for item in template_items}
    measurements_by_item: dict[int, list[Any]] = defaultdict(list)
    for measurement in parsed_sheet.measurements:
        measurements_by_item[measurement.template_item_id].append(measurement)

    ordered_ids = sorted(
        measurements_by_item,
        key=lambda item_id: (
            str(item_by_id[item_id].get("form_section_code") or ""),
            int(item_by_id[item_id].get("sequence_no") or 0),
        ),
    )
    rows: list[dict[str, Any]] = []
    row_index_by_item: dict[int, int] = {}
    temperatures_by_item: dict[int, dict[str, float]] = {}

    for item_id in ordered_ids:
        item = item_by_id[item_id]
        measurements = measurements_by_item[item_id]
        temperatures = _temperature_map(measurements)
        temperatures_by_item[item_id] = temperatures
        phase_r = temperatures.get("R")
        phase_s = temperatures.get("S")
        phase_t = temperatures.get("T")
        single = temperatures.get("VALUE")
        data_statuses = {measurement.data_quality_status for measurement in measurements}
        status = (
            "INVALID" if "INVALID" in data_statuses else "WARNING" if "WARNING" in data_statuses else "VALID"
        )
        role = str(item.get("comparison_role") or "").upper()
        method = "REFERENSI PASANGAN" if role == "CONDUCTOR" else ""

        row_index_by_item[item_id] = len(rows)
        rows.append(
            {
                "No.": int(item.get("sequence_no") or 0),
                "Bagian": item.get("form_section_code"),
                "Peralatan": item.get("raw_equipment_label") or item.get("equipment_group_code"),
                "Titik peralatan yang diperiksa": item.get("raw_point_label"),
                "Suhu R (°C)": _rounded(phase_r),
                "Suhu S (°C)": _rounded(phase_s),
                "Suhu T (°C)": _rounded(phase_t),
                "Suhu (°C)": _rounded(single),
                "ΔT aktual R (°C)": None,
                "ΔT aktual S (°C)": None,
                "ΔT aktual T (°C)": None,
                "ΔT evaluasi R (°C)": None,
                "ΔT evaluasi S (°C)": None,
                "ΔT evaluasi T (°C)": None,
                "ΔT R-S (°C)": None,
                "ΔT S-T (°C)": None,
                "ΔT T-R (°C)": None,
                "ΔT analisa (°C)": None,
                "Suhu maksimum (°C)": None,
                "Kenaikan maks. terhadap lingkungan (°C)": None,
                "Pola gradasi": None,
                "Rule set": None,
                "Kode aturan": None,
                "Basis evaluasi": None,
                "Metode analisa": method,
                "Kondisi": "",
                "Kesimpulan / rekomendasi": "",
                "Tingkat perhatian": 0,
                "Status analisa": "BELUM DIEVALUASI",
                "Status data": status,
            }
        )

    # Bushing: ambil titik terpanas setiap fasa dalam satu kelompok/winding.
    bushing_groups: dict[tuple[Any, ...], list[int]] = defaultdict(list)
    for item_id in ordered_ids:
        item = item_by_id[item_id]
        if item.get("point_code") == "TRF_BUSHING" and not item.get("comparison_group_code"):
            key = (
                item.get("form_section_code"),
                item.get("equipment_group_code"),
                item.get("winding_code"),
                item.get("terminal_voltage_kv"),
            )
            bushing_groups[key].append(item_id)

    for group_items in bushing_groups.values():
        top_ids = [
            item_id
            for item_id in group_items
            if str(item_by_id[item_id].get("position_code") or "").upper() == "TOP"
        ]
        target_id = top_ids[0] if top_ids else group_items[0]
        target_row = rows[row_index_by_item[target_id]]
        all_temperatures = [
            value for item_id in group_items for value in temperatures_by_item[item_id].values()
        ]
        if not all_temperatures:
            target_row["Status analisa"] = "DATA TIDAK LENGKAP"
            continue

        phase_maxima = {
            phase: max(
                temperatures_by_item[item_id][phase]
                for item_id in group_items
                if phase in temperatures_by_item[item_id]
            )
            for phase in ("R", "S", "T")
            if any(phase in temperatures_by_item[item_id] for item_id in group_items)
        }
        results: list[RuleResult] = []
        if len(phase_maxima) >= 2:
            phase_r = phase_maxima.get("R")
            phase_s = phase_maxima.get("S")
            phase_t = phase_maxima.get("T")
            delta_rs = abs(phase_r - phase_s) if phase_r is not None and phase_s is not None else None
            delta_st = abs(phase_s - phase_t) if phase_s is not None and phase_t is not None else None
            delta_tr = abs(phase_t - phase_r) if phase_t is not None and phase_r is not None else None
            interphase = max(
                (value for value in (delta_rs, delta_st, delta_tr) if value is not None), default=0.0
            )
            target_row["ΔT R-S (°C)"] = _rounded(delta_rs)
            target_row["ΔT S-T (°C)"] = _rounded(delta_st)
            target_row["ΔT T-R (°C)"] = _rounded(delta_tr)
            target_row["ΔT analisa (°C)"] = _rounded(interphase)
            results.append(evaluate_bushing_interphase(interphase))

        head_temperatures = [
            value for item_id in top_ids for value in temperatures_by_item[item_id].values()
        ]
        if head_temperatures:
            maximum_head = max(head_temperatures)
            target_row["Suhu maksimum (°C)"] = _rounded(maximum_head)
            results.append(evaluate_bushing_head(maximum_head))

        maximum_temperature = max(all_temperatures)
        maximum_rise = maximum_temperature - ambient_temperature_c
        target_row["Kenaikan maks. terhadap lingkungan (°C)"] = _rounded(maximum_rise)
        results.append(evaluate_bushing_ambient(maximum_temperature, ambient_temperature_c))
        _apply_results(target_row, results)
        target_row["Status analisa"] = "TEREVALUASI"
        for item_id in group_items:
            if item_id != target_id:
                row = rows[row_index_by_item[item_id]]
                row["Metode analisa"] = "DATA PROFIL BUSHING"
                row["Status analisa"] = "TERCAKUP PADA RINGKASAN BUSHING"

    # Pairing eksplisit: comparison_group_code + comparison_role + phase.
    comparison_groups: dict[str, list[int]] = defaultdict(list)
    for item_id in ordered_ids:
        group_code = item_by_id[item_id].get("comparison_group_code")
        role = str(item_by_id[item_id].get("comparison_role") or "").upper()
        if group_code and role in {"CLAMP", "CONDUCTOR"}:
            comparison_groups[str(group_code)].append(item_id)

    for group_code, group_items in comparison_groups.items():
        clamp_ids = [
            item_id for item_id in group_items
            if str(item_by_id[item_id].get("comparison_role") or "").upper() == "CLAMP"
        ]
        conductor_ids = [
            item_id for item_id in group_items
            if str(item_by_id[item_id].get("comparison_role") or "").upper() == "CONDUCTOR"
        ]
        if len(clamp_ids) != 1 or len(conductor_ids) != 1:
            issue = "DUPLICATE_PAIR" if len(clamp_ids) > 1 or len(conductor_ids) > 1 else "INCOMPLETE_PAIR"
            for item_id in group_items:
                row = rows[row_index_by_item[item_id]]
                row["Status analisa"] = issue
                row["Kesimpulan / rekomendasi"] = (
                    f"Pasangan {group_code} harus memiliki tepat satu CLAMP dan satu CONDUCTOR."
                )
            continue

        clamp_id, conductor_id = clamp_ids[0], conductor_ids[0]
        clamp_temperatures = temperatures_by_item[clamp_id]
        conductor_temperatures = temperatures_by_item[conductor_id]
        phase_results: dict[str, RuleResult] = {}
        raw_deltas: dict[str, float] = {}
        for phase in ("R", "S", "T", "VALUE"):
            if phase not in clamp_temperatures or phase not in conductor_temperatures:
                continue
            raw_deltas[phase] = abs(clamp_temperatures[phase] - conductor_temperatures[phase])
            phase_results[phase] = evaluate_clamp_conductor(
                clamp_temperatures[phase],
                conductor_temperatures[phase],
                measurement_current_a=measurement_current_a,
                highest_current_a=monthly_peak_current_a,
            )

        clamp_row = rows[row_index_by_item[clamp_id]]
        conductor_row = rows[row_index_by_item[conductor_id]]
        if not phase_results:
            clamp_row["Status analisa"] = "DATA PASANGAN TIDAK LENGKAP"
            clamp_row["Kesimpulan / rekomendasi"] = (
                f"Nilai CLAMP dan CONDUCTOR pada pasangan {group_code} tidak lengkap."
            )
            continue

        for phase in ("R", "S", "T"):
            clamp_row[f"ΔT aktual {phase} (°C)"] = _rounded(raw_deltas.get(phase))
            result = phase_results.get(phase)
            clamp_row[f"ΔT evaluasi {phase} (°C)"] = _rounded(result.evaluated_value_c if result else None)
        governing = max(phase_results.values(), key=lambda result: result.evaluated_value_c or 0)
        clamp_row["ΔT analisa (°C)"] = _rounded(governing.evaluated_value_c)
        _apply_results(clamp_row, [governing])
        clamp_row["Status analisa"] = "TEREVALUASI"
        conductor_row["Metode analisa"] = "REFERENSI KLEM–KONDUKTOR"
        conductor_row["Status analisa"] = "TERCAKUP PADA PASANGAN"

    # Gradasi hanya untuk subsistem Trafo yang disepakati dalam V1.
    gradient_groups: dict[tuple[Any, ...], dict[str, int]] = defaultdict(dict)
    for item_id in ordered_ids:
        item = item_by_id[item_id]
        equipment = str(item.get("equipment_group_code") or "")
        position = str(item.get("position_code") or "").upper()
        if equipment in _GRADIENT_EQUIPMENT and position in {"TOP", "MIDDLE", "BOTTOM"}:
            key = (item.get("form_section_code"), equipment, item.get("instance_no"))
            gradient_groups[key][position] = item_id

    for (_, equipment, _), position_items in gradient_groups.items():
        if set(position_items) != {"TOP", "MIDDLE", "BOTTOM"}:
            for item_id in position_items.values():
                rows[row_index_by_item[item_id]]["Status analisa"] = "GRADASI TIDAK LENGKAP"
            continue
        values = {
            position: temperatures_by_item[item_id].get("VALUE")
            for position, item_id in position_items.items()
        }
        if any(value is None for value in values.values()):
            for item_id in position_items.values():
                rows[row_index_by_item[item_id]]["Status analisa"] = "GRADASI TIDAK LENGKAP"
            continue
        result = evaluate_vertical_gradient(
            values["TOP"],
            values["MIDDLE"],
            values["BOTTOM"],
            equipment_group_code=equipment,
            measurement_current_a=measurement_current_a,
        )
        top_row = rows[row_index_by_item[position_items["TOP"]]]
        top_row["ΔT analisa (°C)"] = _rounded(result.evaluated_value_c)
        top_row["Pola gradasi"] = result.pattern_code
        _apply_results(top_row, [result])
        top_row["Status analisa"] = "TEREVALUASI"
        for position in ("MIDDLE", "BOTTOM"):
            row = rows[row_index_by_item[position_items[position]]]
            row["Metode analisa"] = "DATA PROFIL GRADASI"
            row["Status analisa"] = "TERCAKUP PADA GRADASI"

    return rows


def _display_temperature(value: Any) -> str:
    if value is None:
        return ""
    return f"{float(value):.1f}".replace(".", ",")


def compact_review_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ringkas kolom teknis menjadi tabel review yang nyaman dibaca operator."""
    compact: list[dict[str, Any]] = []
    previous_equipment: tuple[str, str] | None = None
    for row in rows:
        phases = [
            f"{phase} {_display_temperature(row.get(f'Suhu {phase} (°C)'))}"
            for phase in ("R", "S", "T")
            if row.get(f"Suhu {phase} (°C)") is not None
        ]
        if phases:
            measurement = " | ".join(phases) + " °C"
        elif row.get("Suhu (°C)") is not None:
            measurement = _display_temperature(row.get("Suhu (°C)")) + " °C"
        else:
            measurement = "—"

        analysis_parts: list[str] = []
        evaluated_phases = [
            f"{phase} {_display_temperature(row.get(f'ΔT evaluasi {phase} (°C)'))}"
            for phase in ("R", "S", "T")
            if row.get(f"ΔT evaluasi {phase} (°C)") is not None
        ]
        if evaluated_phases:
            analysis_parts.append("ΔT eval " + " | ".join(evaluated_phases) + " °C")
        elif row.get("ΔT analisa (°C)") is not None:
            analysis_parts.append(
                "ΔT " + _display_temperature(row.get("ΔT analisa (°C)")) + " °C"
            )
        if row.get("Suhu maksimum (°C)") is not None:
            analysis_parts.append(
                "T maks " + _display_temperature(row.get("Suhu maksimum (°C)")) + " °C"
            )
        if row.get("Kenaikan maks. terhadap lingkungan (°C)") is not None:
            analysis_parts.append(
                "ΔT lingkungan "
                + _display_temperature(row.get("Kenaikan maks. terhadap lingkungan (°C)"))
                + " °C"
            )
        if row.get("Pola gradasi"):
            analysis_parts.append("Pola " + str(row["Pola gradasi"]))

        equipment_key = (str(row.get("Bagian") or ""), str(row.get("Peralatan") or ""))
        equipment = "" if equipment_key == previous_equipment else str(row.get("Peralatan") or "")
        previous_equipment = equipment_key
        data_status = str(row.get("Status data") or "")
        compact.append(
            {
                "No.": row.get("No."),
                "Peralatan": equipment,
                "Titik yang diperiksa": row.get("Titik peralatan yang diperiksa"),
                "Pengukuran": measurement,
                "Delta T": " · ".join(analysis_parts) or "—",
                "Kondisi": row.get("Kondisi") or "—",
                "Kesimpulan / Rekomendasi": row.get("Kesimpulan / rekomendasi") or "—",
                "Status Data": data_status or "—",
            }
        )
    return compact


def style_compact_review(frame):
    """Warna status kualitas data agar kesalahan langsung terlihat di review."""
    return frame.style.apply(compact_review_row_style, axis=1)


def compact_review_row_style(row) -> list[str]:
    status = str(row.get("Status Data") or "").upper()
    styles = [""] * len(row)
    target_columns = {"Pengukuran", "Status Data"}
    if status == "INVALID":
        css = "background-color: #FEE2E2; color: #991B1B; font-weight: 600"
    elif status == "WARNING":
        css = "background-color: #FEF3C7; color: #92400E"
    else:
        return styles
    for index, column in enumerate(row.index):
        if column in target_columns:
            styles[index] = css
    return styles
