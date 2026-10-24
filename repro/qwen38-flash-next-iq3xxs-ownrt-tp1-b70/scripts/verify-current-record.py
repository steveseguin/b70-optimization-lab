#!/usr/bin/env python3
"""Read-only replay of the pinned P196 capped record; no benchmark or submission."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
import resource
import signal
import sys

ROOT = Path(__file__).resolve().parents[3]
PACKET = "experiments/own-xpu-runtime/stage2/packet196-onecard-diet-chain/"
RESULT = PACKET + "submission/prepared-a/result.json"
BUNDLE = PACKET + "submission/prepared-a/evidence.json.gz"
LEDGER = "scripts/packet58_onecard_record_threshold.json"
PINS = {
    PACKET + "packet58_submission.py": "81d8b22a718bbadc3b5ad391c8cda62a10c4aa75b989376ab49fe9cc0099aa73",
    PACKET + "suite_metrics.py": "4eef50d1272c759904b64947297c865b71b683a52c5590fb822301bcdc7f04aa",
    PACKET + "composition.py": "b12c1a3ed605308275101998c8b56f3da0ffe58c91ae3b824fa858a00290c4da",
    PACKET + "submission-policy.json": "f615a12c0bcfbcfe2f3102ac75b5b73805893af58f5b98b99245c6c4ad94bc23",
    PACKET + "submission-pins.json": "ea4ecda79c2974b51f43822873ec8d9a79f24e19de1d41e50e4f98a02d06f4c6",
    RESULT: "1d457535852ab0b8bccab207122bf8983ca5960bb3ae7dde0a26f424ab904ba4",
    BUNDLE: "76b5f58346f36417fe83a002e0b28a1599138008747bd46ee5fc078e8f5db8f9",
    LEDGER: "895c3d83e1bc4f535542f2e9b2d7e9c5da28c23ae72006eb0ca4046aab755dc8",
}
EXPECTED_SPEED = 37.59560460827345
RECORD_ID = "cmvl5k4p9004nng01z5xtanw5"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_only(event, args):
    """Backstop for the inspected pure replay path, not a general sandbox."""
    if event.startswith(("socket.", "subprocess.", "os.exec", "os.spawn")) or event in {
        "os.system", "ctypes.dlopen", "os.remove", "os.rename", "os.mkdir",
        "os.rmdir", "os.truncate", "os.chmod", "os.chown", "os.link", "os.symlink",
    }:
        raise RuntimeError("read-only evidence verifier refused " + event)
    if event == "open":
        path, mode, flags = args
        if (mode and any(x in mode for x in "wax+")) or flags & (
            os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND
        ):
            raise RuntimeError("read-only evidence verifier refused writable open")
        if isinstance(path, (str, bytes)) and os.fsdecode(path).startswith(("/dev/dri/", "/dev/accel/")):
            raise RuntimeError("read-only evidence verifier refused device open")


def load(name, relative):
    require(name not in sys.modules, "unexpected preloaded verifier module: " + name)
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    require(Path(module.__file__).resolve() == (ROOT / relative).resolve(), "verifier module origin")
    return module


def configure_process():
    """Restrict this process only; never widen its existing CPU affinity."""
    allowed = set(os.sched_getaffinity(0))
    require(allowed, "no allowed CPUs")
    preferred = allowed & (set(range(8, 16)) | set(range(24, 32)))
    selected = set(sorted(preferred or allowed)[:2])
    os.setpriority(os.PRIO_PROCESS, 0, 19)
    os.sched_setaffinity(0, selected)
    for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ[key] = "2"
    require(set(os.sched_getaffinity(0)) == selected, "process affinity was not applied")
    require(os.getpriority(os.PRIO_PROCESS, 0) == 19, "process priority was not applied")
    return {"nice": 19, "allowed_cpus_before": sorted(allowed),
            "selected_cpus": sorted(selected), "threads": 2}


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    placement = configure_process()
    resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3, 4 * 1024**3))
    resource.setrlimit(resource.RLIMIT_CPU, (120, 120))
    signal.alarm(120)
    sys.dont_write_bytecode = True
    sys.addaudithook(read_only)
    for relative, expected in PINS.items():
        require(digest(ROOT / relative) == expected, "pinned input changed: " + relative)
    metrics = load("suite_metrics", PACKET + "suite_metrics.py")
    load("composition", PACKET + "composition.py")
    verifier = load("packet58_submission", PACKET + "packet58_submission.py")
    result = json.loads((ROOT / RESULT).read_text())
    # replay_result only reads the hash-bound archive and derives its result.
    # Never call collect(), main(), write_prepared(), update_record(), or a CLI.
    replayed = verifier.replay_result(result, ROOT)
    record = verifier.validate_threshold(json.loads((ROOT / LEDGER).read_text()))
    require(record["reference_submission"] == RECORD_ID, "current local record ID changed")
    require(record["result"] == {"path": RESULT, "sha256": PINS[RESULT]}, "local record result differs")
    require(replayed["primary_metric"]["value_tok_s"] == record["threshold_tok_s"] == EXPECTED_SPEED,
            "recomputed record metric differs")
    rows = replayed["rows"]
    require(len(rows) == 12 and [row["prompt_id"] for row in rows] == list(metrics.PROMPT_CLASSES),
            "exact twelve-prompt suite required")
    require(all(row["exact_oracle"] and row["requested_max_new"] == row["output_tokens"] == 128
                and len(row["tokens"]) == 128 for row in rows), "128-token exactness differs")
    require(replayed["exactness"]["all_prompts_exact"] is True, "exact oracle gate failed")
    for relative, expected in PINS.items():
        require(digest(ROOT / relative) == expected, "input changed during replay: " + relative)
    print(json.dumps({
        "schema": "qwen38-ownrt-p196.read-only-record-verification.v1", "passed": True,
        "verification": "pinned packet58_submission.replay_result; full derived result equality",
        "process_limits": dict(placement, address_space_bytes=4 * 1024**3, deadline_seconds=120),
        "source_sha256": digest(__file__), "input_sha256": PINS,
        "current_local_record_id": RECORD_ID, "packet": replayed["packet"],
        "model": replayed["model"], "gpu_count": replayed["gpu_count"],
        "promotion_identity": replayed["promotionIdentity"], "primary_metric": replayed["primary_metric"],
        "requested_max_new": 128, "exact_prompts": len(rows), "exact_output_tokens": sum(len(r["tokens"]) for r in rows),
        "prompt_ids": [r["prompt_id"] for r in rows],
        "strict_512_gate_passed": replayed["submission_scope"]["strict_512_gate_passed"],
        "fresh_timing_repeat_passed": replayed["fresh_timing_repeat_passed"],
        "device_executed": False, "model_executed": False, "network_used": False,
        "new_submission": False, "new_measurement": False,
        "scope": "Retained capped evidence replay and pinned local record identity; no current global leaderboard claim or new device qualification.",
    }, indent=2, allow_nan=False))
    signal.alarm(0)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, OSError, KeyError, TypeError) as error:
        print("REFUSED: " + str(error), file=sys.stderr)
        raise SystemExit(1)
