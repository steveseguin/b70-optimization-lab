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
import re
import signal
import subprocess
import tempfile
import time
from types import SimpleNamespace
import uuid

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
IMAGE = "sha256:506fcc26897b12915cb9e27c28e0adc256d278666fa745602a1ae5e1dd8ea066"
IDENTITY = Path("/mnt/fast-ai/bench-results/amd-transfer-fp8-20260914/control-identity.json")
RUNTIME_REFERENCE = Path("/mnt/fast-ai/bench-results/amd-transfer-fp8-20260914/restored-service/container-inspect.json")
FILES = ("exact_tp2.cpp", "native.py", "protocol.py", "gate.py", "analyze.py", "run-native.py", "cpu-validation.json", "ipc-import-source-review.json")
LEGACY_LIBRARY = Path("/tmp/mtp-exact-tp2-build-20260914/libexact_tp2.so")

# Stages reviewed 2026-09-15. Stages 01-04 above stay quarantined without override.
CAMPAIGN_ROOT = Path("/mnt/fast-ai/bench-results/optimization-validation-20260915")
OLD_CAMPAIGN_ROOT = Path("/mnt/fast-ai/bench-results/mtp-lossless-transfer-20260914")
HEALTH_RECEIPT = "health-post-reboot/DONE.json"
# The qualified R304 image: same torch 2.13.0+xpu, intel-sycl-rt 2026.0.0 and
# oneCCL 2022.0.0 as the Native04 image, and the image of RUNTIME_REFERENCE
# and of the passing post-reboot health check under CAMPAIGN_ROOT.
QUALIFIED_IMAGE = "sha256:7cd7bb16b1fd2e679f0230a38b2f0242fe1c278853867e697c0ce139be2133d2"
QUALIFIED_ENV = {"PYTORCH_ALLOC_CONF": "expandable_segments:True", "FI_PROVIDER": "tcp",
                 "FI_TCP_IFACE": "lo", "PYTHONHASHSEED": "0", "TORCHINDUCTOR_DETERMINISTIC": "1"}
FORBIDDEN_ENV = ("PYTHONPATH", "PYTHONSTARTUP", "LD_PRELOAD", "LD_LIBRARY_PATH_OVERRIDE")
NAN_STAGE, GATE_STAGE = "nan-semantics-01", "communication-native-05"
NEW_STAGES = (NAN_STAGE, GATE_STAGE)
ADD_MODES = ("m0", "m1", "m2", "m3")
NEW_LIBRARY = Path("/mnt/fast-ai/research/exact-tp2-build-20260915-sycl9/libexact_tp2.so")
NEW_RECEIPT = "cpu-validation-20260915.json"
GUARD = ROOT / "experiments/qwen38-27b-b70/scripts/host_memory_guard.py"
SUDO_PASSWORD = Path("/home/steve/SUDO_PASSWORD.txt")
GUARD_FIRED_EXIT = 3
NAN_CLASS_DECISION = "NAN-CLASS-DECISION.json"
NAN_RULES = ("bit-exact", "nan-class")
NEW_FILES = ("exact_tp2.cpp", "native.py", "protocol.py", "gate.py", "analyze.py", "run-native.py",
             "quality_retirement.py", "nan_semantics.py", "nan_analysis.py", "ipc-import-source-review.json", NEW_RECEIPT)
CHECKED_SOURCES = ("exact_tp2.cpp", "native.py", "protocol.py", "gate.py", "analyze.py", "run-native.py",
                   "quality_retirement.py", "nan_semantics.py", "nan_analysis.py", "host_memory_guard.py")
CONTAINER_SYCL_RUNTIME = "intel-sycl-rt==2026.0.0"


def require_native_execution_admission(check_only):
    if not check_only:
        raise RuntimeError(
            "Native04 GPU-fault quarantine: this prototype cannot execute. "
            "See native04-postmortem.md. No override exists; recovery and a "
            "corrected candidate require a new reviewed recipe. --check-only is CPU-only."
        )


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


def owned(info, state, image=IMAGE):
    if info["Name"].lstrip("/") != state["name"] or info["Image"] != image or (state.get("container_id") and state["container_id"] != info["Id"]):
        raise RuntimeError("container ownership mismatch; refusing operation")
    state["container_id"] = info["Id"]


def finish_owned(helper, child, out, state, image=IMAGE):
    receipt = {"at": helper.now(), "stop_attempted": False, "confirmed": False, "errors": []}
    try:
        info = helper.inspect_container(state.get("container_id") or state["name"])
        if info:
            owned(info, state, image)
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
                owned(info, state, image)
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


def sycl_majors(library):
    needed = subprocess.run(["readelf", "-d", str(library)], capture_output=True, text=True, check=True, timeout=30).stdout
    return set(re.findall(r"libsycl\.so\.(\d+)", needed))


def qualified_contract(reference):
    """Existing transport contract plus the five qualified service variables."""
    record = reference[0] if isinstance(reference, list) and len(reference) == 1 else reference
    contract = runtime_contract(reference)
    if record.get("Image") != QUALIFIED_IMAGE:
        raise ValueError("qualified runtime reference is not the admitted image")
    env = dict(entry.split("=", 1) for entry in record["Config"]["Env"])
    if any(env.get(k) != v for k, v in QUALIFIED_ENV.items()):
        raise ValueError("qualified service environment (allocator/libfabric/determinism) changed")
    contract["qualified_env"] = dict(QUALIFIED_ENV)
    return contract


def stage_env(contract):
    env = dict(contract["env"])
    env.update(QUALIFIED_ENV)
    env.update(PYTHONUNBUFFERED="1", OMP_NUM_THREADS="1")
    if any(k in env for k in FORBIDDEN_ENV):
        raise ValueError("Python/native injection variable in stage environment")
    return env


def stage_inputs(library, here=HERE, guard=GUARD, reference=RUNTIME_REFERENCE, majors=sycl_majors):
    """CPU-only frozen input set for a 2026-09-15 stage; every check fails closed."""
    blobs = {name: (here / name).read_bytes() for name in NEW_FILES}
    blobs["host_memory_guard.py"] = Path(guard).read_bytes()
    for name, data in blobs.items():
        if name.endswith(".py"):
            compile(data, name, "exec")
    receipt = json.loads(blobs[NEW_RECEIPT])
    if receipt.get("schema") != "neural.download.exact-tp2-cpu-validation.v2" or receipt.get("gpu_initialized") is not False \
            or receipt.get("tests", {}).get("returncode") != 0:
        raise RuntimeError("CPU validation receipt is not a passing CPU-only v2 receipt")
    checked = {x["path"]: x["sha256"] for x in receipt["sources"]}
    for name in CHECKED_SOURCES:
        if checked.get(name) != sha(blobs[name]):
            raise RuntimeError(f"CPU-checked source drift: {name}")
    blobs["libexact_tp2.so"] = Path(library).read_bytes()
    if not any(b["library_sha256"] == sha(blobs["libexact_tp2.so"]) and b["source_sha256"] == sha(blobs["exact_tp2.cpp"])
               and b.get("sycl_needed") == "libsycl.so.9" and b.get("container_runtime") == CONTAINER_SYCL_RUNTIME
               and b.get("abi_symbol_check", {}).get("passed") is True for b in receipt["builds"]):
        raise RuntimeError("native library does not match an ABI-checked CPU build receipt")
    if majors(library) != {"9"}:
        raise RuntimeError("native library is not built against libsycl.so.9 (container intel-sycl-rt 2026.0)")
    raw_reference = Path(reference).read_bytes()
    contract = qualified_contract(json.loads(raw_reference))
    contract.update(reference_sha256=sha(raw_reference), reference_path=str(reference), image=IMAGE,
                    reference_image=QUALIFIED_IMAGE)
    blobs["qualified-runtime-contract.json"] = (json.dumps(contract, indent=2) + "\n").encode()
    return blobs, contract


def nan_semantics_admission(root, add_mode, library_sha256):
    """Stage 05 requires the completed nan-semantics-01 verdict for this exact binary and mode."""
    stage = Path(root) / NAN_STAGE
    try:
        done = json.loads((stage / "DONE.json").read_text())
        state = json.loads((stage / "state.json").read_text())
        raw = (stage / "nan-semantics-verdict.json").read_bytes()
        verdict = json.loads(raw)
        if done.get("passed") is not True or done.get("stage") != NAN_STAGE or done.get("image") != IMAGE:
            raise ValueError("nan-semantics-01 did not complete on the admitted launch image")
        if state.get("status") != "completed" or state.get("stop_confirmed") is not True or (stage / "GPU-FAULT.json").exists():
            raise ValueError("nan-semantics-01 state is not a confirmed clean completion")
        if done.get("verdict_sha256") != sha(raw):
            raise ValueError("nan-semantics verdict hash differs from its DONE receipt")
        if done.get("library_sha256") != library_sha256:
            raise ValueError("stage 05 library differs from the characterized library")
        extra = {}
        if verdict.get("status") == "selected" and verdict.get("selected_mode") in ADD_MODES:
            rule, chosen, matching = "bit-exact", verdict["selected_mode"], verdict.get("matching_modes")
        else:
            # User decision 2026-09-15: NaN outputs may be compared as a class. It
            # must name this exact verdict; the saved raw outputs are re-analyzed.
            decision_raw = (Path(root) / NAN_CLASS_DECISION).read_bytes()
            decision = json.loads(decision_raw)
            if (decision.get("rule") != "nan-class" or decision.get("decided_by") != "user"
                    or decision.get("evidence", {}).get("verdict_sha256") != sha(raw)):
                raise ValueError(f"nan-semantics verdict selected no mode (status {verdict.get('status')!r}) "
                                 "and no user nan-class decision is bound to this verdict")
            reanalysis = class_verdict(stage / "results")
            if reanalysis.get("status") != "selected" or reanalysis.get("selected_mode") not in ADD_MODES:
                raise ValueError(f"nan-class re-analysis selected no mode (status {reanalysis.get('status')!r})")
            rule, chosen, matching = "nan-class", reanalysis["selected_mode"], reanalysis.get("matching_modes")
            extra = {"decision_sha256": sha(decision_raw), "bit_exact_status": reanalysis.get("bit_exact_status"),
                     "class_mismatch_counts": reanalysis.get("class_mismatch_counts")}
        if chosen != add_mode:
            raise ValueError(f"--add-mode {add_mode} differs from selected mode {chosen}")
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        return {"satisfied": False, "reason": f"{type(exc).__name__}: {exc}"}, None
    return {"satisfied": True, "selected_mode": add_mode, "verdict_sha256": sha(raw), "nan_rule": rule,
            "matching_modes": matching, **extra}, raw


def class_verdict(results):
    """CPU re-analysis of saved nan-semantics outputs under the user's nan-class rule."""
    return load_module("nan_analysis_class_admission", HERE / "nan_analysis.py").analyze(results, rule="nan-class")


def stage_admission(out, add_mode, check_only, library, root=CAMPAIGN_ROOT, **inputs_kwargs):
    out, root = Path(out).resolve(), Path(root).resolve()
    if out.name not in NEW_STAGES or out.parent != root:
        raise RuntimeError(f"only {NEW_STAGES} directly under {root} are admitted")
    if out.is_relative_to(OLD_CAMPAIGN_ROOT):
        raise RuntimeError("fault-latched campaign root stays closed")
    if (root / "FAULT.json").exists():
        raise RuntimeError("campaign GPU/memory fault latch is set; no successor")
    health = json.loads((root / HEALTH_RECEIPT).read_text())
    if health.get("passed") is not True:
        raise RuntimeError("post-reboot health receipt did not pass")
    if not check_only and out.exists():
        raise RuntimeError("output exists; one-shot stage, no retry")
    if out.name == NAN_STAGE and add_mode is not None:
        raise ValueError("nan-semantics-01 characterizes all modes; --add-mode is refused")
    if out.name == GATE_STAGE and add_mode not in ADD_MODES:
        raise ValueError("communication-native-05 requires --add-mode m0..m3")
    blobs, contract = stage_inputs(library, **inputs_kwargs)
    nan_receipt = None
    if out.name == GATE_STAGE:
        nan_receipt, raw = nan_semantics_admission(root, add_mode, sha(blobs["libexact_tp2.so"]))
        if not nan_receipt["satisfied"] and not check_only:
            raise RuntimeError("stage 05 refused: " + nan_receipt["reason"])
        if raw is not None:
            blobs["nan-semantics-verdict.json"] = raw
    return {"out": out, "root": root, "stage": out.name, "blobs": blobs, "contract": contract,
            "env": stage_env(contract), "nan_semantics_receipt": nan_receipt}


def stage_argv(stage, add_mode=None, nan_rule="bit-exact"):
    if nan_rule not in NAN_RULES:
        raise ValueError("unknown NaN comparison rule")
    head = [IMAGE, "--nnodes=1", "--node-rank=0", "--nproc-per-node=2",
            "--master-addr=127.0.0.1", "--master-port=29500", "--max-restarts=0"]
    if stage == NAN_STAGE:
        return head + ["/probe/nan_semantics.py", "--library", "/probe/libexact_tp2.so", "--out", "/results",
                       "--rows", "1,2,512,4096", "--timeout", "15", "--admitted-exclusive-gpu-test"]
    if stage == GATE_STAGE and add_mode in ADD_MODES:
        return head + ["/probe/gate.py", "--library", "/probe/libexact_tp2.so", "--out", "/results",
                       "--rows", "1,2,512,4096", "--blocks", "5", "--iterations", "12",
                       "--timeout", "15", "--add-mode", add_mode, "--nan-rule", nan_rule, "--admitted-exclusive-gpu-test"]
    raise ValueError("unknown stage or add mode")


def bounded_run(args, timeout, env=None, popen=subprocess.Popen, clock=time.monotonic, sleep=time.sleep):
    """subprocess.run replacement whose deadline never waits on a killed child.

    A child in uninterruptible I/O ignores SIGKILL until the I/O returns, and
    subprocess.run then blocks in wait(). Output goes to unlinked files, so no
    pipe read can block either; the caller's monitor loop keeps running.
    """
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        child = popen(args, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr, env=env, start_new_session=True)
        deadline = clock() + timeout
        while child.poll() is None:
            if clock() >= deadline:
                try:
                    child.kill()
                except OSError:
                    pass
                raise TimeoutError(f"bounded command exceeded {timeout}s; child abandoned: {' '.join(map(str, args[:3]))}")
            sleep(0.05)
        stdout.seek(0); stderr.seek(0)
        return SimpleNamespace(returncode=child.returncode, stdout=stdout.read().decode(errors="replace"),
                               stderr=stderr.read().decode(errors="replace"), args=args)


class BoundedHelper:
    """Qualified serve-helper semantics with every in-loop command bounded."""
    def __init__(self, helper, runner=bounded_run):
        self.helper, self.runner = helper, runner
        self.FAULT, self.now, self.clean_env = helper.FAULT, helper.now, helper.clean_env

    def run(self, args, check=True, timeout=30):
        result = self.runner(args, timeout, env=self.clean_env())
        if check and result.returncode:
            raise subprocess.CalledProcessError(result.returncode, args, result.stdout, result.stderr)
        return result

    def inspect_container(self, identity):
        result = self.run(["docker", "container", "inspect", identity], check=False, timeout=20)
        if result.returncode:
            if "No such" in result.stderr:
                return None
            raise RuntimeError("Docker inspection failed: " + result.stderr.strip())
        return json.loads(result.stdout)[0]

    def journal(self, since):
        result = self.run(["journalctl", "-k", "--since", since, "--no-pager", "-o", "short-iso"], check=False, timeout=20)
        if result.returncode or re.search(r"permission|not seeing messages|No journal files", result.stderr, re.I):
            raise RuntimeError("Cannot read the kernel journal for fault monitoring")
        return result.stdout

    def check_available(self, port, name):
        return self.helper.check_available(port, name)  # Before any container exists.


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def guard_argv(guard_path, container_id, guard_out, baseline_unaccounted):
    if not re.fullmatch(r"[0-9a-f]{64}", container_id):
        raise ValueError("full 64-hex container ID required for the memory guard")
    return ["sudo", "-S", "-p", "", "--", "/usr/bin/python3", str(guard_path), "--container-id", container_id,
            "--out", str(guard_out), "--baseline-unaccounted", str(int(baseline_unaccounted)), "--appear-timeout", "120"]


def start_guard(argv, log, password=SUDO_PASSWORD, popen=subprocess.Popen, env=None):
    """Root memory guard through sudo; the password goes only to sudo's stdin."""
    child = popen(argv, stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT, start_new_session=True, env=env)
    secret = Path(password).read_bytes()
    try:
        child.stdin.write(secret if secret.endswith(b"\n") else secret + b"\n")
        child.stdin.close()
    finally:
        secret = None
    return child


def wait_guard_ready(child, guard_out, timeout=20, clock=time.monotonic, sleep=time.sleep):
    deadline = clock() + timeout
    samples = Path(guard_out) / "memory-guard.jsonl"
    while True:
        code = child.poll()
        if code is not None:
            raise RuntimeError(f"memory guard exited {code} before monitoring started")
        try:
            if samples.stat().st_size > 0:
                return
        except OSError:
            pass
        if clock() >= deadline:
            raise TimeoutError("memory guard did not start sampling; container not started")
        sleep(0.1)


def guard_outcome(code):
    """Guard contract: None running, 0 container gone/clean, 3 fired, other = guard failure."""
    if code is None:
        return "running"
    return {0: "clean", GUARD_FIRED_EXIT: "fired"}.get(code, "failed")


def latch(root, receipt):
    """Campaign latch; never overwrite an earlier fault."""
    try:
        with (Path(root) / "FAULT.json").open("x") as stream:
            json.dump(receipt, stream, indent=2); stream.write("\n"); stream.flush(); os.fsync(stream.fileno())
    except FileExistsError:
        pass


class StageFailure(RuntimeError):
    def __init__(self, kind, message):
        super().__init__(message)
        self.kind = kind


def classify_failure(exc, gpu_fault, guard_code):
    if gpu_fault:
        return "gpu_fault", "GPU-FAULT.json"
    if guard_outcome(guard_code) == "fired" or getattr(exc, "kind", None) == "memory_guard_fired":
        return "memory_guard_fired", "MEMORY-GUARD-FIRED.json"
    return "client_failed", "CLIENT-FAILED.json"


def check_guard(guard, gone_since, clock=time.monotonic, child_running=True):
    """One monitor-loop guard check; returns updated gone_since."""
    code = guard.poll()
    outcome = guard_outcome(code)
    if outcome == "fired":
        raise StageFailure("memory_guard_fired", "host memory guard fired and killed the container cgroup")
    if outcome == "failed":
        raise StageFailure("guard_failed", f"host memory guard failed with exit {code}")
    if outcome == "clean" and child_running:
        gone_since = gone_since or clock()
        if clock() - gone_since > 15:
            raise StageFailure("guard_failed", "memory guard exited while the container attach still runs")
    return gone_since


def main_new_stage(args):
    library = NEW_LIBRARY if args.library == LEGACY_LIBRARY else args.library
    admission = stage_admission(args.out, args.add_mode, args.check_only, library)
    out, root, stage = admission["out"], admission["root"], admission["stage"]
    argv_tail = stage_argv(stage, args.add_mode, (admission["nan_semantics_receipt"] or {}).get("nan_rule", "bit-exact"))
    if args.check_only:
        print(json.dumps({"status": "CPU-only input admission passed", "stage": stage, "image": IMAGE,
                          "out": str(out), "gpu_discovery": False, "docker_calls": 0, "runtime_env": admission["env"],
                          "nan_semantics_receipt": admission["nan_semantics_receipt"], "worker_argv": argv_tail,
                          "hashes": {k: sha(v) for k, v in admission["blobs"].items()}}, indent=2))
        return
    if not 30 <= args.timeout <= 1200:
        raise ValueError("bounded timeout must be 30–1200 seconds")
    helper = BoundedHelper(load_module("qualified_serve_helper", ROOT / "packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py"))
    guard_module = load_module("host_memory_guard_admitted", GUARD)
    with open("/tmp/qwen-short-prefill-stage.lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        admission = stage_admission(args.out, args.add_mode, False, library)  # Revalidate under the lock.
        blobs = admission["blobs"]
        name = f"exact-tp2-{stage}-" + uuid.uuid4().hex
        helper.check_available(18130, name)
        started = helper.now()
        helper.journal(started)
        image = json.loads(helper.run(["docker", "image", "inspect", IMAGE]).stdout)
        if len(image) != 1 or image[0]["Id"] != IMAGE:
            raise RuntimeError("qualified image identity mismatch")
        out.mkdir(parents=False, exist_ok=False)
        snapshot = freeze(out, blobs)
        results = out / "results"; results.mkdir()
        write(out / "image.json", image)
        env = admission["env"]
        cmd = ["docker", "create", "--name", name, "--restart", "no"] + hardware_argv() + [
               "--memory", "6g", "--memory-swap", "8g", "--workdir", "/probe",
               "--mount", f"type=bind,source={snapshot},target=/probe,readonly",
               "--mount", f"type=bind,source={results},target=/results",
               "--entrypoint", "/opt/venv/bin/torchrun"]
        for key, value in sorted(env.items()):
            cmd += ["--env", f"{key}={value}"]
        cmd += argv_tail
        nodes = sorted(str(p) for p in Path("/dev/dri").glob("renderD*"))
        owners = helper.run(["fuser", *nodes], check=False)
        write(out / "owners-before.json", {"returncode": owners.returncode, "stdout": owners.stdout, "stderr": owners.stderr})
        state = {"status": "prepared", "stage": stage, "owner_pid": os.getpid(), "name": name, "image": IMAGE,
                 "container_id": None, "started": started, "add_mode": args.add_mode,
                 "nan_semantics_receipt": admission["nan_semantics_receipt"],
                 "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip()}
        write(out / "state.json", state)
        signals = []
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, lambda signum, frame: signals.append(signum))
        child = guard = guard_code = None; failure = None; gpu_fault = False; analysis = None
        try:
            # Baseline strictly before container creation, as the guard requires.
            meminfo = guard_module.parse_meminfo(Path("/proc/meminfo").read_text())
            baseline = guard_module.unaccounted_bytes(meminfo)
            write(out / "launch.json", {"argv": cmd, "started": started, "timeout_seconds": args.timeout,
                  "runtime_env": env, "qualified_env": QUALIFIED_ENV,
                  "qualified_runtime_reference_sha256": admission["contract"]["reference_sha256"],
                  "memory_guard_baseline_unaccounted": baseline, "memory_available_before": meminfo["MemAvailable"],
                  "memory": "6GiB RAM / 8GiB RAM+swap container limit; root host-memory guard kills the cgroup"})
            created = helper.run(cmd, timeout=60)
            identity = created.stdout.strip()
            if not re.fullmatch(r"[0-9a-f]{64}", identity):
                raise RuntimeError("docker create returned no immutable container ID")
            state["container_id"] = identity
            info = helper.inspect_container(identity)
            if info is None:
                raise RuntimeError("created container disappeared before startup")
            owned(info, state, IMAGE); write(out / "container-created.json", info)
            gargv = guard_argv(snapshot / "host_memory_guard.py", identity, out / "memory-guard", baseline)
            state["memory_guard"] = {"argv": gargv}; write(out / "state.json", state)
            with (out / "memory-guard.log").open("x") as guard_log:  # Popen keeps its own descriptor.
                guard = start_guard(gargv, guard_log, env=helper.clean_env())
            state["memory_guard"]["pid"] = guard.pid
            wait_guard_ready(guard, out / "memory-guard")
            state["status"] = "running"; write(out / "state.json", state)
            with (out / "operator.log").open("x") as log, (out / "memory.jsonl").open("x") as memory:
                child = subprocess.Popen(["docker", "start", "--attach", identity], stdout=log, stderr=subprocess.STDOUT,
                                         start_new_session=True, env=helper.clean_env())
                deadline, last_memory, gone_since = time.monotonic() + args.timeout, 0, None
                while True:
                    gone_since = check_guard(guard, gone_since, child_running=child.poll() is None)
                    journal = helper.journal(started)
                    (out / "kernel.log").write_text(journal)
                    bad = [line for line in journal.splitlines() if helper.FAULT.search(line)]
                    if bad:
                        gpu_fault = True
                        latch(root, {"at": helper.now(), "stage": stage, "lines": bad})
                        raise RuntimeError("GPU/kernel fault; no successor admitted")
                    if signals or (out / "STOP").exists():
                        raise InterruptedError("operator controller interrupted")
                    if time.monotonic() >= deadline:
                        raise TimeoutError("one-shot operator deadline; no retry")
                    if list(results.glob("*-FAULT.txt")):
                        raise RuntimeError("worker reported an unknown fault; stop owned container")
                    if child.poll() is not None:
                        break
                    if time.monotonic() - last_memory >= 5:
                        info = helper.inspect_container(identity)
                        if info is None:
                            raise RuntimeError("owned container disappeared")
                        owned(info, state, IMAGE)
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
                    time.sleep(1)
            info = helper.inspect_container(identity)
            if info is None:
                raise RuntimeError("operator exit identity unavailable")
            owned(info, state, IMAGE)
            if list(results.glob("*-QUALITY-REJECTED.json")):
                raise RuntimeError("mutually acknowledged exact-bit quality rejection (cooperative retirement); no retry")
            if info["State"]["Running"] or info["State"]["ExitCode"] != 0 or child.returncode != 0:
                raise RuntimeError(f"operator client failed: attach={child.returncode}, state={info['State']}; no retry")
            if list(results.glob("*-FAULT.txt")):
                raise RuntimeError("worker fault receipt present")
            if stage == NAN_STAGE:
                verdict_path = out / "nan-semantics-verdict.json"
                result = helper.run(["python3", str(snapshot / "nan_analysis.py"), str(results), "--out", str(verdict_path)], check=False, timeout=900)
                if result.returncode:
                    raise RuntimeError("CPU NaN-semantics analysis failed")
                analysis = json.loads(verdict_path.read_text())
                if analysis["status"] not in ("selected", "no-single-formulation-matches", "xccl-ranks-disagree"):
                    raise RuntimeError(f"NaN-semantics evidence incomplete: {analysis['errors']}")
            else:
                rule = (admission["nan_semantics_receipt"] or {}).get("nan_rule", "bit-exact")
                result = helper.run(["python3", str(snapshot / "analyze.py"), str(results), "--out", str(out / "analysis.json"),
                                     "--nan-rule", rule], check=False, timeout=900)
                if result.returncode:
                    raise RuntimeError("CPU result analysis failed")
                analysis = json.loads((out / "analysis.json").read_text())
            state["status"] = "operator_completed"
        except BaseException as exc:
            failure = f"{type(exc).__name__}: {exc}"
            guard_code = guard.poll() if guard is not None else None
            kind, receipt_name = classify_failure(exc, gpu_fault, guard_code)
            state.update(status=kind, error=failure)
            write(out / receipt_name, {"at": helper.now(), "error": failure, "guard_exit": guard_code})
        finally:
            stop = finish_owned(helper, child, out, state, IMAGE) if state.get("container_id") else {"confirmed": child is None}
            if guard is not None:
                limit = time.monotonic() + 20
                while guard.poll() is None and time.monotonic() < limit:
                    time.sleep(0.25)
                guard_code = guard.poll()
                write(out / "memory-guard-exit.json", {"at": helper.now(), "exit": guard_code, "outcome": guard_outcome(guard_code)})
                if guard_outcome(guard_code) == "fired":
                    failure = failure or "host memory guard fired"
                    if state.get("status") != "gpu_fault":  # A GPU fault classification is never downgraded.
                        state.update(status="memory_guard_fired", error=failure)
                    if not (out / "MEMORY-GUARD-FIRED.json").exists():
                        write(out / "MEMORY-GUARD-FIRED.json", {"at": helper.now(), "error": failure, "guard_exit": guard_code})
                elif guard_outcome(guard_code) != "clean":
                    if not failure:
                        state.update(status="client_failed", error=f"memory guard exit unconfirmed or failed: {guard_code}")
                    failure = failure or f"memory guard exit unconfirmed or failed: {guard_code}"
            if state.get("status") == "memory_guard_fired":
                latch(root, {"at": helper.now(), "stage": stage, "kind": "memory_guard_fired", "error": failure})
            try:
                for _ in range(3):  # Tail window for kernel messages after worker exit.
                    time.sleep(1)
                    final_journal = helper.journal(started)
                    (out / "kernel.log").write_text(final_journal)
                    bad = [line for line in final_journal.splitlines() if helper.FAULT.search(line)]
                    if bad:
                        gpu_fault = True
                        failure = failure or "GPU/kernel fault in final monitoring window"
                        latch(root, {"at": helper.now(), "stage": stage, "lines": bad})
                        write(out / "GPU-FAULT.json", {"at": helper.now(), "error": failure, "lines": bad})
                        state.update(status="gpu_fault", error=failure)
                        break
                owners = helper.run(["fuser", *nodes], check=False)
                write(out / "owners-after.json", {"returncode": owners.returncode, "stdout": owners.stdout, "stderr": owners.stderr})
                if owners.returncode != 1 or owners.stdout.strip():
                    if not failure:
                        state.update(status="client_failed", error="render device ownership not clear after stage")
                    failure = failure or "render device ownership not clear after stage"
            except Exception as exc:
                if not failure:
                    state.update(status="client_failed", error=f"Final monitoring unavailable: {exc}")
                failure = failure or f"Final monitoring unavailable: {exc}"
            state.update(stop_confirmed=stop["confirmed"], finished=helper.now())
            if not stop["confirmed"]:
                state["status"] = "stop_unconfirmed"
            elif not failure:
                state["status"] = "completed"
            write(out / "state.json", state)
        if failure or not state["stop_confirmed"]:
            raise SystemExit(1)
        done = {"passed": True, "stage": stage, "image": IMAGE, "state_sha256": sha((out / "state.json").read_bytes()),
                "library_sha256": sha(blobs["libexact_tp2.so"]), "snapshot_manifest_sha256": sha((out / "snapshot-manifest.json").read_bytes()),
                "runtime_qualified": False}
        if stage == NAN_STAGE:
            done.update(verdict_sha256=sha((out / "nan-semantics-verdict.json").read_bytes()), verdict_status=analysis["status"],
                        selected_mode=analysis["selected_mode"], matching_modes=analysis["matching_modes"],
                        scope="Characterization complete; a mode is admitted only when verdict_status is selected")
        else:
            done.update(add_mode=args.add_mode, quality_passed=analysis["quality_passed"],
                        qualified_operator_shapes=analysis["qualified_operator_shapes"],
                        passed=analysis["quality_passed"] is True)
        write(out / "DONE.json", done)
        print(json.dumps(done, indent=2))
        if not done["passed"]:
            raise SystemExit(1)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--library", type=Path, default=LEGACY_LIBRARY)
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--check-only", action="store_true")
    ap.add_argument("--add-mode", choices=ADD_MODES, default=None, help="communication-native-05 only")
    args = ap.parse_args()
    if args.out.name in NEW_STAGES:
        # Separately reviewed 2026-09-15 stages; their admission is fail-closed
        # (new campaign root only, no fault latch, frozen CPU receipt, env,
        # memory guard and, for stage 05, the selected NaN-semantics mode).
        return main_new_stage(args)
    # Unconditional prototype-level latch, independent of output directory or
    # campaign FAULT files. It precedes imports, locks, Docker and device checks.
    require_native_execution_admission(args.check_only)
    if not 30 <= args.timeout <= 1200:
        raise ValueError("bounded timeout must be 30–1200 seconds")
    out = args.out.resolve()
    if out.name not in ("communication-native-01", "communication-native-02", "communication-native-03", "communication-native-04"):
        raise ValueError("only the original or explicitly corrected one-shot stage is admitted")
    if not args.check_only and (out.exists() or (out.parent / "FAULT.json").exists()):
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
