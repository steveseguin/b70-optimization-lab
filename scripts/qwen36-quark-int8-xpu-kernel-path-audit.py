#!/usr/bin/env python3
"""Audit the current Qwen3.6 Quark W8A8 INT8 XPU MoE dispatch path.

This is CPU/static by default. It does not launch the model and it does not
allocate XPU tensors. The goal is to make the current kernel path and the next
no-quality-loss replacement points reproducible in the tracking repo.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_MODEL_CONFIG = (
    "/mnt/fast-ai/llm-cache/hf/models--nameistoken--"
    "Qwen3.6-35B-A3B-Quark-W8A8-INT8/snapshots/"
    "cced56592e8c8935f8220836b4baa04dfd389118/config.json"
)
DEFAULT_VLLM_ROOT = "/home/steve/src/vllm"
DEFAULT_XPU_KERNELS_ROOT = "/home/steve/src/vllm-xpu-kernels"
DEFAULT_ENDPOINT_RE = r"vllm serve .*Qwen3.6-35B-A3B-Quark-W8A8-INT8.*--port 18080"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def run(cmd: list[str], *, cwd: Path | None = None, timeout: int = 20) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
        return {
            "cmd": cmd,
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
    except Exception as exc:
        return {"cmd": cmd, "error": repr(exc), "stdout": "", "stderr": ""}


def git_info(root: Path) -> dict[str, Any]:
    head = run(["git", "rev-parse", "--short", "HEAD"], cwd=root)
    branch = run(["git", "branch", "--show-current"], cwd=root)
    status = run(["git", "status", "--short"], cwd=root)
    return {
        "root": str(root),
        "head": head["stdout"].strip(),
        "branch": branch["stdout"].strip(),
        "dirty_entries": [line for line in status["stdout"].splitlines() if line],
    }


def load_model_shape(config_path: Path) -> dict[str, Any]:
    cfg = json.loads(read_text(config_path))
    text_cfg = cfg.get("text_config") if isinstance(cfg.get("text_config"), dict) else cfg
    keys = [
        "model_type",
        "hidden_size",
        "moe_intermediate_size",
        "num_hidden_layers",
        "num_experts",
        "num_experts_per_tok",
        "num_attention_heads",
        "num_key_value_heads",
        "vocab_size",
    ]
    return {key: text_cfg.get(key) for key in keys}


def find_function_body(text: str, marker: str) -> str:
    start = text.find(marker)
    if start < 0:
        return ""
    next_def = re.search(r"\n(?:def|class) ", text[start + len(marker):])
    if not next_def:
        return text[start:]
    end = start + len(marker) + next_def.start()
    return text[start:end]


def count_markers(text: str, markers: list[str]) -> dict[str, int]:
    return {marker: text.count(marker) for marker in markers}


def source_audit(vllm_root: Path, xpu_root: Path) -> dict[str, Any]:
    quark_path = vllm_root / "vllm/model_executor/layers/quantization/quark/quark_moe.py"
    int8_path = vllm_root / "vllm/model_executor/layers/fused_moe/oracle/int8.py"
    xpu_moe_path = vllm_root / "vllm/model_executor/layers/fused_moe/experts/xpu_moe.py"
    wrapper_path = xpu_root / "vllm_xpu_kernels/fused_moe_interface.py"
    grouped_path = xpu_root / "csrc/xpu/grouped_gemm/grouped_gemm_interface.cpp"
    sidecar_path = xpu_root / "csrc/xpu/onednn/qwen36_moe_sidecar.cpp"

    quark = read_text(quark_path)
    int8 = read_text(int8_path)
    xpu_moe = read_text(xpu_moe_path)
    wrapper = read_text(wrapper_path)
    grouped = read_text(grouped_path) if grouped_path.exists() else ""
    sidecar = read_text(sidecar_path) if sidecar_path.exists() else ""

    quark_cls = find_function_body(quark, "class QuarkW8A8Int8MoEMethod")
    xpu_apply = find_function_body(xpu_moe, "    def apply(")
    wrapper_fn = find_function_body(wrapper, "def xpu_fused_moe")

    return {
        "files": {
            "quark_moe": str(quark_path),
            "int8_oracle": str(int8_path),
            "xpu_moe": str(xpu_moe_path),
            "xpu_wrapper": str(wrapper_path),
            "grouped_gemm_interface": str(grouped_path),
            "onednn_sidecar": str(sidecar_path),
        },
        "quark_int8_method": {
            "present": bool(quark_cls),
            "selects_int8_backend": "select_int8_moe_backend" in quark_cls,
            "forces_weight_key_static_channel": "kInt8StaticChannelSym" in quark_cls,
            "uses_dynamic_token_activation_when_not_static": (
                "kInt8DynamicTokenSym" in quark_cls
            ),
            "creates_xpu_moe_kernel": "make_int8_moe_kernel" in quark_cls,
            "captures_route_in_apply": "route_capture.capture" in quark_cls,
            "sets_live_abi_context": "VLLM_XPU_MOE_LIVE_ABI_FILE" in quark_cls,
        },
        "int8_backend_selection": {
            "xpu_priority_on_xpu": (
                "if current_platform.is_xpu()" in int8
                and "return [Int8MoeBackend.XPU, Int8MoeBackend.TRITON]" in int8
            ),
            "xpu_backend_class": "XPUExpertsInt8" if "XPUExpertsInt8" in int8 else None,
            "supported_runner_backends": re.findall(r'"(triton|xpu)"', int8),
        },
        "xpu_experts_apply": {
            "present": bool(xpu_apply),
            "calls_xpu_fused_moe": "xpu_fused_moe(" in xpu_apply,
            "passes_is_int8": "is_int8=self.is_int8" in xpu_apply,
            "mixed_workspace_env": "VLLM_XPU_INT8_MOE_MIXED_WORKSPACE",
            "scratch_requires_workspace_manager": (
                "is_workspace_manager_initialized()" in xpu_apply
            ),
            "passes_diagnostic_context": "diagnostic_context=" in xpu_apply,
        },
        "xpu_fused_moe_wrapper": {
            "present": bool(wrapper_fn),
            "stage_marker_counts": count_markers(
                wrapper_fn,
                [
                    "remap_hidden_states",
                    "_per_token_quant_int8_out",
                    "cutlass_grouped_gemm_w8a8_int8_interface",
                    "_silu_and_mul_quant_int8_out",
                    "fused_moe_activation",
                    "moe_gather",
                    "_maybe_record_live_abi",
                    "_maybe_probe_onednn_sidecar",
                    "cutlass_grouped_gemm_w8a8_int8_offsets_interface",
                    "cutlass_grouped_gemm_w8a8_int8_active_offsets_interface",
                ],
            ),
            "fuse_silu_quant_env": "VLLM_XPU_FUSED_MOE_FUSE_SILU_QUANT",
            "sidecar_probe_env": "VLLM_XPU_MOE_ONEDNN_SIDECAR_PROBE",
            "live_abi_env": "VLLM_XPU_MOE_LIVE_ABI_FILE",
        },
        "source_route_aware_entry_points": {
            "offsets_interface_in_cpp_source": (
                "cutlass_grouped_gemm_w8a8_int8_offsets_interface" in grouped
            ),
            "active_offsets_interface_in_cpp_source": (
                "cutlass_grouped_gemm_w8a8_int8_active_offsets_interface" in grouped
            ),
            "onednn_sidecar_source_present": bool(sidecar),
            "onednn_sidecar_validates_qwen_shape": (
                "qwen36_moe_onednn_sidecar_probe" in sidecar
                and "require_shape(w13" in sidecar
            ),
        },
    }


def symbol_audit(xpu_root: Path) -> dict[str, Any]:
    xpu_so = xpu_root / "vllm_xpu_kernels/_xpu_C.abi3.so"
    moe_so = xpu_root / "vllm_xpu_kernels/_moe_C.abi3.so"
    patterns = [
        "per_token_quant_int8_xpu",
        "per_token_quant_int8_xpu_out",
        "silu_and_mul_quant_int8_xpu",
        "silu_and_mul_quant_int8_xpu_out",
        "cutlass_grouped_gemm_w8a8_int8_interface",
        "cutlass_grouped_gemm_w8a8_int8_offsets_interface",
        "cutlass_grouped_gemm_w8a8_int8_active_offsets_interface",
        "qwen36_moe_onednn_sidecar_probe",
        "persistent",
    ]

    def scan(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {"path": str(path), "exists": False}
        nm = run(["bash", "-lc", f"nm -D {path} 2>/dev/null | c++filt"], timeout=30)
        strings = run(["strings", str(path)], timeout=30)
        haystacks = {
            "nm": nm["stdout"],
            "strings": strings["stdout"],
        }
        return {
            "path": str(path),
            "exists": True,
            "size_bytes": path.stat().st_size,
            "mtime_utc": datetime.fromtimestamp(
                path.stat().st_mtime, timezone.utc
            ).isoformat(),
            "patterns": {
                pattern: {
                    "in_nm": pattern in haystacks["nm"],
                    "in_strings": pattern in haystacks["strings"],
                    "nm_matches": [
                        line
                        for line in haystacks["nm"].splitlines()
                        if pattern in line
                    ][:8],
                    "string_matches": [
                        line
                        for line in haystacks["strings"].splitlines()
                        if pattern in line
                    ][:8],
                }
                for pattern in patterns
            },
        }

    return {"_xpu_C": scan(xpu_so), "_moe_C": scan(moe_so)}


def endpoint_audit(endpoint_regex: str) -> dict[str, Any]:
    pgrep = run(["pgrep", "-af", endpoint_regex])
    matches = [line for line in pgrep["stdout"].splitlines() if line.strip()]
    endpoint = {"regex": endpoint_regex, "matches": matches, "env": {}}
    if not matches:
        return endpoint
    pid = matches[0].split(maxsplit=1)[0]
    endpoint["pid"] = pid
    env_path = Path(f"/proc/{pid}/environ")
    wanted = [
        "VLLM_XPU_INT8_MOE_MIXED_WORKSPACE",
        "VLLM_XPU_FUSED_MOE_FUSE_SILU_QUANT",
        "VLLM_XPU_MOE_ONEDNN_SIDECAR_PROBE",
        "VLLM_XPU_MOE_LIVE_ABI_FILE",
        "XPU_GRAPH",
        "VLLM_XPU_ENABLE_XPU_GRAPH",
        "VLLM_XPU_FORCE_GRAPH_WITH_COMM",
        "VLLM_XPU_QUARK_W8A8_MOE",
    ]
    try:
        raw = env_path.read_bytes().split(b"\0")
        env = {}
        for key in wanted:
            prefix = (key + "=").encode()
            values = [
                item.decode(errors="replace").split("=", 1)[1]
                for item in raw
                if item.startswith(prefix)
            ]
            env[key] = values[0] if values else None
        endpoint["env"] = env
    except Exception as exc:
        endpoint["env_error"] = repr(exc)
    return endpoint


def derive_decisions(audit: dict[str, Any]) -> list[dict[str, Any]]:
    wrapper_counts = audit["source"]["xpu_fused_moe_wrapper"]["stage_marker_counts"]
    xpu_patterns = audit["symbols"]["_xpu_C"]["patterns"]
    endpoint_env = audit["endpoint"].get("env", {})

    decisions: list[dict[str, Any]] = []
    decisions.append({
        "finding": "Current Quark W8A8 INT8 dispatch selects the XPU Int8 MoE backend.",
        "evidence": [
            "QuarkW8A8Int8MoEMethod calls select_int8_moe_backend.",
            "select_int8_moe_backend prioritizes XPU before TRITON on XPU.",
            "XPUExpertsInt8 passes is_int8=True into xpu_fused_moe.",
        ],
        "impact": "Optimization work should target XPU xpu_fused_moe / vllm-xpu-kernels, not Triton.",
    })
    decisions.append({
        "finding": "Runtime wrapper is multi-stage, not a single persistent MoE island.",
        "evidence": [
            f"remap markers: {wrapper_counts.get('remap_hidden_states', 0)}",
            f"W8A8 GEMM calls: {wrapper_counts.get('cutlass_grouped_gemm_w8a8_int8_interface', 0)}",
            f"per-token quant calls: {wrapper_counts.get('_per_token_quant_int8_out', 0)}",
            f"gather markers: {wrapper_counts.get('moe_gather', 0)}",
        ],
        "impact": "A fused/persistent c1 topk-8 MoE layerlet could remove several per-token launches and temporary tensors without changing math.",
    })
    decisions.append({
        "finding": "Installed _xpu_C exports base W8A8 grouped GEMM, but not offset/active-offset entry points.",
        "evidence": [
            f"base GEMM exported: {xpu_patterns['cutlass_grouped_gemm_w8a8_int8_interface']['in_nm'] or xpu_patterns['cutlass_grouped_gemm_w8a8_int8_interface']['in_strings']}",
            f"offset GEMM exported: {xpu_patterns['cutlass_grouped_gemm_w8a8_int8_offsets_interface']['in_nm'] or xpu_patterns['cutlass_grouped_gemm_w8a8_int8_offsets_interface']['in_strings']}",
            f"active-offset GEMM exported: {xpu_patterns['cutlass_grouped_gemm_w8a8_int8_active_offsets_interface']['in_nm'] or xpu_patterns['cutlass_grouped_gemm_w8a8_int8_active_offsets_interface']['in_strings']}",
        ],
        "impact": "The dirty source has route-aware prototypes, but the installed binary is still on the row-count interface. Rebuild/ABI validation is needed before route-aware hotset tests.",
    })
    decisions.append({
        "finding": "Two easy env toggles remain rejected for production.",
        "evidence": [
            f"live VLLM_XPU_INT8_MOE_MIXED_WORKSPACE={endpoint_env.get('VLLM_XPU_INT8_MOE_MIXED_WORKSPACE')}",
            f"live VLLM_XPU_FUSED_MOE_FUSE_SILU_QUANT={endpoint_env.get('VLLM_XPU_FUSED_MOE_FUSE_SILU_QUANT')}",
            "Prior notes reject mixed workspace as slower and fused SiLU+quant as quality-failing.",
        ],
        "impact": "Do not spend another endpoint cycle simply enabling these flags. Use route fixtures and parity gates for new implementations.",
    })
    return decisions


def write_markdown(path: Path, audit: dict[str, Any]) -> None:
    lines = [
        "# Qwen3.6 Quark INT8 XPU Kernel Path Audit",
        "",
        f"Generated: `{audit['generated_at']}`",
        "",
        "## Model Shape",
        "",
    ]
    shape = audit["model_shape"]
    for key, value in shape.items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Main Findings", ""])
    for idx, decision in enumerate(audit["decisions"], 1):
        lines.append(f"{idx}. **{decision['finding']}**")
        for item in decision["evidence"]:
            lines.append(f"   - {item}")
        lines.append(f"   - Impact: {decision['impact']}")
    lines.extend(["", "## Runtime Endpoint", ""])
    endpoint = audit["endpoint"]
    lines.append(f"- Matches: `{len(endpoint.get('matches', []))}`")
    if endpoint.get("pid"):
        lines.append(f"- PID: `{endpoint['pid']}`")
    for key, value in endpoint.get("env", {}).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Installed Symbol Snapshot", ""])
    for so_name, so in audit["symbols"].items():
        lines.append(f"### `{so_name}`")
        lines.append(f"- Path: `{so.get('path')}`")
        lines.append(f"- Exists: `{so.get('exists')}`")
        if so.get("exists"):
            lines.append(f"- Size bytes: `{so.get('size_bytes')}`")
            for pattern, result in so.get("patterns", {}).items():
                if pattern in (
                    "cutlass_grouped_gemm_w8a8_int8_interface",
                    "cutlass_grouped_gemm_w8a8_int8_offsets_interface",
                    "cutlass_grouped_gemm_w8a8_int8_active_offsets_interface",
                    "qwen36_moe_onednn_sidecar_probe",
                    "per_token_quant_int8_xpu",
                    "silu_and_mul_quant_int8_xpu",
                ):
                    present = result.get("in_nm") or result.get("in_strings")
                    lines.append(f"- `{pattern}`: `{present}`")
        lines.append("")
    lines.extend(["## Next Gate", ""])
    lines.append(
        "Rebuild or isolate a `vllm-xpu-kernels` candidate that exposes the "
        "offset/active-offset W8A8 INT8 entry points, then replay the "
        "first-decode route fixture with exact tensor comparison before any "
        "endpoint launch."
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-config", default=DEFAULT_MODEL_CONFIG)
    parser.add_argument("--vllm-root", default=DEFAULT_VLLM_ROOT)
    parser.add_argument("--xpu-kernels-root", default=DEFAULT_XPU_KERNELS_ROOT)
    parser.add_argument("--endpoint-regex", default=DEFAULT_ENDPOINT_RE)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--markdown-out", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    vllm_root = Path(args.vllm_root)
    xpu_root = Path(args.xpu_kernels_root)
    audit: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model_config": args.model_config,
        "model_shape": load_model_shape(Path(args.model_config)),
        "git": {
            "vllm": git_info(vllm_root),
            "vllm_xpu_kernels": git_info(xpu_root),
        },
        "source": source_audit(vllm_root, xpu_root),
        "symbols": symbol_audit(xpu_root),
        "endpoint": endpoint_audit(args.endpoint_regex),
        "known_rejected_flags": {
            "VLLM_XPU_INT8_MOE_MIXED_WORKSPACE": {
                "reason": "quality-safe but slower in previous full endpoint gate",
                "notes": "notes/2026-06-10-qwen36-moe-mixed-workspace-rejected.md",
            },
            "VLLM_XPU_FUSED_MOE_FUSE_SILU_QUANT": {
                "reason": "failed text quality/arithmetic canary in previous gate",
                "notes": "notes/2026-06-10-qwen36-exact-siluq-rejected.md",
            },
        },
    }
    audit["decisions"] = derive_decisions(audit)

    output_json = Path(args.output_json)
    markdown_out = Path(args.markdown_out)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")
    write_markdown(markdown_out, audit)


if __name__ == "__main__":
    main()
