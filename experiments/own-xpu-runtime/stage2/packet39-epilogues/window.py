#!/usr/bin/env python3
"""Coordinator window. CPU preparation never invokes the production services."""
import argparse, hashlib, json, os, re, signal, subprocess, time
from pathlib import Path
P = Path(__file__).resolve().parent
FAULT = re.compile(r"Fault response|CAT error|engine reset|(?:GPU|device).*coredump", re.I)

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def command(args):
    return ["nice", "-n", "19", "ionice", "-c", "3", *map(str, args)]

def persist(path, row):
    # All records contain strings, never pathlib objects.
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(row, indent=2, allow_nan=False) + "\n")
    temp.replace(path)

class Services:
    def journal(self, cursor=None):
        argv = ["journalctl", "-k", "--no-pager", "--show-cursor"]
        argv += ["--after-cursor", cursor] if cursor else ["-n", "1"]
        r = subprocess.run(command(argv), capture_output=True, text=True, timeout=10)
        if r.returncode:
            raise RuntimeError("journal read failed: " + r.stderr)
        lines = r.stdout.splitlines()
        found = [x[len("-- cursor: "):] for x in lines if x.startswith("-- cursor: ")]
        if not found and not cursor:
            raise RuntimeError("journal returned no cursor")
        return "\n".join(x for x in lines if not x.startswith("-- cursor: ")), found[-1] if found else cursor

    def ldd(self, binary):
        r = subprocess.run(command(["ldd", binary]), capture_output=True, text=True, timeout=15)
        if r.returncode or "not found" in r.stdout or "not found" in r.stderr:
            raise RuntimeError("missing native library: " + r.stdout + r.stderr)
        return r.stdout

    def launch(self, argv, log, env):
        return subprocess.Popen(argv, stdout=log, stderr=subprocess.STDOUT, env=env)

    def boot(self):
        return Path("/proc/sys/kernel/random/boot_id").read_text().strip()

    def binaries(self):
        seal = json.loads((P / "build-receipt.json").read_text())
        binaries = {name: sha(P / "build" / name) for name in ("p39-k0", "p39-timing")}
        if binaries["p39-k0"] != binaries["p39-timing"]:
            raise RuntimeError("K0/G4 must use byte-identical executable images")
        if binaries != seal["native_binary_sha256"]:
            raise RuntimeError("native binary seal mismatch")
        for name, expected in seal["source_sha256"].items():
            if sha(P / name) != expected:
                raise RuntimeError("source seal mismatch: " + name)
        return binaries

    def assembly(self):
        return json.loads((P / "assembly-review.json").read_text())["classes"]

    def native_command(self, a, run):
        binary = P / "build" / ("p39-k0" if a.window == "K0" else "p39-timing")
        argv = command([binary, "--authorized-device-window", "--card", a.card, "--output", run])
        if a.window == "G4":
            argv += ["--repetitions", "200"]
        else:
            argv += ["--compile-smoke"]
        return binary, argv


def main(argv=None, services=None):
    services = services or Services()
    parser = argparse.ArgumentParser()
    parser.add_argument("--authorized-device-window", action="store_true")
    parser.add_argument("--window", choices=("K0", "G4"), required=True)
    parser.add_argument("--card", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--k0", type=Path)
    a = parser.parse_args(argv)
    out = a.output.resolve()
    if not out.is_relative_to(P / "build") or out.exists():
        raise ValueError("fresh output below packet39/build required")
    out.mkdir(parents=True)
    record = out / "window.json"
    row = dict(schema="packet39.window.v1", window=a.window, passed=False, card=a.card,
               device_accessed=False, device_executed=False, kernel_execution=False,
               environment={k: v for k, v in os.environ.items() if k in {"PATH", "LD_LIBRARY_PATH", "OMP_NUM_THREADS", "SYCL_DEVICE_FILTER", "ONEAPI_DEVICE_SELECTOR", "SYCL_PI_LEVEL_ZERO_USE_IMMEDIATE_COMMANDLISTS", "SYCL_CACHE_PERSISTENT", "IGC_EnableDPEmulation", "SYCL_PROGRAM_COMPILE_OPTIONS", "SYCL_PROGRAM_LINK_OPTIONS"}}, expected_seconds=60 if a.window == "K0" else 240,
               expectation_enforced=False, no_retry=True)
    row["watchdog_seconds"] = max(300, 4 * row["expected_seconds"])
    persist(record, row)
    child = None
    requested = []
    old_handlers = {}
    try:
        if not a.authorized_device_window:
            raise ValueError("coordinator authorization required")
        if os.getpriority(os.PRIO_PROCESS, 0) != 19 or os.environ.get("OMP_NUM_THREADS") != "2":
            raise ValueError("nice19 and OMP_NUM_THREADS=2 required")
        if not 0 <= a.card <= 3:
            raise ValueError("card must be 0..3")
        row["native_binary_sha256"] = services.binaries()
        row["boot_id"] = services.boot()
        if a.window == "G4":
            if not a.k0:
                raise ValueError("successful matching K0 receipt required")
            previous = json.loads(a.k0.read_text())
            if not previous.get("passed") or previous.get("window") != "K0":
                raise ValueError("K0 did not pass")
            for key in ("boot_id", "card", "native_binary_sha256", "environment"):
                if previous.get(key) != row[key]:
                    raise ValueError("K0 identity differs: " + key)
        run = out / "run"
        run.mkdir()
        binary, argv = services.native_command(a, run)
        row["command"] = argv
        row["ldd"] = services.ldd(binary)
        # Ignore historical lines. Only lines AFTER this cursor may latch a fault.
        _, cursor = services.journal()
        row["journal_start_cursor"] = cursor
        for sig in (signal.SIGINT, signal.SIGTERM):
            old_handlers[sig] = signal.getsignal(sig)
            signal.signal(sig, lambda s, f: requested.append("coordinator signal"))
        persist(record, row)
        start = time.monotonic()
        sent = None
        with (out / "stdout.txt").open("w") as log, (out / "kernel.txt").open("w") as kernel:
            child = services.launch(argv, log, dict(os.environ))
            row.update(pid=child.pid, device_accessed=True, device_executed=a.window == "G4", kernel_execution=a.window == "G4")
            persist(record, row)
            while child.poll() is None:
                try:
                    fresh, cursor = services.journal(cursor)
                    kernel.write(fresh + "\n")
                    kernel.flush()
                    if FAULT.search(fresh):
                        requested.append("new GPU fault")
                        persist(out / "FAULT.json", dict(reason="new GPU fault", cursor=cursor, lines=fresh))
                except Exception as exc:
                    requested.append(str(exc))
                if time.monotonic() - start >= row["watchdog_seconds"]:
                    requested.append("watchdog exceeded")
                if requested and sent is None:
                    row.update(stop_reasons=list(requested), error="; ".join(requested))
                    persist(record, row)  # Failure durable BEFORE graceful stop.
                    child.send_signal(signal.SIGTERM)
                    sent = time.monotonic()
                if sent is not None and time.monotonic() - sent >= 360:
                    row.update(child_retained=True, error="native process did not stop gracefully; coordinator owns recovery")
                    persist(record, row)
                    return 1
                time.sleep(0.1)
        row.update(returncode=child.returncode, elapsed_seconds=time.monotonic() - start)
        fresh, cursor = services.journal(cursor)
        (out / "postflight-kernel.txt").write_text(fresh)
        if FAULT.search(fresh):
            requested.append("new postflight GPU fault")
            persist(out / "FAULT.json", dict(reason=requested[-1], cursor=cursor, lines=fresh))
        native = json.loads((run / "receipt.json").read_text())
        infrastructure_ok = native.get("infrastructure_passed", native.get("passed")) is True
        if child.returncode != 0 or requested or not infrastructure_ok:
            raise RuntimeError("native window failed: " + str(requested))
        if a.window == "G4":
            dispatch = json.loads((run / "dispatch-measured.json").read_text())
            if not isinstance(dispatch.get("fusions"), dict):
                raise RuntimeError("missing fusion timing mapping")
            summary = json.loads((run / "summary.json").read_text())
            case_rows = summary["rows"]
            failed = {r["class"]: r for r in case_rows if not r["passed"]}
            row.update(cases_passed=not failed, failed_cases=len(failed),
                       cases_completed=len(case_rows), infrastructure_passed=True)
            # Timing alone cannot resurrect a fusion rejected by offline codegen.
            review = services.assembly()
            provisional = run / "dispatch-provisional.json"
            (run / "dispatch-measured.json").replace(provisional)
            selection = [dict(class_name=name, selected=False, reason="case failed: " + r.get("failure_kind", "unknown")) for name, r in failed.items()]
            kept = {}
            for name, candidate in dispatch["fusions"].items():
                if name in failed:
                    continue
                if not any(r["class"] == name and r["passed"] for r in case_rows):
                    raise RuntimeError("dispatch without passing case row: " + name)
                verdict = review.get(name, {})
                accepted = candidate == "p39.epilogue" and verdict.get("accepted") is True
                reason = ("measured winner; assembly accepted" if accepted else
                          "not faster than unfused" if candidate != "p39.epilogue" else
                          verdict.get("reason", "missing offline assembly acceptance"))
                if accepted:
                    kept[name] = candidate
                selection.append(dict(class_name=name, selected=accepted, reason=reason))
            # Activation includes these same two checks: never dispatch or count
            # both. Prefer the complete accepted activation chain when it wins;
            # otherwise the status-only chain may stand on its own measurement.
            for fmt in ("iq2", "iq3"):
                complete, checks = "expert-act-" + fmt, "expert-checks-" + fmt
                if complete in kept and checks in kept:
                    del kept[checks]
                    for decision in selection:
                        if decision["class_name"] == checks:
                            decision.update(selected=False, reason="mutually exclusive: selected " + complete)
            dispatch["fusions"] = kept
            persist(run / "dispatch-measured.json", dispatch)
            persist(run / "dispatch-selection.json", dict(schema="packet39.dispatch-selection.v1",
                    screening_only=True, native_provisional_sha256=sha(provisional), rows=selection))
            row["dispatch_sha256"] = sha(run / "dispatch-measured.json")
        row["passed"] = True
        persist(record, row)
        return 0
    except Exception as exc:
        row["error"] = str(exc)
        persist(record, row)
        if child is not None and child.poll() is None:
            child.send_signal(signal.SIGTERM)
            row["child_retained"] = True
            persist(record, row)
        return 1
    finally:
        for sig, handler in old_handlers.items():
            signal.signal(sig, handler)

if __name__ == "__main__":
    raise SystemExit(main())
