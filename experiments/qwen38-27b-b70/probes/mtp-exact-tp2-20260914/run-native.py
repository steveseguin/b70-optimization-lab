#!/usr/bin/env python3
"""Own exactly one isolated TP2 operator container, with fault monitoring.

--check-only is CPU/files only. Normal mode is reserved for the root agent's
exclusive native window; it never stops another service or retries a launch.
"""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import uuid

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
IMAGE = "sha256:506fcc26897b12915cb9e27c28e0adc256d278666fa745602a1ae5e1dd8ea066"
IDENTITY = Path("/mnt/fast-ai/bench-results/amd-transfer-fp8-20260914/control-identity.json")
RUNTIME_REFERENCE = Path("/mnt/fast-ai/bench-results/amd-transfer-fp8-20260914/restored-service/container-inspect.json")
FILES = ("exact_tp2.cpp", "native.py", "protocol.py", "gate.py", "analyze.py", "run-native.py", "cpu-validation.json")


def runtime_contract(reference):
    """CPU-only admission of the qualified oneCCL transport, IPC and selector."""
    if isinstance(reference, list):
        if len(reference) != 1:
            raise ValueError("expected one qualified container reference")
        reference = reference[0]
    host = reference["HostConfig"]
    required = {"NetworkMode": "bridge", "IpcMode": "host", "CapAdd": ["CAP_SYS_PTRACE"],
                "SecurityOpt": ["label=disable"], "GroupAdd": ["render"], "Privileged": False,
                "Devices": [{"PathOnHost": "/dev/dri", "PathInContainer": "/dev/dri", "CgroupPermissions": "rwm"}],
                "ShmSize": 8589934592, "Ulimits": [{"Name": "core", "Hard": 0, "Soft": 0}]}
    if any(host.get(k) != v for k, v in required.items()):
        raise ValueError("qualified container hardware/transport settings changed")
    env = {k: v for entry in reference["Config"]["Env"] for k, v in [entry.split("=", 1)]
           if k.startswith(("CCL_", "ONECCL_", "ONEAPI_", "SYCL_", "ZE_", "UR_", "TORCH_", "OMP_", "MKL_", "KMP_"))}
    expected = {"CCL_TOPO_P2P_ACCESS": "1", "CCL_RECV": "direct", "CCL_SEND": "direct",
                "CCL_ZE_IPC_EXCHANGE": "pidfd", "ZE_AFFINITY_MASK": "0,1",
                "CCL_ATL_TRANSPORT": "ofi", "ONEAPI_DEVICE_SELECTOR": "level_zero:0,1",
                "CCL_SYCL_ALLGATHERV_SIMPLE_THRESHOLD": "4294967296",
                "CCL_SYCL_REDUCE_SCATTER_SIMPLE_THRESHOLD": "4294967296",
                "CCL_SYCL_ALLREDUCE_SIMPLE_THRESHOLD": "4294967296"}
    if any(env.get(k) != v for k, v in expected.items()):
        raise ValueError("qualified oneCCL transport/IPC/selector environment changed")
    return {"host_config": required, "env": env}


def hardware_argv():
    return ["--network", "bridge", "--device", "/dev/dri", "--group-add", "render",
            "--ipc", "host", "--cap-add", "SYS_PTRACE", "--shm-size", "8g",
            "--ulimit", "core=0", "--security-opt", "label=disable"]


def operator_argv():
    # Explicit static loopback rendezvous avoids --standalone's container-
    # hostname discovery. No worker or rendezvous restart policy is enabled.
    return [IMAGE, "--nnodes=1", "--node-rank=0", "--nproc-per-node=2",
            "--master-addr=127.0.0.1", "--master-port=29500", "--max-restarts=0",
            "/probe/gate.py", "--library", "/probe/libexact_tp2.so", "--out", "/results",
            "--rows", "1,2,512,4096", "--blocks", "5", "--iterations", "12",
            "--timeout", "15", "--admitted-exclusive-gpu-test"]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write(path, value):
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n"); stream.flush(); os.fsync(stream.fileno())
    tmp.replace(path)


def inputs(library):
    blobs = {name: (HERE / name).read_bytes() for name in FILES}
    for name, data in blobs.items():
        if name.endswith(".py"):
            compile(data, name, "exec")
    receipt = json.loads(blobs["cpu-validation.json"])
    checked_sources = {x["path"]: x["sha256"] for x in receipt["sources"]}
    for name in ("exact_tp2.cpp", "native.py", "protocol.py", "gate.py"):
        if checked_sources.get(name) != sha(blobs[name]):
            raise RuntimeError(f"CPU-checked source drift: {name}")
    blobs["libexact_tp2.so"] = library.read_bytes()
    if not any(b["library_sha256"] == sha(blobs["libexact_tp2.so"]) and b["source_sha256"] == sha(blobs["exact_tp2.cpp"]) for b in receipt["builds"]):
        raise RuntimeError("native library does not match a CPU build receipt")
    raw_reference = RUNTIME_REFERENCE.read_bytes()
    contract = runtime_contract(json.loads(raw_reference))
    contract["reference_sha256"] = sha(raw_reference)
    contract["reference_path"] = str(RUNTIME_REFERENCE)
    blobs["qualified-runtime-contract.json"] = (json.dumps(contract, indent=2) + "\n").encode()
    return blobs


def freeze(out, blobs):
    snapshot = out / "snapshot"
    snapshot.mkdir(exist_ok=False)
    manifest = {}
    for name, data in blobs.items():
        target = snapshot / name
        with target.open("xb") as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        target.chmod(0o444)
        manifest[name] = {"sha256": sha(data), "bytes": len(data)}
    snapshot.chmod(0o555)
    write(out / "snapshot-manifest.json", manifest)
    return snapshot


def owned(info, state):
    if info["Name"].lstrip("/") != state["name"] or info["Image"] != IMAGE or (state.get("container_id") and state["container_id"] != info["Id"]):
        raise RuntimeError("container ownership mismatch; refusing operation")
    state["container_id"] = info["Id"]


def finish_owned(helper, child, out, state):
    receipt = {"at": helper.now(), "stop_attempted": False, "confirmed": False, "errors": []}
    try:
        info = helper.inspect_container(state.get("container_id") or state["name"])
        if info:
            owned(info, state)
            if info["State"]["Running"]:
                receipt["stop_attempted"] = True
                # Exactly one owned-ID stop. No kill, reset, restart or retry.
                try:
                    stopped = helper.run(["docker", "stop", "--time", "30", info["Id"]], check=False, timeout=45)
                    receipt.update(stop_returncode=stopped.returncode, stop_stdout=stopped.stdout, stop_stderr=stopped.stderr)
                except Exception as exc:
                    receipt["errors"].append(repr(exc))
            info = helper.inspect_container(info["Id"])
            if info:
                owned(info, state)
                write(out / "container-final.json", info)
                receipt["confirmed"] = not info["State"]["Running"]
                receipt["container_exit_code"] = info["State"]["ExitCode"]
                receipt["oom_killed"] = info["State"]["OOMKilled"]
            else:
                receipt["confirmed"] = True
        else:
            receipt["confirmed"] = child is None or child.poll() is not None
        if child is not None:
            try:
                receipt["attach_exit_code"] = child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                receipt["confirmed"] = False
                receipt["errors"].append("Docker attach exit unconfirmed")
    except Exception as exc:
        receipt["confirmed"] = False
        receipt["errors"].append(repr(exc))
    write(out / "stop.json", receipt)
    if not receipt["confirmed"]:
        (out / "STOP_UNCONFIRMED").write_text("No successor until owned container/client exit is confirmed.\n")
    return receipt


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--library", type=Path, default=Path("/tmp/mtp-exact-tp2-build-20260914/libexact_tp2.so"))
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--check-only", action="store_true")
    args = ap.parse_args()
    if not 30 <= args.timeout <= 1200:
        raise ValueError("bounded timeout must be 30–1200 seconds")
    out = args.out.resolve()
    if out.name not in ("communication-native-01", "communication-native-02", "communication-native-03"):
        raise ValueError("only the original or explicitly corrected one-shot stage is admitted")
    if out.exists() or (out.parent / "FAULT.json").exists():
        raise RuntimeError("output exists or campaign GPU fault latch is set; no retry")
    blobs = inputs(args.library)
    if args.check_only:
        print(json.dumps({"status": "CPU-only input admission passed", "image": IMAGE,
                          "out": str(out), "gpu_discovery": False,
                          "hashes": {k: sha(v) for k, v in blobs.items()}}, indent=2))
        return
    spec = importlib.util.spec_from_file_location("qualified_serve_helper", ROOT / "packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py")
    helper = importlib.util.module_from_spec(spec); spec.loader.exec_module(helper)
    with open("/tmp/qwen-short-prefill-stage.lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        name = "mtp-exact-tp2-" + uuid.uuid4().hex
        helper.check_available(18130, name)
        started = helper.now()
        helper.journal(started)  # Require readable fault evidence before launch.
        image = json.loads(helper.run(["docker", "image", "inspect", IMAGE]).stdout)
        if len(image) != 1 or image[0]["Id"] != IMAGE:
            raise RuntimeError("immutable control image identity mismatch")
        out.mkdir(parents=True, exist_ok=False)
        snapshot = freeze(out, blobs)
        results = out / "results"; results.mkdir()
        write(out / "image.json", image)
        contract = json.loads(blobs["qualified-runtime-contract.json"])
        env = dict(contract["env"])
        env.update(PYTHONUNBUFFERED="1", OMP_NUM_THREADS="1")
        cmd = ["docker", "create", "--name", name, "--restart", "no"] + hardware_argv() + [
               "--memory", "6g", "--memory-swap", "8g", "--workdir", "/probe",
               "--mount", f"type=bind,source={snapshot},target=/probe,readonly",
               "--mount", f"type=bind,source={results},target=/results",
               "--entrypoint", "/opt/venv/bin/torchrun"]
        for key, value in sorted(env.items()):
            cmd += ["--env", f"{key}={value}"]
        cmd += operator_argv()
        write(out / "launch.json", {"argv": cmd, "started": started, "timeout_seconds": args.timeout,
              "original_identity_sha256": sha(IDENTITY.read_bytes()), "runtime_env": env,
              "qualified_runtime_reference_sha256": contract["reference_sha256"],
              "memory": "6GiB RAM maximum; 8GiB RAM+swap maximum; no host setting changes"})
        state = {"status": "prepared", "owner_pid": os.getpid(), "name": name, "image": IMAGE,
                 "container_id": None, "started": started,
                 "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip()}
        write(out / "state.json", state)
        signals = []
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, lambda signum, frame: signals.append(signum))
        child = None; failure = None; gpu_fault = False
        try:
            created = helper.run(cmd, timeout=30)
            state["container_id"] = created.stdout.strip()
            info = helper.inspect_container(state["container_id"])
            if info is None:
                raise RuntimeError("created container disappeared before startup")
            owned(info, state); write(out / "container-created.json", info)
            state["status"] = "running"; write(out / "state.json", state)
            with (out / "operator.log").open("x") as log, (out / "memory.jsonl").open("x") as memory:
                child = subprocess.Popen(["docker", "start", "--attach", info["Id"]],
                                         stdout=log, stderr=subprocess.STDOUT,
                                         start_new_session=True, env=helper.clean_env())
                deadline, last_memory = time.monotonic() + args.timeout, 0
                while True:
                    journal = helper.journal(started)
                    (out / "kernel.log").write_text(journal)
                    bad = [line for line in journal.splitlines() if helper.FAULT.search(line)]
                    if bad:
                        gpu_fault = True
                        write(out.parent / "FAULT.json", {"at": helper.now(), "stage": out.name, "lines": bad})
                        raise RuntimeError("GPU/kernel fault; no successor admitted")
                    if signals or (out / "STOP").exists():
                        raise InterruptedError("operator controller interrupted")
                    if time.monotonic() >= deadline:
                        raise TimeoutError("one-shot operator deadline; no retry")
                    if list(results.glob("*-FAULT.txt")):
                        raise RuntimeError("operator worker reported client failure; stop owned container")
                    if child.poll() is not None:
                        break
                    if time.monotonic() - last_memory >= 10:
                        info = helper.inspect_container(state["container_id"])
                        if info is None:
                            raise RuntimeError("owned container disappeared")
                        owned(info, state)
                        entry = {"at": helper.now(), "host_meminfo": Path("/proc/meminfo").read_text()}
                        try:
                            pid = info["State"]["Pid"]
                            group = next(s.split(":", 2)[2] for s in Path(f"/proc/{pid}/cgroup").read_text().splitlines() if s.startswith("0::"))
                            cg = Path("/sys/fs/cgroup") / group.lstrip("/")
                            entry["cgroup"] = {n: (cg / n).read_text().strip() for n in ("memory.current", "memory.peak", "memory.events", "memory.swap.current") if (cg / n).exists()}
                        except (OSError, StopIteration):
                            entry["cgroup"] = "unavailable"
                        memory.write(json.dumps(entry) + "\n"); memory.flush(); os.fsync(memory.fileno())
                        last_memory = time.monotonic()
                    time.sleep(2)
            info = helper.inspect_container(state["container_id"])
            if info is None:
                raise RuntimeError("operator exit identity unavailable")
            owned(info, state)
            if info["State"]["Running"] or info["State"]["ExitCode"] != 0 or child.returncode != 0:
                raise RuntimeError(f"operator client failed: attach={child.returncode}, state={info['State']}; no retry")
            if list(results.glob("*-FAULT.txt")):
                raise RuntimeError("operator worker fault receipt present")
            analysis = helper.run(["python3", str(snapshot / "analyze.py"), str(results), "--out", str(out / "analysis.json")], timeout=60)
            if analysis.returncode:
                raise RuntimeError("CPU result analysis failed")
            state["status"] = "operator_completed"
        except BaseException as exc:
            failure = f"{type(exc).__name__}: {exc}"
            state.update(status="gpu_fault" if gpu_fault else "client_failed", error=failure)
            write(out / ("GPU-FAULT.json" if gpu_fault else "CLIENT-FAILED.json"), {"at": helper.now(), "error": failure})
        finally:
            stop = finish_owned(helper, child, out, state)
            try:
                final_journal = helper.journal(started)
                (out / "kernel.log").write_text(final_journal)
                bad = [line for line in final_journal.splitlines() if helper.FAULT.search(line)]
                if bad:
                    gpu_fault = True
                    failure = "GPU/kernel fault in final monitoring window"
                    write(out.parent / "FAULT.json", {"at": helper.now(), "stage": out.name, "lines": bad})
                    write(out / "GPU-FAULT.json", {"at": helper.now(), "error": failure, "lines": bad})
                    state.update(status="gpu_fault", error=failure)
            except Exception as exc:
                failure = failure or f"Final kernel monitoring unavailable: {exc}"
                state.update(status="client_failed", error=failure)
            state.update(stop_confirmed=stop["confirmed"], finished=helper.now())
            if not stop["confirmed"]:
                state["status"] = "stop_unconfirmed"
            write(out / "state.json", state)
        if failure or not state["stop_confirmed"]:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
