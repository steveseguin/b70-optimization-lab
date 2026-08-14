#!/usr/bin/env python3
"""Run two fresh canonical Muse Q8/WOQ 256-token record trials."""

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import urllib.request

TARGET_SHA = "e63bf23b7710ecdea2579e4b1de58980c4a2b446e8ecf48b782cfcefd2e31770"
DRAFT_SHA = "4a624b08e65047d94768f9ada606a1c42a1a7c08e05fc1ed0be876f1606b2ab2"
RECORD_BINARY_SHA = "81bdb51d9c22fdffaeaa6bc2b7808f83d6106bf12d8a85d2ab501047ad8e8d17"
PROMPTS = {
    "prose": "Write a detailed technical explanation of how a B-tree index accelerates database range queries, covering node structure, fanout, height, and cache behavior.",
    "code": "Implement an LRU cache class in Python with O(1) get and put using a doubly linked list plus dict. Include docstrings and a small usage example.",
    "json": "Produce only a JSON array of 12 objects, fields name, priority (1-3), eta_minutes, describing the ordered steps of a server migration runbook. No prose outside the JSON.",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def request_json(port: int, path: str, payload: dict, timeout: int = 900) -> dict:
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())


def wait_healthy(port: int, process: subprocess.Popen) -> None:
    for _ in range(180):
        if process.poll() is not None:
            raise RuntimeError(f"server exited during startup with {process.returncode}")
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2)
            return
        except Exception:
            time.sleep(4)
    raise RuntimeError("server did not become healthy")


def sanitized_environment(runtime_env: dict[str, str]) -> dict[str, str]:
    env = dict(os.environ)
    for name in list(env):
        if name.startswith(("GGML_", "LLAMA_", "MUSE_", "UR_L0_")) or name == "ONEAPI_DEVICE_SELECTOR":
            del env[name]
    env.update(runtime_env)
    # Historical identity: despite its value, presence enables profiling in
    # this source. Preserve it only in this exact canonical replay.
    env["LLAMA_SPEC_PROFILE"] = "0"
    return env


def stop_server(process: subprocess.Popen) -> None:
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--draft", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument("--port", type=int, default=19494)
    parser.add_argument("--lock", type=Path, default=Path("/run/lock/muse-glimmer-gpu-exclusive.lock"))
    parser.add_argument("--require-record-binary", action="store_true")
    args = parser.parse_args()

    if args.out_dir.exists():
        raise SystemExit(f"refusing to overwrite {args.out_dir}")
    if sha256(args.target) != TARGET_SHA or args.target.stat().st_size != 32300651040:
        raise SystemExit("target model identity mismatch")
    if sha256(args.draft) != DRAFT_SHA or args.draft.stat().st_size != 5125206048:
        raise SystemExit("draft model identity mismatch")
    binary_sha = sha256(args.binary)
    if args.require_record_binary and binary_sha != RECORD_BINARY_SHA:
        raise SystemExit(f"record binary hash mismatch: {binary_sha}")

    recipe_root = Path(__file__).resolve().parent.parent
    runtime_env = json.loads((recipe_root / "configs/runtime-env.json").read_text())
    server_args = json.loads((recipe_root / "configs/server-args.json").read_text())
    env = sanitized_environment(runtime_env)

    args.lock.parent.mkdir(parents=True, exist_ok=True)
    lock_handle = args.lock.open("a+")
    try:
        fcntl.flock(lock_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as error:
        raise SystemExit("GPU host lock is busy") from error
    lock_handle.seek(0)
    lock_handle.truncate()
    lock_handle.write(f"muse-q8-canonical pid={os.getpid()} out={args.out_dir}\n")
    lock_handle.flush()

    args.out_dir.mkdir(parents=True)
    output_jsonl = args.out_dir / "canonical-full256.jsonl"
    summaries = []
    try:
        for run_number in range(1, args.runs + 1):
            run_dir = args.out_dir / f"run-{run_number}"
            run_dir.mkdir()
            port = args.port + run_number - 1
            command = [
                str(args.binary), "-m", str(args.target), "--alias", "muse-glimmer-30b-q8-woq",
                "--host", "127.0.0.1", "--port", str(port),
                *server_args,
                "--spec-draft-model", str(args.draft),
            ]
            (run_dir / "command.json").write_text(json.dumps(command, indent=2) + "\n")
            (run_dir / "runtime-env.json").write_text(json.dumps({
                **runtime_env,
                "LLAMA_SPEC_PROFILE": "0",
                "LLAMA_SPEC_PROFILE_EFFECTIVE": "enabled-by-presence",
            }, indent=2, sort_keys=True) + "\n")
            log_path = run_dir / "server.log"
            with log_path.open("w") as log:
                process = subprocess.Popen(
                    command, env=env, stdout=log, stderr=subprocess.STDOUT,
                    pass_fds=(lock_handle.fileno(),), start_new_session=True,
                )
            try:
                wait_healthy(port, process)
                row = {
                    "run": run_number,
                    "effective_spec_profile": True,
                    "prompts": {},
                }
                for name, prompt in PROMPTS.items():
                    messages = [
                        {"role": "system", "content": "Reasoning strength: low"},
                        {"role": "user", "content": prompt},
                    ]
                    template = request_json(port, "/apply-template", {"messages": messages}, 60)
                    response = request_json(port, "/completion", {
                        "prompt": template["prompt"],
                        "n_predict": 256,
                        "temperature": 0,
                        "cache_prompt": False,
                        "backend_sampling": True,
                        "samplers": ["temperature"],
                    })
                    timings = response["timings"]
                    if timings["predicted_n"] != 256:
                        raise RuntimeError(f"{name}: expected 256 tokens, got {timings['predicted_n']}")
                    row["prompts"][name] = {
                        "gen_tok_s": round(timings["predicted_per_second"], 3),
                        "predicted_n": timings["predicted_n"],
                        "draft_n": timings.get("draft_n", 0),
                        "draft_accepted": timings.get("draft_n_accepted", 0),
                        "text_sha": hashlib.sha256(response["content"].encode()).hexdigest()[:16],
                    }
                row["arithmetic_mean_tok_s"] = sum(
                    item["gen_tok_s"] for item in row["prompts"].values()
                ) / len(row["prompts"])
                with output_jsonl.open("a") as output:
                    output.write(json.dumps(row, sort_keys=True) + "\n")
                summaries.append(row)
            finally:
                stop_server(process)
            (run_dir / "server.log.sha256").write_text(f"{sha256(log_path)}  server.log\n")

        summary = {
            "schema": "muse-q8-woq-canonical-repro-v1",
            "binary_sha256": binary_sha,
            "target_sha256": TARGET_SHA,
            "draft_sha256": DRAFT_SHA,
            "runs": summaries,
            "both_above_100": all(row["arithmetic_mean_tok_s"] > 100 for row in summaries),
            "pooled_arithmetic_mean_tok_s": sum(
                row["arithmetic_mean_tok_s"] for row in summaries
            ) / len(summaries),
            "profiler_note": "LLAMA_SPEC_PROFILE=0 was present and therefore enabled profiling in the record source.",
        }
        (args.out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        if not summary["both_above_100"]:
            raise SystemExit("canonical gate failed: not every fresh run exceeded mean 100 tok/s")
        print(json.dumps(summary, indent=2))
    finally:
        lock_handle.close()


if __name__ == "__main__":
    main()
