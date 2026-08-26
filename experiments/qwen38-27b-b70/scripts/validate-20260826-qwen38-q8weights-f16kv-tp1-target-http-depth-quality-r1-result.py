#!/usr/bin/env python3
"""Validate the compact Q8_0-weight/F16-KV result against retained raw evidence."""

from __future__ import annotations
import hashlib, json
from pathlib import Path

REPO=Path(__file__).resolve().parents[3]
RESULT=REPO/"experiments/qwen38-27b-b70/data/2026-08-26-qwen38-q8weights-f16kv-tp1-target-http-depth-quality-r1-result.json"
ROOT=Path("/mnt/fast-ai/bench-results/qwen38-q8weights-f16kv-tp1-target-http-depth-quality-20260826-r1")
DEPTHS=(0,2048,4096,8192,16384,24576,32768)
TERMINAL_SHA="42d12af5440c63f7b0ae1c765e491df5a7bff7138c367916d6202b2ff45b1aad"

def load(path: Path): return json.loads(path.read_text(encoding="utf-8"))
def sha(path: Path) -> str:
    digest=hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda:stream.read(4<<20),b""): digest.update(chunk)
    return digest.hexdigest()

def main() -> int:
    result=load(RESULT); terminal=load(ROOT/"terminal-receipt.json"); identity=load(ROOT/"identity.json"); quality=load(ROOT/"target-mtp0/quality.json"); cleanup=load(ROOT/"target-mtp0/cleanup.json"); arm=load(ROOT/"target-mtp0/arm-result.json")
    assert sha(ROOT/"terminal-receipt.json")==TERMINAL_SHA==result["raw_artifacts"]["sha256"]["terminal-receipt.json"]
    assert result["status"]=="passed" and terminal["status"]=="completed-valid-target-only-q8weights-f16kv-depth-quality"
    assert result["identity"]["git_head"]==result["identity"]["origin_main"]==identity["git_head"]==identity["origin_main"]
    assert result["identity"]["model"]["sha256"]==identity["model"]["sha256"]
    assert result["identity"]["runtime"]["binary_sha256"]==identity["runtime"]["binary_sha256"]
    assert result["validation"]["terminal_checks"]==terminal["checks"] and len(terminal["checks"])==16 and all(terminal["checks"].values())
    assert result["authority"]==terminal["authority"]
    assert cleanup=={"forced_kill":False,"port_closed":True,"render_node_idle":True,"server_survivor":False} and arm["cleanup"]==cleanup and arm["error"] is None
    for compact,cell,depth in zip(result["serving_curve"]["cells"],terminal["cells"],DEPTHS,strict=True):
        raw_path=ROOT/f"target-mtp0/depth-{depth}/exact-depth.json"; raw=load(raw_path)
        assert compact["active_context_tokens"]==cell["active_context_tokens"]==depth
        assert compact["serving_decode_tok_s_99_interval"]==cell["serving_decode_tok_s_99_interval"]==raw["metric_window"]["conventional_99_interval_tok_s"]
        assert compact["output_token_ids_sha256"]==cell["output_token_ids_sha256"]==raw["response"]["output_token_ids_sha256"]
        assert compact["text_sha256"]==raw["response"]["text_sha256"] and compact["receipt_sha256"]==sha(raw_path)
        assert compact["cached_tokens"]==cell["cached_tokens"]==raw["response"]["usage"]["prompt_tokens_details"]["cached_tokens"]==0
        assert compact["completion_tokens"]==raw["response"]["usage"]["completion_tokens"]==128
    compact_exact=result["quality"]["exact_cases"]["outputs"]
    assert compact_exact==[{"name":x["name"],"sha256":x["sha256"]} for x in quality["exact_cases"]]
    assert quality["pass_all"] and all(x["pass"] and x["usage"]["prompt_tokens_details"]["cached_tokens"]==0 for x in quality["exact_cases"])
    repeat=quality["repeat_case"]; long=quality["long_context_case"]
    assert result["quality"]["repeat_stability"]["output_sha256"]==repeat["unique_hashes"][0] and repeat["pass"] and len(repeat["unique_hashes"])==1
    assert result["quality"]["long_context_needle"]["output_sha256"]==long["sha256"] and long["pass"] and long["actual_prompt_tokens"]==25200 and long["usage"]["prompt_tokens_details"]["cached_tokens"]==0
    assert sum(1 for path in ROOT.rglob("*") if path.is_file()) == result["raw_artifacts"]["file_count"] == 24
    for relative, expected in result["raw_artifacts"]["sha256"].items():
        assert sha(ROOT/relative) == expected
    print("PASS: compact Q8_0-weight/F16-KV result matches retained raw evidence")
    return 0

if __name__=="__main__": raise SystemExit(main())
