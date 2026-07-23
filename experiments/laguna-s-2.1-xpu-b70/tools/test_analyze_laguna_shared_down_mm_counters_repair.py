"""CPU-only tests for the sealed-campaign timing-parser repair."""

from __future__ import annotations

import copy
import csv
import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).with_name(
    "analyze_laguna_shared_down_mm_counters_repair.py"
)
SPEC = importlib.util.spec_from_file_location("counter_analysis_repair", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
repair = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(repair)

KERNEL = "gemm_kernel[SIMD16 {24; 1; 1} {128; 4; 1}]"
TIMING_FIELDS = (
    "Kernel",
    "Calls",
    "Time (ns)",
    "Time (%)",
    "Average (ns)",
    "Min (ns)",
    "Max (ns)",
)


def timing_rows() -> list[dict[str, str]]:
    raw = [
        ("zeCommandListAppendMemoryCopy(D2M)[1572864]", 2, 20, 10, 9, 11),
        (KERNEL, 13, 130, 10, 9, 11),
        ("zeCommandListAppendMemoryCopy(M2D)[1572864]", 1, 10, 10, 10, 10),
        ("zeCommandListAppendMemoryCopy(D2M)[49152]", 13, 130, 10, 9, 11),
        ("zeCommandListAppendMemoryCopy(D2M)[4096]", 2, 20, 10, 9, 11),
        ("zeCommandListAppendMemoryCopy(M2D)[4096]", 1, 10, 10, 10, 10),
    ]
    total = sum(row[2] for row in raw)
    return [
        {
            "Kernel": name,
            "Calls": str(calls),
            "Time (ns)": str(time_ns),
            "Time (%)": f"{time_ns * 100.0 / total:.6f}",
            "Average (ns)": str(average),
            "Min (ns)": str(minimum),
            "Max (ns)": str(maximum),
        }
        for name, calls, time_ns, average, minimum, maximum in raw
    ]


def write_timing(
    path: Path,
    rows: list[dict[str, str]] | None = None,
    *,
    reported_total: int = 320,
    property_kernel: str = KERNEL,
    compiled: str = "AOT",
    simd: str = "16",
    argument_count: str = "15",
    spill: str = "0",
) -> Path:
    selected_rows = rows or timing_rows()
    with path.open("w", newline="") as handle:
        handle.write("=== Device Timing Summary ===\n\n")
        handle.write(f"Total Device Time for L0 backend (ns): {reported_total}\n\n")
        writer = csv.DictWriter(handle, fieldnames=TIMING_FIELDS)
        writer.writeheader()
        writer.writerows(selected_rows)
        handle.write("\n=== Kernel Properties ===\n\n")
        property_writer = csv.DictWriter(
            handle,
            fieldnames=(
                "Kernel",
                "Compiled",
                "SIMD",
                "Number of Arguments",
                "SLM Per Work Group",
                "Private Memory Per Thread",
                "Spill Memory Per Thread",
                "Register File Size Per Thread",
            ),
        )
        property_writer.writeheader()
        property_writer.writerow(
            {
                "Kernel": property_kernel,
                "Compiled": compiled,
                "SIMD": simd,
                "Number of Arguments": argument_count,
                "SLM Per Work Group": "0",
                "Private Memory Per Thread": "0",
                "Spill Memory Per Thread": spill,
                "Register File Size Per Thread": "256",
            }
        )
    return path


def parse(path: Path) -> dict[str, object]:
    return repair.parse_timing_properties_repair(
        path,
        expected_kernel_name=KERNEL,
    )


def test_accepts_exact_six_row_schema_and_reordering(tmp_path: Path) -> None:
    result = parse(write_timing(tmp_path / "ordered"))
    assert result["kernel_name"] == KERNEL
    assert result["calls"] == 13
    assert result["reported_total_device_time_ns"] == 320
    rows = list(reversed(timing_rows()))
    result = parse(write_timing(tmp_path / "reordered", rows))
    assert result["timing_row_order"] == [row["Kernel"] for row in rows]


@pytest.mark.parametrize("operation", ("missing", "extra"))
def test_rejects_missing_or_extra_timing_row(
    tmp_path: Path,
    operation: str,
) -> None:
    rows = timing_rows()
    if operation == "missing":
        rows.pop()
    else:
        extra = copy.deepcopy(rows[0])
        extra["Kernel"] = "unexpected_kernel"
        rows.append(extra)
    with pytest.raises(RuntimeError, match="exact selected-GEMM plus copy set"):
        parse(write_timing(tmp_path / operation, rows))


def test_rejects_copy_identity_or_call_count_tamper(tmp_path: Path) -> None:
    rows = timing_rows()
    rows[0]["Calls"] = "3"
    with pytest.raises(RuntimeError, match="Calls drift"):
        parse(write_timing(tmp_path / "calls", rows))
    rows = timing_rows()
    rows[0]["Kernel"] = "zeCommandListAppendMemoryCopy(D2M)[1572865]"
    with pytest.raises(RuntimeError, match="exact selected-GEMM plus copy set"):
        parse(write_timing(tmp_path / "identity", rows))


def test_rejects_blank_kernel_physical_record(tmp_path: Path) -> None:
    path = write_timing(tmp_path / "blank-kernel")
    text = path.read_text().replace(
        "\n=== Kernel Properties ===",
        "\n,1,1,1,1,1,1\n\n=== Kernel Properties ===",
    )
    path.write_text(text)
    with pytest.raises(RuntimeError, match="empty-kernel"):
        parse(path)


@pytest.mark.parametrize("section", ("timing", "properties"))
def test_rejects_extra_named_csv_column(tmp_path: Path, section: str) -> None:
    path = write_timing(tmp_path / f"extra-{section}")
    text = path.read_text()
    fields = repair.TIMING_FIELDS if section == "timing" else repair.PROPERTY_FIELDS
    header = ",".join(fields)
    path.write_text(text.replace(header, f"{header},Unexpected", 1))
    with pytest.raises(RuntimeError, match="header/schema"):
        parse(path)


def test_rejects_reported_total_or_percentage_tamper(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="row sum"):
        parse(write_timing(tmp_path / "total", reported_total=321))
    rows = timing_rows()
    rows[0]["Time (%)"] = "99.0"
    with pytest.raises(RuntimeError, match="percentage"):
        parse(write_timing(tmp_path / "percent", rows))


def test_rejects_gemm_name_or_property_tamper(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="properties must contain"):
        parse(
            write_timing(
                tmp_path / "property-name",
                property_kernel="gemm_kernel[SIMD16 {1; 1; 1} {1; 1; 1}]",
            )
        )
    with pytest.raises(RuntimeError, match="property identity"):
        parse(write_timing(tmp_path / "spill", spill="1"))


def test_repair_contract_preserves_original_logic_and_closes_downstream() -> None:
    contract = repair.expected_parser_contract()
    assert contract["metric_parser"] == "unchanged original analyzer"
    assert contract["campaign_evidence_validator"] == "unchanged original analyzer"
    assert contract["comparison_and_thresholds"] == "unchanged original analyzer"
    assert contract["timing_rows"]["exact_row_count"] == 6
    assert contract["timing_rows"]["no_other_rows"] is True


def test_repair_source_has_no_hardware_or_execution_lane() -> None:
    source = MODULE_PATH.read_text()
    assert "torch" not in source
    assert "xpu-smi" not in source
    assert "unitrace" in source
    assert "run_arm(" not in source
    assert 'counter_reexecution_authorized": False' in source
    assert "sys.dont_write_bytecode" in source
    assert "compile(" in source
    assert "source_bytes" in source
    assert "refuse preloaded local module" in source
    assert "is contract" in source
