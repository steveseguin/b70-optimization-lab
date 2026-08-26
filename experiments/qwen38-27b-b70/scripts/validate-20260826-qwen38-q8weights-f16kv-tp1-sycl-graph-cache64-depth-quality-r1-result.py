#!/usr/bin/env python3
"""Read-only validator for the compact Q8_0/F16 cache64 graph curve."""

from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
CAMPAIGN = "qwen38-q8weights-f16kv-tp1-sycl-graph-cache64-depth-quality-20260826-r1"
ROOT = Path("/mnt/fast-ai/bench-results") / CAMPAIGN
RESULT = REPO / "experiments/qwen38-27b-b70/data/2026-08-26-qwen38-q8weights-f16kv-tp1-sycl-graph-cache64-depth-quality-r1-result.json"
DEPTHS = [0, 2048, 4096, 8192, 16384, 24576, 32768]

def load(path): return json.loads(path.read_text(encoding="utf-8"))
def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 << 20), b""): h.update(chunk)
    return h.hexdigest()
def need(value, message):
    if not value: raise RuntimeError(message)

def validate(root, result_path):
    result = load(result_path)
    need(result["campaign_id"] == CAMPAIGN and result["status"] == "passed", "compact result identity/status changed")
    for binding in result["tracked_inputs"].values():
        path = REPO / binding["path"]
        need(path.is_file() and digest(path) == binding["sha256"], f"tracked input changed: {path}")
    hashes = result["raw_artifacts"]["sha256"]
    actual = sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())
    need(len(hashes) == 25 and actual == sorted(hashes), "raw inventory changed")
    for relative, expected in hashes.items(): need(digest(root / relative) == expected, f"raw hash changed: {relative}")
    identity = load(root / "identity.json")
    need(identity["git_head"] == identity["origin_main"] == result["identity"]["git_head_and_origin_main"], "Git identity changed")
    need(identity["model"]["sha256"] == result["identity"]["model"]["sha256"], "model changed")
    need(identity["graph_runtime"]["binary_sha256"] == result["identity"]["runtime"]["binary_sha256"], "runtime changed")
    need(identity["runtime_environment"] == {"GGML_SYCL_ENABLE_GRAPH":"1","GGML_SYCL_GRAPH_CACHE_SIZE":"64","ONEAPI_DEVICE_SELECTOR":"level_zero:0"}, "graph environment changed")
    cells = []
    for depth in DEPTHS:
        raw = load(root / f"target-mtp0-graph-cache64/depth-{depth}/exact-depth.json")
        need(raw == load(root / f"target-mtp0-graph-cache64/depth-{depth}/exact-depth.stdout.json"), f"depth stdout mismatch: {depth}")
        need(raw["status"] == "passed" and raw["gate"]["passed"] and all(raw["gate"]["checks"].values()), f"depth failed: {depth}")
        response = raw["response"]
        need(response["usage"]["completion_tokens"] == 128 and response["usage"]["prompt_tokens_details"]["cached_tokens"] == 0, f"usage changed: {depth}")
        cells.append({"active_context_tokens":depth,"serving_decode_tok_s_99_interval":raw["metric_window"]["conventional_99_interval_tok_s"],"time_to_first_token_s":raw["metric_window"]["time_to_first_token_s"],"cached_tokens":0,"completion_tokens":128,"output_token_ids_sha256":response["output_token_ids_sha256"],"text_sha256":response["text_sha256"]})
    need(cells == result["serving_curve"]["cells"], "compact curve differs from raw receipts")
    quality = load(root / "target-mtp0-graph-cache64/quality.json")
    requests = quality["exact_cases"] + quality["repeat_case"]["runs"] + [quality["long_context_case"]]
    need(quality["pass_all"] and len(quality["exact_cases"]) == 7 and all(row["pass"] for row in quality["exact_cases"]), "quality failed")
    need(quality["repeat_case"]["pass"] and len(quality["repeat_case"]["unique_hashes"]) == 1, "repeat quality failed")
    need(quality["long_context_case"]["pass"] and all(row["usage"]["prompt_tokens_details"]["cached_tokens"] == 0 for row in requests), "needle/cache-zero failed")
    graph = load(root / "target-mtp0-graph-cache64/graph-evidence.json")
    need(graph["requested"] == graph["cache_hit"] + graph["cache_miss"], "graph hit/miss conservation failed")
    need(graph["replayed"] + graph["cache_full"] == graph["requested"], "graph replay/full conservation failed")
    need(graph["direct_replay"] == 947 >= result["graph_mechanism"]["minimum_direct_replays"], "direct replay floor failed")
    need(graph["created"] == graph["recorded"] == graph["cache_entries"] == 64, "graph creation conservation failed")
    need(load(root / "target-mtp0-graph-cache64/cleanup.json") == {"forced_kill":False,"port_closed":True,"render_node_idle":True,"server_survivor":False}, "cleanup failed")
    terminal = load(root / "terminal-receipt.json")
    need(terminal == load(root / "validator.stdout.json"), "terminal/stdout differ")
    need(terminal["status"] == result["validation"]["terminal_status"] and len(terminal["checks"]) == 19 and all(terminal["checks"].values()), "terminal is not 19/19")
    need(terminal["authority"]["graph_q8weights_f16_serving_curve_cells"] == 7 and terminal["authority"]["graph_off_cells"] == 0 and not terminal["authority"]["protected_or_headline_replacement"], "authority widened")
    return {"status":"pass","raw_files_verified":len(hashes),"terminal_checks":len(terminal["checks"]),"cells_verified":len(cells),"direct_replay":graph["direct_replay"],"site_cells_authorized":7,"graph_off_cells_replaced":0}

def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--root", type=Path, default=ROOT); parser.add_argument("--result", type=Path, default=RESULT); args = parser.parse_args()
    try: report = validate(args.root, args.result)
    except (KeyError, OSError, TypeError, ValueError, RuntimeError, json.JSONDecodeError) as exc: parser.error(str(exc))
    print(json.dumps(report, indent=2, sort_keys=True)); return 0
if __name__ == "__main__": raise SystemExit(main())
