"""Coordinator-only windows; CPU tests inject services and a mock native binary."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time

P = Path(__file__).resolve().parent
FAULT = re.compile(r"Fault response|CAT error|engine reset|(?:GPU|device).*coredump", re.I)
ENV_KEYS = {"LD_LIBRARY_PATH", "OMP_NUM_THREADS", "SYCL_DEVICE_FILTER", "ONEAPI_DEVICE_SELECTOR", "SYCL_PI_LEVEL_ZERO_USE_IMMEDIATE_COMMANDLISTS", "SYCL_CACHE_PERSISTENT", "SYCL_PROGRAM_COMPILE_OPTIONS", "SYCL_PROGRAM_LINK_OPTIONS", "IGC_EnableDPEmulation"}

def command(argv):
    return ["nice", "-n", "19", "ionice", "-c", "3", *map(str, argv)]

def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()

def persist(path, value):
    """No empty final receipt on ENOSPC; report the storage failure to stderr."""
    path = Path(path)
    temp = path.with_name(path.name + ".tmp")
    try:
        data = json.dumps(value, indent=2, allow_nan=False, ensure_ascii=False) + "\n"
        with temp.open("w") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        temp.replace(path)
    except Exception as exc:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass
        print("FAILED WINDOW: receipt write failed at " + str(path) + ": " + str(exc), file=sys.stderr, flush=True)
        raise

def proc_memory(pid):
    try:
        fields = dict(line.split(":", 1) for line in Path(f"/proc/{pid}/status").read_text().splitlines() if ":" in line)
        return {k: int(fields[k].split()[0]) * 1024 for k in ("RssAnon", "VmRSS") if k in fields}
    except FileNotFoundError:
        return {}  # A just-exited child is normal.

class Services:
    def persist(self, path, row):
        persist(path, row)

    def journal(self, cursor=None):
        argv = ["journalctl", "-k", "--no-pager", "--show-cursor"]
        argv += ["--after-cursor", cursor] if cursor else ["-n", "1"]
        r = subprocess.run(command(argv), text=True, capture_output=True, timeout=10)
        if r.returncode:
            raise RuntimeError("kernel journal unavailable: " + r.stderr)
        lines = r.stdout.splitlines()
        cursors = [x.removeprefix("-- cursor: ") for x in lines if x.startswith("-- cursor: ")]
        if not cursors and not cursor:
            raise RuntimeError("journal cursor missing")
        return "\n".join(x for x in lines if not x.startswith("-- cursor: ")), cursors[-1] if cursors else cursor

    def boot(self):
        return Path("/proc/sys/kernel/random/boot_id").read_text().strip()

    def seal(self):
        seal = json.loads((P / "build-receipt.json").read_text())
        for path, digest in seal["source_sha256"].items():
            if sha(P / path) != digest:
                raise RuntimeError("source seal mismatch: " + path)
        for path, digest in seal["native_binary_sha256"].items():
            if sha(P / path) != digest:
                raise RuntimeError("binary seal mismatch: " + path)
        for path, digest in seal.get("readonly_dependency_sha256", {}).items():
            if sha(P.parent / path) != digest:
                raise RuntimeError("dependency seal mismatch: " + path)
        for path, digest in seal.get("gate_sha256", {}).items():
            if sha(P / path) != digest:
                raise RuntimeError("gate seal mismatch: " + path)
        return seal

    def ldd(self, binary):
        r = subprocess.run(command(["ldd", binary]), capture_output=True, text=True, timeout=15)
        if r.returncode or "not found" in r.stdout + r.stderr:
            raise RuntimeError("missing native library: " + r.stdout + r.stderr)
        return r.stdout

    def launch(self, argv, log):
        # Preserve coordinator LD_LIBRARY_PATH verbatim, including absence/empty.
        return subprocess.Popen(command(argv), stdout=log, stderr=subprocess.STDOUT, env=dict(os.environ))

    def memory(self, pid):
        return proc_memory(pid)

    def free(self):
        return shutil.disk_usage("/").free

    def summarize(self, window, out):
        from summarize import summarize
        return summarize(window, out)


def main(argv=None, services=None):
    s = services or Services()
    ap = argparse.ArgumentParser()
    ap.add_argument("--authorized-device-window", action="store_true")
    ap.add_argument("--window", choices=("K0", "T1", "K2"), required=True)
    ap.add_argument("--card", type=int, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--k0", type=Path)
    ap.add_argument("--t1", type=Path)
    a = ap.parse_args(argv)
    out = a.output.resolve()
    if not out.is_relative_to(P / "build") or out.exists():
        print("FAILED WINDOW: fresh output under packet42/build required", file=sys.stderr)
        return 1
    row = dict(schema="packet42.window.v1", window=a.window, card=a.card, passed=False,
               device_accessed=False, device_executed=False, no_retry=True,
               expected_seconds={"K0":120, "T1":600, "K2":600}[a.window],
               environment={k:os.environ[k] for k in sorted(os.environ) if k in ENV_KEYS or k.startswith(("ZE_", "UR_", "SYCL_", "IGC_", "ONEAPI_"))})
    row["watchdog_seconds"] = max(300, 4 * row["expected_seconds"])
    row["expectation_enforced"] = False
    child = None
    old_handlers = {}
    requested = []
    try:
        out.mkdir(parents=True)
        s.persist(out / "window.json", row)
        if not a.authorized_device_window or not 0 <= a.card <= 3:
            raise ValueError("coordinator authorization and card 0..3 required")
        if os.getpriority(os.PRIO_PROCESS, 0) != 19 or os.environ.get("OMP_NUM_THREADS") != "2":
            raise ValueError("nice19 and OMP_NUM_THREADS=2 required")
        if s.free() < 8_000_000_000:
            raise RuntimeError("root disk below 8 GB free; refusing before device contact")
        seal = s.seal()
        row.update(boot_id=s.boot(), native_binary_sha256=seal["native_binary_sha256"])
        for required, name in ((a.k0, "K0"), (a.t1, "T1")):
            needed = a.window != "K0" if name == "K0" else a.window == "K2"
            if not needed:
                continue
            if required is None:
                raise ValueError(name + " receipt required")
            prev = json.loads(required.read_text())
            if prev.get("passed") is not True or prev.get("window") != name:
                raise ValueError(name + " failed")
            for k in ("card", "boot_id", "native_binary_sha256", "environment"):
                if prev.get(k) != row[k]:
                    raise ValueError(name + " identity differs: " + k)
        specs = seal["windows"][a.window]
        row["components"] = []
        # Resolve every binary before any device contact.
        for spec in specs:
            s.ldd(P / spec["binary"])
        _, cursor = s.journal()
        row["journal_start_cursor"] = cursor
        s.persist(out / "window.json", row)
        for sig in (signal.SIGINT, signal.SIGTERM):
            old_handlers[sig] = signal.getsignal(sig)
            signal.signal(sig, lambda sig, frame: requested.append("coordinator signal"))
        start = time.monotonic()
        for spec in specs:
            run = out / spec["name"]
            run.mkdir()
            cmd = [str(P / spec["binary"]), "--authorized-device-window", "--card", str(a.card), "--output", str(run), *spec.get("args", [])]
            component = dict(name=spec["name"], command=cmd, passed=False)
            row["components"].append(component)
            sent = None
            with (run / "stdout.txt").open("w") as log:
                child = s.launch(cmd, log)
                row.update(device_accessed=True, device_executed=a.window != "K0", pid=child.pid)
                s.persist(out / "window.json", row)
                while child.poll() is None:
                    fresh, cursor = s.journal(cursor)
                    if fresh:
                        with (out / "kernel.txt").open("a") as f:
                            f.write(fresh + "\n")
                    if FAULT.search(fresh):
                        requested.append("new kernel fault")
                        s.persist(out / "FAULT.json", dict(cursor=cursor, lines=fresh, reason="new kernel fault"))
                    if s.memory(child.pid).get("RssAnon", 0) > 8_000_000_000:
                        requested.append("anonymous memory limit")
                    if s.free() < 8_000_000_000:
                        requested.append("root disk below 8 GB free")
                    if time.monotonic() - start >= row["watchdog_seconds"]:
                        requested.append("watchdog")
                    if requested and sent is None:
                        row.update(error="; ".join(requested), passed=False)
                        s.persist(out / "window.json", row)  # failure before teardown
                        child.send_signal(signal.SIGTERM)
                        sent = time.monotonic()
                    if sent is not None and time.monotonic() - sent >= 300:
                        row.update(child_retained=True, error="child did not stop gracefully; coordinator recovery required")
                        s.persist(out / "window.json", row)
                        return 1
                    time.sleep(0.1)
            component["returncode"] = child.returncode
            fresh, cursor = s.journal(cursor)
            if FAULT.search(fresh):
                requested.append("new postflight kernel fault")
                s.persist(out / "FAULT.json", dict(cursor=cursor, lines=fresh, reason=requested[-1]))
            if child.returncode:
                with (run / "stdout.txt").open("rb") as f:
                    f.seek(0, 2);size=f.tell();f.seek(max(0,size-2048));tail=f.read().decode("utf-8",errors="replace")
                raise RuntimeError("native infrastructure failed: " + spec["name"] + ": exit " + str(child.returncode) + ": " + tail)
            native = json.loads((run / "receipt.json").read_text())
            if requested or child.returncode or native.get("infrastructure_passed", native.get("passed")) is not True:
                raise RuntimeError("native infrastructure failed: " + spec["name"] + ": " + str(requested))
            component["passed"] = True
            s.persist(out / "window.json", row)
        summary = s.summarize(a.window, out)
        row.update(passed=True, summary_sha256=sha(out / "summary.json"),
                   cases_passed=summary.get("cases_passed", True), elapsed_seconds=time.monotonic()-start)
        s.persist(out / "window.json", row)
        return 0
    except Exception as exc:
        row.update(passed=False, error=str(exc))
        print("FAILED WINDOW: " + str(exc), file=sys.stderr, flush=True)
        try:
            s.persist(out / "window.json", row)
        except Exception:
            pass  # stderr remains authoritative when storage is unavailable.
        if child is not None and child.poll() is None:
            child.send_signal(signal.SIGTERM)
            row["child_retained"] = True
            try:
                s.persist(out / "window.json", row)
            except Exception:
                pass
        return 1
    finally:
        for sig, handler in old_handlers.items():
            signal.signal(sig, handler)

if __name__ == "__main__":
    raise SystemExit(main())
