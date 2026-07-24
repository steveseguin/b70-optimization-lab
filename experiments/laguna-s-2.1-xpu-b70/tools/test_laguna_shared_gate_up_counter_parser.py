"""CPU-only tamper tests for the gate+up unitrace parser."""

from __future__ import annotations

import copy
import csv
import hashlib
import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).with_name("laguna_shared_gate_up_counter_parser.py")
SPEC = importlib.util.spec_from_file_location("gate_up_counter_parser", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
parser = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(parser)

KERNEL = "gemm_kernel[SIMD16 {24; 1; 1} {128; 4; 1}]"


def timing_rows() -> list[dict[str, str]]:
    raw = [
        ("zeCommandListAppendMemoryCopy(D2M)[1572864]", 2, 20, 10, 9, 11),
        (KERNEL, 26, 260, 10, 9, 11),
        ("zeCommandListAppendMemoryCopy(M2D)[1572864]", 2, 20, 10, 9, 11),
        ("zeCommandListAppendMemoryCopy(D2M)[49152]", 1, 10, 10, 10, 10),
        ("zeCommandListAppendMemoryCopy(D2M)[4096]", 26, 260, 10, 9, 11),
        ("zeCommandListAppendMemoryCopy(M2D)[49152]", 1, 10, 10, 10, 10),
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
    total: int = 580,
    property_kernel: str = KERNEL,
    spill: str = "0",
) -> Path:
    with path.open("w", newline="") as handle:
        handle.write("=== Device Timing Summary ===\n\n")
        handle.write(f"Total Device Time for L0 backend (ns): {total}\n\n")
        writer = csv.DictWriter(handle, fieldnames=parser.TIMING_FIELDS)
        writer.writeheader()
        writer.writerows(rows or timing_rows())
        handle.write("\n=== Kernel Properties ===\n\n")
        writer = csv.DictWriter(handle, fieldnames=parser.PROPERTY_FIELDS)
        writer.writeheader()
        writer.writerow(
            {
                "Kernel": property_kernel,
                "Compiled": "AOT",
                "SIMD": "16",
                "Number of Arguments": "15",
                "SLM Per Work Group": "0",
                "Private Memory Per Thread": "0",
                "Spill Memory Per Thread": spill,
                "Register File Size Per Thread": "256",
            }
        )
    return path


def metric_row(index: int) -> dict[str, str]:
    values = {field: "1" for field in parser.METRIC_FIELDS}
    values.update(
        {
            field: "0"
            for field in parser.ZERO_VALIDITY_FIELDS + parser.ZERO_TRAFFIC_FIELDS
        }
    )
    values.update(
        {
            "XVE_ACTIVE[%]": "50",
            "XVE_STALL[%]": "25",
            "XVE_THREADS_OCCUPANCY_ALL[%]": "75",
        }
    )
    return {
        **values,
        "Kernel": KERNEL,
        "GlobalInstanceId": str((index // 2) * 3 + index % 2),
        "SubDeviceId": "0",
        "ReportsCount": "1",
    }


def write_metrics(path: Path, rows: list[dict[str, str]] | None = None) -> Path:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=parser.METRIC_FIELDS)
        writer.writeheader()
        writer.writerows(rows or [metric_row(i) for i in range(26)])
    return path


def test_accepts_unordered_six_rows_and_exact_gate_up_call_count(
    tmp_path: Path,
) -> None:
    result = parser.parse_timing_properties(
        write_timing(tmp_path / "timing"), expected_kernel_name=KERNEL
    )
    assert result["calls"] == 26
    reversed_rows = list(reversed(timing_rows()))
    assert parser.parse_timing_properties(
        write_timing(tmp_path / "reordered", reversed_rows), expected_kernel_name=KERNEL
    )["timing_row_order"] == [row["Kernel"] for row in reversed_rows]


@pytest.mark.parametrize("operation", ("missing", "extra", "duplicate"))
def test_rejects_timing_multiset_tampering(tmp_path: Path, operation: str) -> None:
    rows = timing_rows()
    if operation == "missing":
        rows.pop()
    elif operation == "extra":
        row = copy.deepcopy(rows[0])
        row["Kernel"] = "unexpected"
        rows.append(row)
    else:
        rows.append(copy.deepcopy(rows[0]))
    with pytest.raises(RuntimeError, match="exact selected-GEMM plus copy set"):
        parser.parse_timing_properties(
            write_timing(tmp_path / operation, rows), expected_kernel_name=KERNEL
        )


def test_rejects_timing_header_call_total_percent_and_property_tampering(
    tmp_path: Path,
) -> None:
    rows = timing_rows()
    rows[1]["Calls"] = "13"
    with pytest.raises(RuntimeError, match="Calls drift"):
        parser.parse_timing_properties(
            write_timing(tmp_path / "calls", rows), expected_kernel_name=KERNEL
        )
    with pytest.raises(RuntimeError, match="row sum"):
        parser.parse_timing_properties(
            write_timing(tmp_path / "total", total=451), expected_kernel_name=KERNEL
        )
    rows = timing_rows()
    rows[0]["Time (%)"] = "99"
    with pytest.raises(RuntimeError, match="percentage"):
        parser.parse_timing_properties(
            write_timing(tmp_path / "percent", rows), expected_kernel_name=KERNEL
        )
    with pytest.raises(RuntimeError, match="property identity"):
        parser.parse_timing_properties(
            write_timing(tmp_path / "spill", spill="1"), expected_kernel_name=KERNEL
        )
    path = write_timing(tmp_path / "header")
    path.write_text(path.read_text().replace("Time (ns)", "TimeNs", 1))
    with pytest.raises(RuntimeError, match="header/schema"):
        parser.parse_timing_properties(path, expected_kernel_name=KERNEL)


def test_pair_aware_metrics_discard_first_two_pairs_and_keep_22_samples(
    tmp_path: Path,
) -> None:
    result = parser.parse_metrics(write_metrics(tmp_path / "metrics"))
    assert result["kernel_name"] == KERNEL
    assert result["discarded_pair_indexes"] == [0, 1]
    assert result["analyzed_pairs"] == 11
    assert result["analyzed_gemm_samples"] == 22
    assert [pair["pair_index"] for pair in result["retained_pairs"]] == list(
        range(2, 13)
    )
    assert result["retained_pairs"][0]["gate"]["GlobalInstanceId"] == "6"
    assert result["retained_pairs"][0]["up"]["GlobalInstanceId"] == "7"


def test_rejects_nonconsecutive_gate_up_query_ids(tmp_path: Path) -> None:
    rows = [metric_row(i) for i in range(26)]
    rows[7]["GlobalInstanceId"] = "99"
    for index in range(8, 26):
        rows[index]["GlobalInstanceId"] = str(100 + index)
    with pytest.raises(RuntimeError, match="consecutive within each selected pair"):
        parser.parse_metrics(write_metrics(tmp_path / "nonconsecutive", rows))


def test_rejects_wrong_eviction_gap_between_pairs(tmp_path: Path) -> None:
    rows = [metric_row(i) for i in range(26)]
    rows[2]["GlobalInstanceId"] = "4"
    rows[3]["GlobalInstanceId"] = "5"
    with pytest.raises(RuntimeError, match="exactly one eviction gap"):
        parser.parse_metrics(write_metrics(tmp_path / "eviction-gap", rows))


def test_metrics_require_the_complete_sealed_computebasic_header(
    tmp_path: Path,
) -> None:
    path = write_metrics(tmp_path / "full-header")
    assert tuple(path.read_text().splitlines()[0].split(",")) == parser.METRIC_FIELDS
    assert len(parser.METRIC_FIELDS) > 80
    assert (
        hashlib.sha256(",".join(parser.METRIC_FIELDS).encode()).hexdigest()
        == parser.METRIC_HEADER_SHA256
    )
    parser.parse_metrics(path, expected_kernel_name=KERNEL)


@pytest.mark.parametrize(
    "tamper", ("missing", "extra", "duplicate-id", "kernel", "validity", "header")
)
def test_rejects_metric_row_and_schema_tampering(tmp_path: Path, tamper: str) -> None:
    rows = [metric_row(i) for i in range(26)]
    if tamper == "missing":
        rows.pop()
    elif tamper == "extra":
        rows.append(metric_row(26))
    elif tamper == "duplicate-id":
        rows[-1]["GlobalInstanceId"] = "24"
    elif tamper == "kernel":
        rows[-1]["Kernel"] = "other"
    elif tamper == "validity":
        rows[-1]["ReportLost"] = "1"
    path = write_metrics(tmp_path / tamper, rows)
    if tamper == "header":
        path.write_text(path.read_text().replace("GpuTime[ns]", "GpuTimeNs", 1))
    with pytest.raises(RuntimeError):
        parser.parse_metrics(path, expected_kernel_name=KERNEL)


def test_parser_is_cpu_only_and_does_not_offer_execution_or_write_paths() -> None:
    source = MODULE_PATH.read_text()
    assert "import subprocess" not in source
    assert "import torch" not in source
    assert "xpu-smi" not in source
    assert ".write_text" not in source
