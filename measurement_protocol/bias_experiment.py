from __future__ import annotations

from typing import Any, Callable

import json

from measurement_protocol.psf_bias_protocol import (
    MEASUREMENT_EXTRACTION_MODES,
    MEASUREMENT_PIPELINE_MODES,
)


def build_measurement_protocol_package(
    *,
    representative_cases: list[dict[str, Any]],
    run_case: Callable[..., dict[str, Any]],
    compare_measurement_snapshots: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]],
    full_na_mode: str,
    low_na_mode: str,
    asymptotic_mode: str,
    bridge_mode: str,
) -> tuple[dict[str, Any], str]:
    package = {
        "cases": [],
        "measurement_extraction_modes": list(MEASUREMENT_EXTRACTION_MODES),
        "measurement_pipeline_modes": list(MEASUREMENT_PIPELINE_MODES),
    }
    md_sections = [
        "# Round 6p1 Measurement-Protocol Bias",
        "",
        "These summaries now compare two measurement-layer routes on top of the solver stack:",
        "",
        "- `solver_output_peak_slice_adapter`: direct measurement on reconstructed solver output.",
        "- `fd_oct_reconstruction`: minimal FD-OCT interferogram + k-linearization + IFFT reconstruction built from solver spectral sample-arm fields.",
        "",
        "This is still not a full measurement-grade OCT simulator, but the FD-OCT route is closer to the intended measurement chain than direct peak-slice extraction alone.",
        "",
    ]
    columns = [
        ("mode", "mode"),
        ("measured_lateral_peak_x_um", "measured_lateral_peak_x_um"),
        ("measured_lateral_fwhm_um", "measured_lateral_fwhm_um"),
        ("measured_axial_fwhm_opd_um", "measured_axial_fwhm_opd_um"),
        ("measured_psr_db", "measured_psr_db"),
        ("measured_psr_definition", "measured_psr_definition"),
        ("measured_sidelobe_to_main_db", "measured_sidelobe_to_main_db"),
        ("measured_main_to_sidelobe_rejection_db", "measured_main_to_sidelobe_rejection_db"),
        ("raw_peak_intensity", "raw_peak_intensity"),
        ("measured_peak_shift_um_vs_bridge", "measured_peak_shift_um_vs_bridge"),
        ("measured_lateral_width_bias_um_vs_bridge", "measured_lateral_width_bias_um_vs_bridge"),
        ("measured_axial_width_bias_um_vs_bridge", "measured_axial_width_bias_um_vs_bridge"),
        ("measured_sidelobe_distortion_vs_bridge", "measured_sidelobe_distortion_vs_bridge"),
    ]

    def _format_float(value: float):
        return f"{float(value):.6g}"

    def _markdown_table(rows: list[dict], columns: list[tuple[str, str]]):
        header = "| " + " | ".join(label for _, label in columns) + " |"
        separator = "| " + " | ".join("---" for _ in columns) + " |"
        lines = [header, separator]
        for row in rows:
            values = []
            for key, _label in columns:
                value = row[key]
                if isinstance(value, float):
                    values.append(_format_float(value))
                else:
                    values.append(str(value))
            lines.append("| " + " | ".join(values) + " |")
        return "\n".join(lines)

    for case_definition in representative_cases:
        bridge = run_case(case_definition, mode=bridge_mode)
        full_na = run_case(case_definition, mode=full_na_mode)
        low_na = run_case(case_definition, mode=low_na_mode)
        asymptotic = run_case(case_definition, mode=asymptotic_mode)
        results = (full_na, bridge, low_na, asymptotic)
        pipeline_mode_rows: dict[str, dict[str, list[dict[str, Any]]]] = {}
        pipeline_failures: dict[str, str] = {}
        for pipeline_mode in MEASUREMENT_PIPELINE_MODES:
            mode_rows: dict[str, list[dict[str, Any]]] = {}
            try:
                for extraction_mode in MEASUREMENT_EXTRACTION_MODES:
                    rows = []
                    for result in results:
                        measured = compare_measurement_snapshots(
                            result,
                            bridge,
                            extraction_mode=extraction_mode,
                            pipeline_mode=pipeline_mode,
                        )
                        row = {
                            "mode": result["mode"],
                            "measurement_pipeline_mode": pipeline_mode,
                            "measurement_extraction_mode": extraction_mode,
                            "measured_lateral_peak_x_um": measured["candidate_snapshot"]["measured_lateral_peak_x_um"],
                            "measured_lateral_fwhm_um": measured["candidate_snapshot"]["measured_lateral_fwhm_um"],
                            "measured_axial_fwhm_opd_um": measured["candidate_snapshot"]["measured_axial_fwhm_opd_um"],
                            "measured_psr_db": measured["candidate_snapshot"]["measured_psr_db"],
                            "measured_psr_definition": measured["candidate_snapshot"].get(
                                "measured_psr_definition",
                                "main_to_sidelobe_rejection_db",
                            ),
                            "measured_sidelobe_to_main_db": measured["candidate_snapshot"].get(
                                "measured_sidelobe_to_main_db",
                                -float(measured["candidate_snapshot"]["measured_psr_db"]),
                            ),
                            "measured_main_to_sidelobe_rejection_db": measured["candidate_snapshot"].get(
                                "measured_main_to_sidelobe_rejection_db",
                                float(measured["candidate_snapshot"]["measured_psr_db"]),
                            ),
                            "raw_peak_intensity": measured["candidate_snapshot"]["raw_peak_intensity"],
                            "fd_oct_k_axis_kind": measured["candidate_snapshot"].get("fd_oct_k_axis_kind"),
                            "fd_oct_depth_convention": measured["candidate_snapshot"].get("fd_oct_depth_convention"),
                            "fd_oct_medium_index_policy": measured["candidate_snapshot"].get("fd_oct_medium_index_policy"),
                            "fd_oct_reference_n_medium": measured["candidate_snapshot"].get("fd_oct_reference_n_medium"),
                            "fd_oct_reference_delay_opd_um": measured["candidate_snapshot"].get("fd_oct_reference_delay_opd_um"),
                            "fd_oct_reference_arm_policy": measured["candidate_snapshot"].get("fd_oct_reference_arm_policy"),
                            "measured_peak_shift_um_vs_bridge": measured["measured_peak_shift_um"],
                            "measured_lateral_width_bias_um_vs_bridge": measured["measured_lateral_width_bias_um"],
                            "measured_axial_width_bias_um_vs_bridge": measured["measured_axial_width_bias_um"],
                            "measured_sidelobe_distortion_vs_bridge": measured["measured_sidelobe_distortion"],
                            "extraction_plane_opd_um": measured["candidate_snapshot"]["extraction_plane_opd_um"],
                        }
                        rows.append(row)
                    mode_rows[extraction_mode] = rows
            except Exception as exc:
                pipeline_failures[pipeline_mode] = str(exc)
                continue
            pipeline_mode_rows[pipeline_mode] = mode_rows
        default_pipeline_mode = (
            "fd_oct_reconstruction"
            if "fd_oct_reconstruction" in pipeline_mode_rows
            else "solver_output_peak_slice_adapter"
        )
        default_comparison_modes = pipeline_mode_rows.get(default_pipeline_mode, {})
        package["cases"].append(
            {
                "name": case_definition["name"],
                "description": case_definition["description"],
                "measurement_pipeline_modes": list(pipeline_mode_rows.keys()),
                "pipeline_comparison_modes": pipeline_mode_rows,
                "comparison_modes": default_comparison_modes,
                "default_measurement_pipeline_mode": default_pipeline_mode,
                "default_comparison_mode": "self_peak",
                "measurement_report_schema_version": "pipeline_and_comparison_modes",
                "bridge_reference_mode": bridge_mode,
                "pipeline_failures": pipeline_failures,
            }
        )
        md_sections.extend(
            [
                f"## {case_definition['name']}",
                case_definition["description"],
                "",
            ]
        )
        for pipeline_mode, extraction_mode_rows in pipeline_mode_rows.items():
            md_sections.extend(
                [
                    f"### measurement_pipeline_mode = {pipeline_mode}",
                    "",
                ]
            )
            for extraction_mode in MEASUREMENT_EXTRACTION_MODES:
                mode_columns = columns + [("extraction_plane_opd_um", "extraction_plane_opd_um")]
                md_sections.extend(
                    [
                        f"#### extraction_mode = {extraction_mode}",
                        "",
                        _markdown_table(extraction_mode_rows[extraction_mode], mode_columns),
                        "",
                    ]
                )
        if pipeline_failures:
            md_sections.extend(
                [
                    "### unsupported measurement pipeline modes",
                    "",
                    "```json",
                    json.dumps(pipeline_failures, indent=2),
                    "```",
                    "",
                ]
            )
    return package, "\n".join(md_sections)


__all__ = ["build_measurement_protocol_package"]
