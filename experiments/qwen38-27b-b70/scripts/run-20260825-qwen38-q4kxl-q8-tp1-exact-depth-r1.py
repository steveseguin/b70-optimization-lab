#!/usr/bin/env python3
"""Run the frozen Qwen3.8 UD-Q4_K_XL q8_0-KV exact-depth curve."""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Iterator


REPO = Path(__file__).resolve().parents[3]
LANE = REPO / "experiments/qwen38-27b-b70"
MANIFEST = LANE / "data/2026-08-25-qwen38-q4kxl-q8-tp1-exact-depth-prereg.json"
PARSER = REPO / "scripts/parse-llama-bench-exact-depth.py"
PROTECTED = LANE / "data/2026-08-23-qwen38-current-main-overlay-manifest.json"
EXPECTED_PARSER_SHA256 = (
    "bd32939350062e104a526536357e6f1055b683adc9c520c76e4e3d42e563f66e"
)
EXPECTED_PROTECTED_SHA256 = (
    "4eb3eeb81e40099a64ba0444743074e6b044295ff566c1abc11d864902abb454"
)
CAMPAIGN_ID = "qwen38-q4kxl-q8-tp1-exact-depth-20260825-r1"
ACK = f"RUN {CAMPAIGN_ID}"
SOURCE = Path("/home/steve/src/llama.cpp-q38-tp1-lane")
SOURCE_HEAD = "fa0f3b25a47f346858a4d0d169f5181aa424b110"
SUDO_PASSWORD = Path("/home/steve/SUDOPASSWORD.txt")
RENDER_LINK = Path("/dev/dri/by-path/pci-0000:23:00.0-render")
FORBIDDEN_ENV = re.compile(
    r"^(?:GGML_|LLAMA_|ONEAPI_|ZE_|ZES_|SYCL_|UR_|XPU_|CCL_|ONECCL_|"
    r"FI_|I_MPI_|MPI_|PMI_|PMIX_|VLLM_|LD_PRELOAD$|LD_LIBRARY_PATH$)"
)


class GateError(RuntimeError):
    """Raised when the frozen launch contract is not satisfied."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest() -> dict[str, Any]:
    try:
        value = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GateError(f"invalid campaign manifest: {exc}") from exc
    return value


def validate_manifest(value: dict[str, Any]) -> None:
    selectors = value.get("selectors") or {}
    runtime = value.get("runtime") or {}
    lifecycle = value.get("lifecycle") or {}
    interpretation = value.get("interpretation") or {}
    depths = [0, 2048, 4096, 8192, 16384, 24576, 32768]
    if not (
        value.get("schema") == "neural.download.qwen38-llama-exact-depth-prereg.v1"
        and value.get("campaign_id") == CAMPAIGN_ID
        and value.get("state") == "preregistered-not-launched"
        and selectors.get("tp") == 1
        and selectors.get("mtp") == 0
        and selectors.get("graph_mode") == "off"
        and selectors.get("kv") == "q8_0"
        and selectors.get("active_context_tokens") == depths
        and runtime.get("source_head") == SOURCE_HEAD
        and lifecycle.get("exact_ack") == ACK
        and lifecycle.get("output_fstype") == "ext4"
        and lifecycle.get("artifacts_are_create_only") is True
        and interpretation.get("speed_floor") is None
        and interpretation.get("http_serving_metric") is False
        and interpretation.get("new_quality_gate") is False
        and interpretation.get("historical_featured_speeds_are_immutable") is True
    ):
        raise GateError("campaign manifest invariant failed")
    argv = value.get("argv")
    expected = [
        runtime["binary"]["path"],
        "-m",
        value["model"]["path"],
        "-dev",
        "SYCL0",
        "-ngl",
        "99",
        "-sm",
        "layer",
        "-p",
        "2048",
        "-n",
        "128",
        "-d",
        "0,2048,4096,8192,16384,24576,32768",
        "-b",
        "2048",
        "-ub",
        "512",
        "-fa",
        "on",
        "-ctk",
        "q8_0",
        "-ctv",
        "q8_0",
        "-t",
        "16",
        "--poll",
        "50",
        "-r",
        "5",
        "-o",
        "json",
    ]
    if argv != expected:
        raise GateError("llama-bench argv differs from preregistration")
    libraries = runtime.get("effective_shared_libraries")
    if not isinstance(libraries, list) or len(libraries) != 32:
        raise GateError("exactly 32 effective shared-library rows are required")
    if len({row[0] for row in libraries if len(row) == 4}) != 32:
        raise GateError("shared-library inventory is malformed or duplicated")


def write_json_exclusive(path: Path, value: Any) -> None:
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(payload)


def reject_inherited_runtime_environment(environment: dict[str, str]) -> None:
    names = sorted(name for name in environment if FORBIDDEN_ENV.match(name))
    if names:
        raise GateError("forbidden inherited runtime variables: " + ", ".join(names))


def oneapi_environment(output: Path, knobs: dict[str, str]) -> dict[str, str]:
    command = [
        "/usr/bin/env",
        "-i",
        "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "HOME=/home/steve",
        "LANG=C.UTF-8",
        "LC_ALL=C.UTF-8",
        "/bin/bash",
        "-c",
        "set +u; source /opt/intel/oneapi/setvars.sh --force >/dev/null 2>&1; "
        "set -u; /usr/bin/env -0",
    ]
    result = subprocess.run(command, check=True, capture_output=True)
    environment: dict[str, str] = {}
    for item in result.stdout.decode().split("\0"):
        if item:
            name, separator, content = item.partition("=")
            if not separator:
                raise GateError("oneAPI environment contains an invalid entry")
            environment[name] = content
    environment.update(knobs)
    environment.update(
        {
            "HOME": str(output / "runtime-home"),
            "XDG_CACHE_HOME": str(output / "runtime-cache"),
            "SYCL_CACHE_DIR": str(output / "runtime-cache/sycl"),
            "TMPDIR": str(output / "runtime-tmp"),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
        }
    )
    return environment


def effective_libraries(binary: Path, environment: dict[str, str]) -> list[list[str]]:
    result = subprocess.run(
        ["/usr/bin/ldd", str(binary)],
        env=environment,
        check=True,
        text=True,
        capture_output=True,
    )
    rows: list[list[str]] = []
    for raw in result.stdout.splitlines():
        line = raw.strip()
        if not line or line.startswith("linux-vdso"):
            continue
        if " => " in line:
            soname, right = line.split(" => ", 1)
            reported = right.rsplit(" (", 1)[0]
            if reported == "not found":
                raise GateError(f"unresolved shared library: {soname}")
        elif line.startswith("/") and " (" in line:
            reported = line.rsplit(" (", 1)[0]
            soname = Path(reported).name
        else:
            raise GateError(f"unparsed ldd row: {line}")
        resolved = str(Path(reported).resolve(strict=True))
        rows.append([soname, reported, resolved, sha256_file(Path(resolved))])
    return rows


def git_output(*args: str, cwd: Path = REPO) -> str:
    return subprocess.check_output(["git", "-C", str(cwd), *args], text=True).strip()


def require_clean_pushed_main() -> str:
    if git_output("branch", "--show-current") != "main":
        raise GateError("lab repository must be on main")
    if git_output("status", "--porcelain=v1", "--untracked-files=all"):
        raise GateError("lab repository must be completely clean")
    head = git_output("rev-parse", "HEAD")
    if git_output("rev-parse", "origin/main") != head:
        raise GateError("lab main is not pushed to origin/main")
    remote = subprocess.check_output(
        [
            "timeout",
            "30s",
            "git",
            "-C",
            str(REPO),
            "ls-remote",
            "--exit-code",
            "origin",
            "refs/heads/main",
        ],
        text=True,
    ).split()[0]
    if remote != head:
        raise GateError("lab main differs from live origin/main")
    return head


def sudo_run(args: list[str]) -> subprocess.CompletedProcess[bytes]:
    if not SUDO_PASSWORD.is_file():
        raise GateError("sudo password file is unavailable")
    return subprocess.run(
        ["sudo", "-S", "-p", "", *args],
        input=SUDO_PASSWORD.read_bytes(),
        capture_output=True,
        check=False,
    )


def active_model_processes() -> list[str]:
    matches: list[str] = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit() or int(entry.name) == os.getpid():
            continue
        try:
            comm = (entry / "comm").read_text().strip()
            cmdline = (
                (entry / "cmdline")
                .read_bytes()
                .replace(b"\0", b" ")
                .decode(errors="replace")
            )
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        if comm in {"llama-bench", "llama-server"} or any(
            marker in cmdline
            for marker in (
                "vllm.entrypoints",
                "vllm serve",
                "VLLM::EngineCore",
            )
        ):
            matches.append(f"{entry.name}:{comm}")
    return matches


def require_idle() -> None:
    processes = active_model_processes()
    if processes:
        raise GateError("active model processes: " + ", ".join(processes))
    containers = sudo_run(["docker", "ps", "-q"])
    if containers.returncode != 0:
        raise GateError("could not verify Docker container state")
    if containers.stdout.strip():
        raise GateError("running Docker containers are present")
    if not RENDER_LINK.is_symlink() or RENDER_LINK.resolve().name != "renderD130":
        raise GateError("GPU0 render-node mapping changed")
    owner = sudo_run(["fuser", str(RENDER_LINK.resolve())])
    if owner.returncode == 0:
        raise GateError("GPU0 render node is owned by another process")
    if owner.returncode != 1:
        raise GateError("could not verify GPU0 render-node ownership")


@contextlib.contextmanager
def campaign_locks() -> Iterator[None]:
    paths = [
        Path("/run/lock/muse-glimmer-gpu-exclusive.lock"),
        Path("/tmp/b70-benchmark.lock"),
        Path(f"/run/user/{os.getuid()}/qwen36-b70-gpu-leases/gpu0.lock"),
    ]
    handles = []
    try:
        paths[-1].parent.mkdir(parents=True, exist_ok=True)
        for path in paths:
            handle = path.open("a+b")
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise GateError(f"campaign lock is held: {path}") from exc
            handles.append(handle)
        yield
    finally:
        for handle in reversed(handles):
            handle.close()


def static_check() -> dict[str, Any]:
    manifest = load_manifest()
    validate_manifest(manifest)
    if sha256_file(PARSER) != EXPECTED_PARSER_SHA256:
        raise GateError("exact-depth parser changed")
    if sha256_file(PROTECTED) != EXPECTED_PROTECTED_SHA256:
        raise GateError("protected historical speed manifest changed")
    return manifest


def preflight(manifest: dict[str, Any]) -> tuple[str, dict[str, str], list[list[str]]]:
    reject_inherited_runtime_environment(dict(os.environ))
    head = require_clean_pushed_main()
    if git_output("rev-parse", "HEAD", cwd=SOURCE) != SOURCE_HEAD:
        raise GateError("llama.cpp source HEAD changed")
    if git_output("status", "--porcelain=v1", "--untracked-files=all", cwd=SOURCE):
        raise GateError("llama.cpp source tree is not clean")
    model = Path(manifest["model"]["path"])
    binary = Path(manifest["runtime"]["binary"]["path"])
    if sha256_file(model) != manifest["model"]["sha256"]:
        raise GateError("model SHA-256 mismatch")
    if sha256_file(binary) != manifest["runtime"]["binary"]["sha256"]:
        raise GateError("llama-bench SHA-256 mismatch")
    output = Path(manifest["lifecycle"]["output_root"])
    if output.exists():
        raise GateError(f"output root already exists: {output}")
    parent = output.parent
    if not parent.is_dir():
        raise GateError(f"output parent is absent: {parent}")
    fstype = subprocess.check_output(
        ["findmnt", "-n", "-o", "FSTYPE", "--target", str(parent)], text=True
    ).strip()
    if fstype != "ext4":
        raise GateError(f"output parent must be ext4, got {fstype}")
    environment = oneapi_environment(output, manifest["environment"])
    libraries = effective_libraries(binary, environment)
    if libraries != manifest["runtime"]["effective_shared_libraries"]:
        raise GateError("effective shared-library inventory changed")
    require_idle()
    return head, environment, libraries


def metadata(manifest: dict[str, Any], libraries: list[list[str]]) -> dict[str, Any]:
    return {
        "schema": "llama-bench-exact-depth-metadata-v1",
        "receipt_id": CAMPAIGN_ID,
        "declared_depths": manifest["selectors"]["active_context_tokens"],
        "binary": {
            **manifest["runtime"]["binary"],
            "source_head": SOURCE_HEAD,
            "effective_shared_libraries": libraries,
        },
        "model": manifest["model"],
        "argv": manifest["argv"],
        "env": manifest["environment"],
        "cell_selectors": {
            key: value
            for key, value in manifest["selectors"].items()
            if key not in {"active_context_tokens", "graph_mode"}
        },
        "graph": {
            "requested": False,
            "capture": {"count": 0, "source": "GGML_SYCL_ENABLE_GRAPH=0"},
            "replay": {"count": 0, "source": "GGML_SYCL_ENABLE_GRAPH=0"},
        },
    }


def evidence_hashes(output: Path) -> dict[str, str]:
    return {
        path.name: sha256_file(path)
        for path in sorted(output.iterdir())
        if path.is_file() and path.name != "terminal-receipt.json"
    }


def execute(acknowledgement: str) -> int:
    if acknowledgement != ACK:
        raise GateError(f"exact acknowledgement required: {ACK}")
    manifest = static_check()
    output = Path(manifest["lifecycle"]["output_root"])
    state = "failed"
    error: str | None = None
    bench_rc: int | None = None
    parser_rc: int | None = None
    launched = False
    head = ""
    cleanup = False
    with campaign_locks():
        head, environment, libraries = preflight(manifest)
        output.mkdir(mode=0o700)
        for name in ("runtime-home", "runtime-cache/sycl", "runtime-tmp"):
            (output / name).mkdir(parents=True, exist_ok=False)
        write_json_exclusive(output / "metadata.json", metadata(manifest, libraries))
        write_json_exclusive(output / "effective-shared-libraries.json", libraries)
        launched = True
        try:
            with (
                (output / "llama-bench.json").open("xb") as stdout,
                (output / "llama-bench.stderr.log").open("xb") as stderr,
            ):
                result = subprocess.run(
                    manifest["argv"],
                    cwd=REPO,
                    env=environment,
                    stdout=stdout,
                    stderr=stderr,
                    timeout=manifest["lifecycle"]["timeout_seconds"],
                    check=False,
                )
            bench_rc = result.returncode
            if bench_rc != 0:
                raise GateError(f"llama-bench exited {bench_rc}")
            parser = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(PARSER),
                    "--bench-json",
                    str(output / "llama-bench.json"),
                    "--metadata",
                    str(output / "metadata.json"),
                    "--output",
                    str(output / "exact-depth-receipt.json"),
                    "--create",
                ],
                cwd=REPO,
                text=True,
                capture_output=True,
                check=False,
            )
            parser_rc = parser.returncode
            with (output / "parser.stdout.json").open("x", encoding="utf-8") as stream:
                stream.write(parser.stdout)
            with (output / "parser.stderr.log").open("x", encoding="utf-8") as stream:
                stream.write(parser.stderr)
            if parser_rc != 0:
                raise GateError(f"exact-depth parser exited {parser_rc}")
            receipt = json.loads((output / "exact-depth-receipt.json").read_text())
            if not (
                receipt.get("status") == "passed"
                and (receipt.get("gate") or {}).get("exact_cell_ready") is True
                and len(receipt.get("cells") or []) == 7
            ):
                raise GateError("exact-depth receipt did not pass all seven cells")
            require_idle()
            cleanup = True
            state = "passed"
        except (
            GateError,
            OSError,
            subprocess.SubprocessError,
            json.JSONDecodeError,
        ) as exc:
            error = str(exc)
            try:
                require_idle()
                cleanup = True
            except GateError as cleanup_exc:
                cleanup = False
                error = f"{error}; cleanup: {cleanup_exc}"
        terminal = {
            "schema": "neural.download.qwen38-llama-exact-depth-terminal.v1",
            "campaign_id": CAMPAIGN_ID,
            "terminal": True,
            "state": state,
            "created_at_utc": dt.datetime.now(dt.UTC).isoformat(),
            "lab_git_head": head,
            "launched": launched,
            "bench_return_code": bench_rc,
            "parser_return_code": parser_rc,
            "cleanup_passed": cleanup,
            "error": error,
            "speed_floor": None,
            "new_quality_gate": False,
            "historical_featured_speeds_are_immutable": True,
            "evidence_sha256": evidence_hashes(output),
        }
        write_json_exclusive(output / "terminal-receipt.json", terminal)
    print(json.dumps(terminal, indent=2, sort_keys=True))
    return 0 if state == "passed" else 20


def plan(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "campaign_id": CAMPAIGN_ID,
        "state": "preregistered-not-launched",
        "default_is_inert": True,
        "output_root": manifest["lifecycle"]["output_root"],
        "argv": manifest["argv"],
        "ack": ACK,
        "speed_floor": None,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--ack", default="")
    args = parser.parse_args(argv)
    try:
        manifest = static_check()
        if args.check:
            print(
                json.dumps(
                    {"status": "PASS", "launched": False, **plan(manifest)},
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        if args.execute:
            return execute(args.ack)
        print(json.dumps(plan(manifest), indent=2, sort_keys=True))
        return 0
    except (
        GateError,
        OSError,
        subprocess.SubprocessError,
        json.JSONDecodeError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
