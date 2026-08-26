#!/usr/bin/env python3
"""Create-only runner for embedded-Q8 MTP3/F16 TP1 exact-depth R1."""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from typing import Any
from types import SimpleNamespace


REPO = Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen36-27b-mtp-gguf-q4-b70"
MANIFEST = LANE / "data/2026-08-25-qwen36-mtpq8-f16-tp1-mtp3-exact-depth-r1-prereg.json"
VALIDATOR = LANE / "scripts/validate-20260825-qwen36-mtpq8-f16-tp1-mtp3-exact-depth-r1.py"
CAMPAIGN_ID = "qwen36-mtpq8-f16-tp1-mtp3-exact-depth-20260825-r1"
ACK = f"RUN {CAMPAIGN_ID}"
DEPTHS = (0, 2048, 4096, 8192, 16384, 24576, 32768)
ACCEPTANCE_RE = re.compile(r"draft acceptance\s*=\s*([0-9.]+)\s*\(\s*(\d+) accepted\s*/\s*(\d+) generated\)")


class GateError(RuntimeError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise GateError(f"JSON root is not an object: {path}")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(8 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def write_json_x(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def verify_file(path: Path, expected_sha: str, expected_size: int | None = None,
                *, allow_symlink: bool = False) -> None:
    if not path.is_file() or (path.is_symlink() and not allow_symlink):
        raise GateError(f"missing or symlinked identity file: {path}")
    if expected_size is not None and path.stat().st_size != expected_size:
        raise GateError(f"size mismatch: {path}")
    if sha256_file(path) != expected_sha:
        raise GateError(f"SHA-256 mismatch: {path}")


def validate_manifest(value: dict[str, Any]) -> None:
    selectors = value.get("selectors") or {}
    runtime = value.get("runtime") or {}
    server = value.get("server_contract") or {}
    frozen = value.get("frozen_interpretation") or {}
    if not (
        value.get("schema") == "neural.download.qwen36-llama-mtp3-exact-depth-prereg.v1"
        and value.get("campaign_id") == CAMPAIGN_ID
        and value.get("state") == "preregistered-not-launched"
        and selectors.get("active_context_tokens") == list(DEPTHS)
        and selectors.get("candidate_mtp") == 3
        and selectors.get("control_mtp") == 0
        and selectors.get("graph_mode") == "off"
        and selectors.get("target_kv") == selectors.get("draft_kv") == "f16"
        and server.get("context_capacity") >= max(DEPTHS) + 128
        and len(runtime.get("effective_local_shared_libraries") or []) == 8
        and frozen.get("speed_floor") is None
        and frozen.get("cell_gain_if_all_gates_pass") == 7
        and frozen.get("graph_claim_authorized") is False
        and frozen.get("site_or_family_edit_authorized_before_result_and_quality_review") is False
    ):
        raise GateError("manifest invariant failed")


def referenced_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPO / path


def load_depth_client(path: Path):
    spec = importlib.util.spec_from_file_location("qwen36_mtp3_depth_client", path)
    if spec is None or spec.loader is None:
        raise GateError("cannot import exact-depth client")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def static_check(manifest: dict[str, Any]) -> dict[str, Any]:
    validate_manifest(manifest)
    runtime = manifest["runtime"]
    model = manifest["model"]
    fixture = manifest["fixture"]
    clients = manifest["clients"]
    verify_file(referenced_path(runtime["manifest"]), runtime["manifest_sha256"])
    verify_file(referenced_path(model["artifact_manifest"]), model["artifact_manifest_sha256"])
    verify_file(Path(runtime["binary"]), runtime["binary_sha256"], runtime["binary_size_bytes"])
    for row in runtime["effective_local_shared_libraries"]:
        verify_file(Path(row["path"]), row["sha256"], row["size_bytes"])
    verify_file(referenced_path(fixture["path"]), fixture["sha256"])
    verify_file(referenced_path(clients["exact_depth"]["path"]), clients["exact_depth"]["sha256"])
    verify_file(referenced_path(clients["quality"]["path"]), clients["quality"]["sha256"])
    verify_file(Path(clients["quality"]["interpreter"]), clients["quality"]["interpreter_sha256"], allow_symlink=True)
    model_path = Path(model["path"])
    if not model_path.is_file() or model_path.is_symlink() or model_path.stat().st_size != model["size_bytes"]:
        raise GateError("model path/size identity failed (full model hash is execute-only)")
    depth_client_path = referenced_path(clients["exact_depth"]["path"])
    depth_module = load_depth_client(depth_client_path)
    depth_module.load_fixture(referenced_path(fixture["path"]), 0, "depth-0")
    for depth in DEPTHS[1:]:
        command = [sys.executable, "-B", str(referenced_path(clients["exact_depth"]["path"])), "--check",
                   "--fixture", str(referenced_path(fixture["path"])), "--depth", str(depth),
                   "--case-id", f"depth-{depth}", "--context-capacity", str(manifest["server_contract"]["context_capacity"]),
                   "--model", manifest["server_contract"]["model_alias"], "--response-adapter", "llama-server"]
        subprocess.run(command, cwd=REPO, check=True, stdout=subprocess.DEVNULL)
    return {"schema": "neural.download.qwen36-llama-mtp3-exact-depth-plan.v1", "mode": "check",
            "default_is_inert": True, "gpu_actions": 0, "network_requests": 0,
            "output_writes": 0, "campaign_id": CAMPAIGN_ID, "exact_ack": ACK,
            "depths": list(DEPTHS), "arms": ["control-mtp0", "candidate-mtp3"]}


def active_model_processes() -> list[str]:
    result: list[str] = []
    llama = {"llama-bench", "llama-batched-bench", "llama-batched-b", "llama-server"}
    engines = {"VLLM::EngineCore", "VLLM::EngineCor"}
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            comm = (entry / "comm").read_text().strip()
            argv = [part.decode(errors="replace") for part in (entry / "cmdline").read_bytes().split(b"\0") if part]
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        argv0 = Path(argv[0]).name if argv else ""
        is_vllm = (comm in engines or argv0 in engines or (argv0 == "vllm" and len(argv) > 1 and argv[1] == "serve")
                   or (argv0.startswith("python") and any(item == "-m" and i + 1 < len(argv) and argv[i + 1].startswith("vllm.entrypoints") for i, item in enumerate(argv))))
        if comm in llama or argv0 in llama or is_vllm:
            result.append(f"{entry.name}:{comm}")
    return result


def port_open(port: int) -> bool:
    with socket.socket() as sock:
        sock.settimeout(0.3)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def render_busy(render: str) -> bool:
    return subprocess.run(["fuser", render], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def oneapi_environment(runtime_dir: Path) -> dict[str, str]:
    command = "set -a; source /opt/intel/oneapi/setvars.sh --force >/dev/null; env -0"
    raw = subprocess.run(["bash", "-c", command], check=True, stdout=subprocess.PIPE).stdout
    env = {part.split(b"=", 1)[0].decode(): part.split(b"=", 1)[1].decode(errors="surrogateescape") for part in raw.split(b"\0") if b"=" in part}
    env["LD_LIBRARY_PATH"] = str(runtime_dir) + (":" + env["LD_LIBRARY_PATH"] if env.get("LD_LIBRARY_PATH") else "")
    env.update({
        "ONEAPI_DEVICE_SELECTOR": "level_zero:*", "ZE_AFFINITY_MASK": "0", "ZES_ENABLE_SYSMAN": "1",
        "UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS": "1", "GGML_SYCL_ENABLE_VMM": "1",
        "GGML_SYCL_ENABLE_GRAPH": "0", "GGML_SYCL_GRAPH_CACHE_SIZE": "0", "GGML_SYCL_ENABLE_DNN": "0",
        "GGML_SYCL_ENABLE_OPT": "1", "GGML_SYCL_FA_ONEDNN": "1", "GGML_SYCL_FA_ONEDNN_MAX_KV": "0",
        "GGML_SYCL_ENABLE_MKL_FA": "1", "GGML_SYCL_ENABLE_FLASH_ATTN": "1",
        "NO_PROXY": "127.0.0.1,localhost", "no_proxy": "127.0.0.1,localhost",
    })
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        env.pop(name, None)
    return env


def acceptance_rows(log: Path) -> list[dict[str, Any]]:
    text = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
    return [{"ratio": float(m.group(1)), "accepted": int(m.group(2)), "generated": int(m.group(3))} for m in ACCEPTANCE_RE.finditer(text)]


class Execution:
    def __init__(self, manifest: dict[str, Any]):
        self.m = manifest
        self.root = Path(manifest["lifecycle"]["output_root"])
        self.port = manifest["server_contract"]["port"]
        self.render = manifest["lifecycle"]["requires_idle_gpu0_render_node"]
        self.proc: subprocess.Popen[bytes] | None = None
        self.log_stream: Any = None
        self.lock_streams: list[Any] = []

    def require_idle(self) -> None:
        busy = active_model_processes()
        if busy:
            raise GateError("active model processes: " + ",".join(busy))
        if subprocess.run(["docker", "ps", "-q"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL).stdout.strip():
            raise GateError("active container")
        if not Path(self.render).exists() or render_busy(self.render):
            raise GateError("GPU0 render node missing or busy")
        if port_open(self.port):
            raise GateError("campaign port is busy")

    def acquire_locks(self) -> None:
        for name in self.m["lifecycle"]["required_locks"]:
            path = Path(name); path.parent.mkdir(parents=True, exist_ok=True)
            stream = path.open("a+")
            try: fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc: raise GateError(f"lock held: {path}") from exc
            self.lock_streams.append(stream)

    def server_argv(self, candidate: bool) -> list[str]:
        s, model = self.m["server_contract"], self.m["model"]
        argv = [self.m["runtime"]["binary"], "-m", model["path"], "--alias", s["model_alias"], "--host", s["host"], "--port", str(s["port"]),
                "-dev", "SYCL0", "-ngl", "all", "-c", str(s["context_capacity"]), "-np", "1", "-b", "1024", "-ub", "1024", "-t", "8",
                "--threads-http", "6", "--poll", "50", "-lv", "4", "-ctk", "f16", "-ctv", "f16", "-fa", "on", "-fit", "on", "-fitt", "1024"]
        argv += (["--spec-type", "draft-mtp", "--spec-draft-n-max", "3", "--spec-draft-n-min", "0", "--spec-draft-p-split", "0.10", "--spec-draft-p-min", "0.00", "--spec-draft-backend-sampling", "--spec-draft-device", "SYCL0", "--spec-draft-ngl", "all", "--spec-draft-type-k", "f16", "--spec-draft-type-v", "f16"] if candidate else ["--spec-type", "none"])
        argv += ["--reasoning", "off", "--ctx-checkpoints", "0", "--cache-ram", "0", "--no-cache-idle-slots", "--no-context-shift", "--slots", "--metrics", "--jinja", "--no-kv-unified", "--cont-batching", "--no-webui"]
        return argv

    def start(self, arm: str, argv: list[str], env: dict[str, str]) -> None:
        arm_dir = self.root / arm; arm_dir.mkdir()
        self.log_stream = (arm_dir / "server.log").open("xb")
        self.proc = subprocess.Popen(argv, cwd=REPO, env=env, stdout=self.log_stream, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + 900
        url = f"http://127.0.0.1:{self.port}/v1/models"
        while time.monotonic() < deadline:
            if self.proc.poll() is not None: raise GateError(f"{arm} server exited before readiness")
            try:
                with urllib.request.urlopen(url, timeout=5) as response: payload = json.loads(response.read())
                rows = payload.get("data") if isinstance(payload, dict) else None
                if isinstance(rows, list) and any(isinstance(row, dict) and row.get("id") == self.m["server_contract"]["model_alias"] for row in rows):
                    write_json_x(arm_dir / "models.json", payload); return
            except Exception: pass
            time.sleep(2)
        raise GateError(f"{arm} readiness timeout")

    def stop(self, arm: str) -> dict[str, bool]:
        forced = False
        if self.proc is not None and self.proc.poll() is None:
            self.proc.terminate()
            try: self.proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                forced = True; self.proc.kill()
                try: self.proc.wait(timeout=10)
                except subprocess.TimeoutExpired: pass
        survivor = self.proc is not None and self.proc.poll() is None
        if self.log_stream is not None: self.log_stream.close()
        self.proc = None; self.log_stream = None
        deadline = time.monotonic() + 10
        while port_open(self.port) and time.monotonic() < deadline: time.sleep(0.2)
        result = {"forced_kill": forced, "port_closed": not port_open(self.port), "render_node_idle": not render_busy(self.render), "server_survivor": survivor}
        path = self.root / arm / "cleanup.json"
        if not path.exists(): write_json_x(path, result)
        return result

    def run_depth(self, arm: str, depth: int, candidate: bool) -> None:
        directory = self.root / arm / f"depth-{depth}"; directory.mkdir()
        before = len(acceptance_rows(self.root / arm / "server.log")) if candidate else 0
        client_path = referenced_path(self.m["clients"]["exact_depth"]["path"])
        fixture_path = referenced_path(self.m["fixture"]["path"])
        if depth == 0:
            module = load_depth_client(client_path)
            selected = module.load_fixture(fixture_path, 0, "depth-0")
            args = SimpleNamespace(
                base_url=f"http://127.0.0.1:{self.port}",
                model=self.m["server_contract"]["model_alias"],
                response_adapter="llama-server",
                timeout=self.m["lifecycle"]["request_timeout_seconds"],
                context_capacity=self.m["server_contract"]["context_capacity"],
                out=directory / "exact-depth.json",
            )
            with (directory / "exact-depth.stdout.json").open("x", encoding="utf-8") as stdout, contextlib.redirect_stdout(stdout):
                if module.execute(args, selected) != 0:
                    raise GateError("depth-0 exact client failed")
        else:
            command = [sys.executable, "-B", str(client_path), "--execute", "--fixture", str(fixture_path),
                       "--depth", str(depth), "--case-id", f"depth-{depth}", "--context-capacity", str(self.m["server_contract"]["context_capacity"]),
                       "--base-url", f"http://127.0.0.1:{self.port}", "--model", self.m["server_contract"]["model_alias"], "--response-adapter", "llama-server",
                       "--timeout", str(self.m["lifecycle"]["request_timeout_seconds"]), "--out", str(directory / "exact-depth.json")]
            with (directory / "exact-depth.stdout.json").open("xb") as stdout:
                subprocess.run(command, cwd=REPO, check=True, stdout=stdout)
        if candidate:
            deadline = time.monotonic() + 30; rows = acceptance_rows(self.root / arm / "server.log")
            while len(rows) <= before and time.monotonic() < deadline:
                time.sleep(0.2); rows = acceptance_rows(self.root / arm / "server.log")
            write_json_x(directory / "draft-counters.json", {"depth": depth, "rows_before": before, "rows_after": len(rows), "new_rows": rows[before:]})


def execute(manifest: dict[str, Any]) -> Path:
    validate_manifest(manifest)
    unexpected = [name for name in os.environ if name.startswith(("GGML_", "SYCL_", "ZE_", "ZES_", "UR_", "ONEAPI_DEVICE_SELECTOR", "LLAMA_ARG_")) or name == "LD_PRELOAD"]
    if unexpected: raise GateError("unexpected inherited runtime environment: " + ",".join(sorted(unexpected)))
    subprocess.run(["git", "fetch", "origin", "main", "--quiet"], cwd=REPO, check=True)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    origin = subprocess.check_output(["git", "rev-parse", "origin/main"], cwd=REPO, text=True).strip()
    if head != origin or subprocess.check_output(["git", "status", "--porcelain"], cwd=REPO, text=True).strip():
        raise GateError("execution requires clean pushed main")
    run = Execution(manifest); run.acquire_locks(); run.require_idle()
    if run.root.exists(): raise GateError(f"create-only root exists: {run.root}")
    run.root.parent.mkdir(parents=True, exist_ok=True)
    if subprocess.check_output(["findmnt", "-no", "FSTYPE", "--target", str(run.root.parent)], text=True).strip() != "ext4": raise GateError("run-root parent must be ext4")
    run.root.mkdir()
    try:
        model, runtime = manifest["model"], manifest["runtime"]
        verify_file(Path(model["path"]), model["sha256"], model["size_bytes"])
        static_check(manifest)
        env = oneapi_environment(Path(runtime["binary"]).parent)
        version = subprocess.check_output([runtime["binary"], "--version"], env=env, stderr=subprocess.STDOUT, text=True).strip()
        if runtime["reported_version"] not in version.splitlines(): raise GateError("runtime version drift")
        help_text = subprocess.check_output([runtime["binary"], "--help"], env=env, stderr=subprocess.STDOUT, text=True)
        if "draft-mtp" not in help_text: raise GateError("runtime lacks draft-mtp")
        ldd = subprocess.check_output(["ldd", runtime["binary"]], env=env, text=True)
        captured = []
        for row in runtime["effective_local_shared_libraries"]:
            match = re.search(rf"^{re.escape(row['soname'])}\s+=>\s+(\S+)", ldd, re.M)
            if not match or str(Path(match.group(1)).resolve()) != str(Path(row["path"]).resolve()): raise GateError(f"ldd closure mismatch: {row['soname']}")
            captured.append(row)
        local_names = sorted({line.split()[0] for line in ldd.splitlines() if " => " in line and line.split()[2].startswith(str(Path(runtime["binary"]).parent) + "/")})
        if local_names != sorted(row["soname"] for row in captured): raise GateError("unexpected runtime-origin DSO")
        control_argv, candidate_argv = run.server_argv(False), run.server_argv(True)
        identity = {"campaign_id": CAMPAIGN_ID, "created_at_utc": dt.datetime.now(dt.UTC).isoformat(), "git_head": head, "origin_main": origin,
                    "model": {"path": model["path"], "size_bytes": model["size_bytes"], "sha256": model["sha256"], "repository": model["repository"], "revision": model["revision"]},
                    "runtime": {"binary": runtime["binary"], "binary_sha256": runtime["binary_sha256"], "manifest": runtime["manifest"], "manifest_sha256": runtime["manifest_sha256"], "source_commit": runtime["source_commit"], "version": version, "local_dsos": captured, "ldd": ldd.splitlines()},
                    "fixture_sha256": manifest["fixture"]["sha256"], "server_argv": {"control-mtp0": control_argv, "candidate-mtp3": candidate_argv},
                    "runtime_environment": {key: env[key] for key in ("ONEAPI_DEVICE_SELECTOR", "ZE_AFFINITY_MASK", "GGML_SYCL_ENABLE_GRAPH", "GGML_SYCL_GRAPH_CACHE_SIZE", "GGML_SYCL_ENABLE_DNN", "GGML_SYCL_ENABLE_OPT", "GGML_SYCL_ENABLE_VMM")}}
        write_json_x(run.root / "identity.json", identity)
        for arm, candidate, argv in (("control-mtp0", False, control_argv), ("candidate-mtp3", True, candidate_argv)):
            run.require_idle(); run.start(arm, argv, env)
            try:
                for depth in DEPTHS: run.run_depth(arm, depth, candidate)
                if candidate:
                    q = manifest["clients"]["quality"]
                    command = [q["interpreter"], "-I", "-B", str(referenced_path(q["path"])), "--base-url", f"http://127.0.0.1:{run.port}", "--model", manifest["server_contract"]["model_alias"],
                               "--tokenizer", q["tokenizer_path"], "--timeout", str(manifest["lifecycle"]["request_timeout_seconds"]), "--repeat-runs", str(q["repeat_runs"]),
                               "--long-context-tokens", str(q["long_context_tokens"]), "--request-id-prefix", "qwen36-mtpq8-mtp3-depth-r1", "--output-json", str(run.root / arm / "quality.json")]
                    with (run.root / arm / "quality.stdout.json").open("xb") as stdout, (run.root / arm / "quality.stderr.log").open("xb") as stderr:
                        subprocess.run(command, cwd=REPO, check=True, stdout=stdout, stderr=stderr)
            finally:
                cleanup = run.stop(arm)
                if cleanup != {"forced_kill": False, "port_closed": True, "render_node_idle": True, "server_survivor": False}: raise GateError(f"{arm} cleanup failed: {cleanup}")
        terminal = run.root / "terminal-receipt.json"
        subprocess.run([sys.executable, "-B", str(VALIDATOR), "--root", str(run.root), "--manifest", str(MANIFEST), "--output", str(terminal)], cwd=REPO, check=True,
                       stdout=(run.root / "validator.stdout.json").open("xb"))
        return terminal
    except BaseException as exc:
        if run.proc is not None:
            try: run.stop("interrupted-arm")
            except Exception: pass
        terminal = run.root / "terminal-receipt.json"
        if not terminal.exists():
            write_json_x(terminal, {"schema": "neural.download.qwen36-llama-mtp3-exact-depth-terminal.v1", "campaign_id": CAMPAIGN_ID,
                                    "created_at_utc": dt.datetime.now(dt.UTC).isoformat(), "status": "failed-preserve-do-not-publish", "error": f"{type(exc).__name__}: {exc}",
                                    "authority": {"matrix_cells": 0, "site_publication": False, "speed_claim": False}})
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--ack", default="")
    args = parser.parse_args()
    if args.check and args.execute: parser.error("choose --check or --execute")
    try:
        manifest = load_json(MANIFEST)
        if not args.execute:
            print(json.dumps(static_check(manifest), indent=2, sort_keys=True)); return 0
        if args.ack != ACK: raise GateError(f"exact --ack required: {ACK}")
        print(execute(manifest)); return 0
    except (GateError, OSError, ValueError, json.JSONDecodeError, subprocess.SubprocessError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
