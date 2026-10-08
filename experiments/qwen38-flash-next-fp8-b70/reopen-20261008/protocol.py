#!/usr/bin/env python3
"""One fixed-mode, 16-generation-request screen; dry-run unless --execute.

The morning proposal's 32-request ceiling = (four pins + twelve prompts) *
two modes. Stock v0.30.0 cannot change speculative depth per request. This
client never changes mode or starts a server: choose one arm per launch.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import shlex
import signal
import sys
import urllib.parse

ROOT = Path(__file__).resolve().parents[3]
LANE = ROOT / "experiments/qwen38-flash-next-fp8-b70"
DEPTH = ROOT / "scripts/bench-openai-token-depth-suite.py"
REALISTIC = ROOT / "scripts/bench-openai-realistic-suite.py"
FIXTURE = ROOT / "data/qwen27-exact-depth/qwen38-flash-next-bcd9f01-exact-depth-v1.json"
SUITE = ROOT / "repro/rapid-model-snapshots-b70/realistic-suite-v1.json"
FILE_PINS = {
    DEPTH: "8f162c1ab9fde7e0daffed2c4f0d6ff061ad6076c5de716e36f3d883ab4a1067",
    REALISTIC: "7b4aef6fca0ffebf6ab83ac0b70bb13505cb4b93010f45529623dcf8892fc130",
    FIXTURE: "c44fccbaf600cc506d8ed0cc7357161057b86abc44469b611be71db97558061d",
    SUITE: "0ad543d1c1f379a0b6cee88e06236e495c45eee7ba12cfcef062b6e03303e812",
}
OUTPUT_PINS = {
    2048: "afffd2110812762164862b6388f054bb56696ee57b07eadce411a702c40bc714",
    4096: "1d833e5f463366223a669aa15495840d1337b173e675a9ea04f00a5ae339d5cc",
}


def token_hash(ids):
    return hashlib.sha256(json.dumps(ids, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def load_module(path):
    spec = importlib.util.spec_from_file_location("screen1_" + path.stem.replace("-", "_"), path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def invoke_client(module, cmd, log_path):
    """Run the stdlib client in this process: cancellation leaves no child."""
    saved_argv = sys.argv
    try:
        sys.argv = cmd[1:]
        with log_path.open("w") as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            return module.main()
    finally:
        sys.argv = saved_argv


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mode", choices=("mtp0", "mtp1", "mtp3"), default="mtp1")
    p.add_argument("--base-url", default="http://127.0.0.1:19988")
    p.add_argument("--model", default="qwen38-flash-next-fp8-tp4",
                   choices=("qwen38-flash-next-fp8-tp4",))
    p.add_argument("--output-dir", type=Path, default=Path("/tmp/q38-screen1-mtp1"))
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--execute", action="store_true")
    mode.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    url = urllib.parse.urlsplit(a.base_url)
    if (url.scheme != "http" or url.hostname not in {"127.0.0.1", "localhost", "::1"}
            or url.username or url.password or url.query or url.fragment or url.path):
        p.error("use a credential-free loopback HTTP base URL with no path")
    for path, expected in FILE_PINS.items():
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RuntimeError(f"review required: input/client hash changed: {path}")
    authority = {}
    authority_sources = {}
    for depth, pin in OUTPUT_PINS.items():
        source = LANE / f"data/20260913-tp4-mtp1-a364-native-exact-gdn-exact-depth-{depth // 1024}k-r1.json"
        ids = json.loads(source.read_text())["response"]["token_ids"]
        if len(ids) != 128 or token_hash(ids) != pin:
            raise RuntimeError(f"invalid frozen authority: {source}")
        authority[depth] = ids
        authority_sources[depth] = {"path": str(source.relative_to(ROOT)),
                                    "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
    if len(json.loads(SUITE.read_text())["prompts"]) != 12:
        raise RuntimeError("fixed suite must have twelve prompts")
    out = a.output_dir.resolve()
    commands = []
    for depth in (2048, 4096):
        for repeat in (1, 2):
            destination = out / f"exact-{depth}-r{repeat}.json"
            cmd = [sys.executable, str(DEPTH), "--execute", "--fixture", str(FIXTURE),
                   "--depth", str(depth), "--context-capacity", "4352", "--base-url",
                   a.base_url, "--model", a.model, "--response-adapter", "vllm",
                   "--timeout", "900" if depth == 2048 else "1400", "--out", str(destination)]
            commands.append((depth, repeat, destination, cmd))
    suite_command = [sys.executable, str(REALISTIC), "--base-url", a.base_url,
                     "--model", a.model, "--api-mode", "chat", "--suite", str(SUITE),
                     "--max-tokens", "512", "--metric-tokens", "100", "--seed",
                     "20260609", "--timeout", "900", "--return-token-ids",
                     "--require-natural-eos", "--request-extra-json",
                     '{"chat_template_kwargs":{"enable_thinking":false},"seed":20260609,"temperature":0,"top_p":1.0}',
                     "--out", str(out / "realistic-suite.json")]
    plan = {"mode": a.mode, "generation_requests": 16, "server_launches_by_client": 0,
            "request_order": "exact-2K twice; exact-4K twice; twelve fixed varied prompts once",
            "request_budget_explanation": "K1 and K3 require separate launches: 16+16=32; optional MTP0 adds16",
            "file_pins": {str(k.relative_to(ROOT)): v for k, v in FILE_PINS.items()},
            "authority_sources": authority_sources,
            "commands": [shlex.join(c[3]) for c in commands] + [shlex.join(suite_command)],
            "quality_scope": "two fixtures repeated; no certification or promotion",
            "fused_pin_miss_policy": "retain mismatch, continue diagnostic-only realistic speed; never accept new pins",
            "stop_policy": "first transport/cache/stream/runtime failure; no retry or server cycling"}
    if not a.execute:
        print(json.dumps(plan, indent=2))
        return 0
    out.mkdir(parents=True, exist_ok=False)
    write(out / "plan.json", plan)
    summary = {"schema": "qwen38-screen1-protocol-v1", "mode": a.mode,
               "started_at_utc": dt.datetime.now(dt.UTC).isoformat(),
               "status": "running", "quality_passed": False, "promotion_eligible": False,
               "historical_reference_tok_s": 46.854250,
               "comparison": "historical screen, not contemporaneous A/B",
               "generation_requests_attempted": 0, "exact_rows": []}
    write(out / "summary.json", summary)
    def cancelled(signum, frame):
        raise SystemExit(128 + signum)
    signal.signal(signal.SIGTERM, cancelled)
    signal.signal(signal.SIGINT, cancelled)
    try:
        depth_module = load_module(DEPTH)
        for depth, repeat, destination, cmd in commands:
            summary["generation_requests_attempted"] += 1
            write(out / "summary.json", summary)
            rc = invoke_client(depth_module, cmd, destination.with_suffix(".log"))
            if rc != 0:
                raise RuntimeError(f"exact client failure rc={rc}; stop without retry")
            row = json.loads(destination.read_text())
            if not row["gate"]["passed"]:
                raise RuntimeError("exact-depth transport/cache/metric gate failed")
            ids = row["response"]["token_ids"]
            diffs = [{"position": i, "expected": x, "actual": y}
                     for i, (x, y) in enumerate(zip(authority[depth], ids)) if x != y]
            exact = ids == authority[depth] and row["response"]["output_token_ids_sha256"] == OUTPUT_PINS[depth]
            summary["exact_rows"].append({"depth": depth, "repeat": repeat,
                "first_use_timing": depth == 2048 and repeat == 1,
                "matches_pin_and_all_tokens": exact, "expected_sha256": OUTPUT_PINS[depth],
                "actual_sha256": token_hash(ids), "token_differences": diffs,
                "timing": row["metric_window"], "artifact": destination.name})
            write(out / "summary.json", summary)
        summary["exactness_pins_passed"] = all(r["matches_pin_and_all_tokens"] for r in summary["exact_rows"])
        # Reuse the frozen full-suite implementation, wrapping only transport to
        # save each row immediately and abort before another prompt on bad cache
        # or stream evidence. Metric computation and requests remain its own.
        module = load_module(REALISTIC)
        # The runner captures hardware/runtime identity. Avoid the historical
        # client's optional xpu-smi subprocess so cancellation has no children.
        module._measuring_host = lambda: {
            "hostname": platform.node(),
            "gpu_identity": "see parent runner receipts; protocol does not query devices",
        }
        original_post = module.post_stream
        count = 0

        def guarded_post(**kwargs):
            nonlocal count
            count += 1
            if count > 12:
                raise RuntimeError("suite request ceiling exceeded")
            summary["generation_requests_attempted"] += 1
            write(out / "summary.json", summary)
            write(out / f"suite-request-{count:02d}.json", kwargs)
            row = original_post(**kwargs)
            row["output_token_ids_sha256"] = token_hash(row["token_ids"])
            offsets = row["token_id_offsets_s"]
            row["screen_metric_accounting"] = {"events": min(len(offsets), 100),
                "intervals": 99 if len(offsets) >= 100 else None,
                "numerator": 99 if len(offsets) >= 100 else None,
                "first_event_offset_s": offsets[0] if offsets else None,
                "last_event_offset_s": offsets[99] if len(offsets) >= 100 else None,
                "timestamps": "client SSE arrival; tokens in one chunk share a timestamp"}
            write(out / f"suite-row-{count:02d}.json", row)
            if module.cached_tokens(row) != 0:
                raise RuntimeError("missing/nonzero cached_tokens; no further requests")
            if (not row["token_ids"] or len(offsets) != len(row["token_ids"])
                    or row["finish_reasons"] not in (["stop"], ["length"])):
                raise RuntimeError("incomplete token stream/finish reason; no further requests")
            return row

        module.post_stream = guarded_post
        rc = invoke_client(module, suite_command, out / "realistic-suite.log")
        suite = json.loads((out / "realistic-suite.json").read_text())
        summary.update({"status": "complete", "generation_requests_completed": 4 + count,
            "realistic_workload_gate_passed": suite["realistic_final_gate"]["passed"],
            "realistic_client_rc": rc, "measurements": suite["summary"],
            "quality_status": "pins-match-only; full battery/fresh-server repeat absent" if summary["exactness_pins_passed"] else "pin-miss; diagnostic speed only",
            "next_step": "Screen2: port exact serial GDN and remaining authority arithmetic, then matched qualification"})
        if count != 12 or not suite["realistic_final_gate"]["cached_tokens_all_zero"]:
            raise RuntimeError("full cold suite incomplete/invalid")
        write(out / "summary.json", summary)
        print(json.dumps(summary, indent=2))
        return 0 if rc == 0 else 2
    except BaseException as error:
        summary.update({"status": "aborted", "error": str(error), "error_type": type(error).__name__})
        write(out / "summary.json", summary)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
