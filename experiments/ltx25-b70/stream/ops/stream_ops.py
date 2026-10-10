#!/usr/bin/env python3
"""Single coordinator transition. No daemon, restart policy, shell eval or device imports.

Paths and Clock are dependency-injection seams used ONLY by the CPU tests; the
CLI always constructs the fixed host Paths. Frozen packet launchers stay intact.
"""
import argparse
import datetime as dt
import fcntl
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass

LANE = Path(__file__).resolve().parents[2]
FAULT = re.compile(r"Fault response|CAT error|engine reset|GPU HANG|GuC.*reset|coredump|Timedout job|timed.out job|wedged", re.I)
UNIT = re.compile(r"ltx(?P<packet>1\d{2}[a-z]?)-stream-(?P<role>client|server)-\d{8}\.service")
SUPPORTED = {str(n) for n in range(120, 136)} | {"123b", "133b"}


class Refusal(Exception):
    pass


def require(ok, message):
    if not ok:
        raise Refusal(message)


def present(path):
    return path.exists() or path.is_symlink()


def plain_path(path):
    require(path.is_absolute() and re.fullmatch(r"/[A-Za-z0-9_./-]+", str(path)),
            "paths must be absolute and contain only letters, digits, / . _ -")
    require(".." not in path.parts and path.resolve() == path, "symlink or parent traversal in path")


@dataclass
class Paths:
    lane: Path = LANE
    results: Path = Path("/mnt/fast-ai/bench-results/ltx25-baseline-20260913")
    work_root: Path = Path("/home/steve/ltx-stream")
    sink: Path = Path("/home/steve/ltx-stream/start-sink-117.sh")
    python: str = "/home/steve/.venvs/ltx25-baseline/bin/python"
    systemctl: str = "systemctl"
    journalctl: str = "journalctl"
    curl: str = "curl"

    @property
    def receipts(self):
        return self.lane / "data/resume-20261008"


class Clock:
    monotonic = staticmethod(time.monotonic)
    sleep = staticmethod(time.sleep)
    utc = staticmethod(lambda: dt.datetime.now(dt.timezone.utc).isoformat())


def run_name(packet, args, env):
    fr, an, dg, ad, bo, pa, sm, cap, ds, ra, ss, dd, rec = args
    name = (f"encoder-server-continuation-stream-{packet}-{an}-dg{dg}-ad{ad}-bo{bo}-pa{pa}"
            f"-sm{'fp' if sm == 'fingerprint' else 'walk'}-two-way20-28-w1-b1-p1-dxpu2-s256x256-f{fr}")
    if (ds, ra, ss) != ("sampler-a", "0", "full"):
        name += f"-ds{ds}-ra{ra}-ss{ss}"
    if dd == "xpu:2":
        name += "-ddxpu2"
    for key, default, suffix in [
        ("AUX_RESIDENCY", "legacy", "auxxpu2"), ("DISPLAY_WORKER", "serial", "dwparallel"),
        ("GC_INTERVAL_SECONDS", "10", "gc60"), ("STORAGE_SCAN_MODE", "request", "ssbackground"),
        ("SNAPSHOT_DIGEST_CACHE", "0", "sdc1"), ("MAINTENANCE_MODE", "parent", "mi"),
        ("DISPLAY_ALLOCATOR_RELEASE", "off", "arbefore-admission"),
        ("CONE_GRAPH_MEMORY", "off", "cm" + env.get("LTX_CONE_GRAPH_MEMORY", "off")),
        ("AUDIO_RESIDENCY", "legacy", "audioxpu2"), ("TEXT_RESIDENCY", "legacy", "textsplit36"),
        ("CHUNK_ARM", "off", "arm" + env.get("LTX_CHUNK_ARM", "off")),
    ]:
        if env.get("LTX_" + key, default) != default:
            name += "-" + suffix
    return name


def requested_latches(args):
    _, _, dg, ad, bo, pa, sm, _, _, _, _, dd, _ = args
    names = []
    if dg == "1":
        names += ["decoder-graph-116-refused.json"]
    if ad == "cone":
        names += [f"anchor-decode-{n}-refused.json" for n in (117, 118)]
    if bo == "1" or pa == "1":
        names += [f"precompute-{n}-refused.json" for n in (117, 118)]
    if sm == "fingerprint":
        names += ["snapshot-118-refused.json"]
    if dd == "xpu:2":
        names += ["display-replica-120-refused.json"]
    return names


class Operation:
    def __init__(self, packet, work, args, env, dry=False, paths=None, clock=None):
        self.paths = paths or Paths()
        self.clock = clock or Clock()
        self.packet, self.work, self.args = packet, Path(work), list(args)
        self.env = dict(env, LTX_STREAM_WORKDIR=str(self.work), OMP_NUM_THREADS="2",
                        MKL_NUM_THREADS="2", PYTHONDONTWRITEBYTECODE="1")
        self.dry = dry
        self.tag = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:10]
        self.receipt = self.paths.receipts / f"stream-ops-{self.tag}.json"
        self.record = {"schema": "ltx.stream-ops.v1", "packet": packet, "work_dir": str(work),
                       "started_utc": self.clock.utc(), "commands": [], "moves": [], "status": "pending",
                       "env": {k: v for k, v in self.env.items() if k.startswith("LTX_")}}

    def save(self):
        if not self.dry:
            tmp = self.receipt.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.record, indent=2, ensure_ascii=False) + "\n")
            tmp.replace(self.receipt)

    def command(self, argv, *, allow_failure=False):
        argv = [str(x) for x in argv]
        print("+ " + shlex.join(argv), flush=True)
        entry = {"argv": argv, "started_utc": self.clock.utc()}
        self.record["commands"].append(entry)
        self.save()  # intent before side effect, including a hung child
        if self.dry:
            return ""
        # Bound read-only clients; never timeout/kill a launcher, health probe or stop.
        readonly = argv[0] in (self.paths.curl, self.paths.journalctl) or (
            argv[0] == self.paths.systemctl and any(x in argv for x in ("show", "list-units")))
        result = subprocess.run(argv, env=self.env, text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, check=False, timeout=20 if readonly else None)
        entry.update(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)
        self.save()
        require(allow_failure or result.returncode == 0, f"command refused ({result.returncode}): {shlex.join(argv)}")
        return result.stdout if result.returncode == 0 else None

    def guards(self):
        for name in ["FAULT.json", *requested_latches(self.args)]:
            require(not present(self.paths.results / name), f"guard present: {name}; manual review required")

    def validate(self):
        require(self.packet in SUPPORTED, "packet not reviewed for this launcher grammar (120–135, 123b, 133b)")
        require(len(self.args) == 13, "exactly 13 launcher args required, including health receipt or -")
        require(all(isinstance(x, str) and x for x in self.args), "launcher args must be nonempty strings")
        require(all(re.fullmatch(r"[A-Za-z0-9_.:-]+", x) for x in self.args[:12]), "invalid launcher argument")
        require(self.args[1] == "frame", "client supports anchor frame only")
        for index, choices in {
            0: ("49", "97", "121", "145", "169"), 2: ("0", "1"), 3: ("full", "cone"),
            4: ("0", "1"), 5: ("0", "1"), 6: ("walk", "fingerprint"),
            8: ("sampler-a", "sampler-b", "eager-display"), 9: ("0", "1"),
            10: ("full", "a-xpu3-sync"), 11: ("xpu:2", "xpu:3"),
        }.items():
            require(self.args[index] in choices, f"invalid launcher argument {index + 1}")
        require(self.args[7] == "-" or re.fullmatch(r"\d+(?:\.\d+)?", self.args[7]), "invalid pool cap")
        plain_path(self.work)
        require(self.work.parent == self.paths.work_root, "work-dir must be an immediate child of the stream work root")
        require(not present(self.work), "work-dir already exists; choose a fresh work-dir")
        plain_path(self.paths.results)
        plain_path(self.paths.receipts)
        require(self.paths.results.is_dir(), "results root missing")
        launchers = list((self.paths.lane / "recovery").glob(f"*-continuation{self.packet}-stream/launch-{self.packet}.sh"))
        require(len(launchers) == 1, "expected exactly one packet launcher")
        self.launcher = launchers[0]
        self.client = self.paths.lane / f"stream/start-client-{self.packet}.sh"
        require(self.client.is_file() and self.paths.sink.is_file(), "client or sink script missing")
        source = self.launcher.read_text()
        choices = {
            "AUX_RESIDENCY": ("legacy", "xpu2"), "DISPLAY_WORKER": ("serial", "parallel"),
            "GC_INTERVAL_SECONDS": ("10", "60"), "STORAGE_SCAN_MODE": ("request", "background"),
            "SNAPSHOT_DIGEST_CACHE": ("0", "1"), "MAINTENANCE_MODE": ("parent", "idle"),
            "DISPLAY_ALLOCATOR_RELEASE": ("off", "before-admission"),
            "CONE_GRAPH_MEMORY": ("off", "replica-release", "text-shift"),
            "AUDIO_RESIDENCY": ("legacy", "xpu2"), "TEXT_RESIDENCY": ("legacy", "split36"),
            "CHUNK_ARM": ("off", "split36-169"),
        }
        for key, values in choices.items():
            value = self.env.get("LTX_" + key, values[0])
            require(value in values, f"invalid LTX_{key}")
            require(value == values[0] or "LTX_" + key in source, f"launcher does not support LTX_{key}")
        unit = re.search(r"^UNIT=(ltx[0-9a-z]+-stream-server-\d{8})$", source, re.M)
        require(unit is not None, "unrecognized launcher unit declaration")
        self.target_unit = unit[1] + ".service"
        self.target_run = self.paths.results / run_name(self.packet, self.args, self.env)
        plain_path(self.target_run)
        require(self.target_run.parent == self.paths.results, "target run escaped results root")
        self.health = (self.paths.receipts / f"health-stream-ops-{self.tag}.json"
                       if self.args[12] == "-" else Path(self.args[12]))
        plain_path(self.health)
        require(self.health.parent == self.paths.receipts and not present(self.health),
                "health receipt must be a fresh path directly under data/resume-20261008 (or use -)")
        self.args[12] = str(self.health)
        self.record.update(launcher_args=self.args, target_run=str(self.target_run), health_receipt=str(self.health))
        self.guards()

    def stopped_unit(self, unit):
        output = self.command([self.paths.systemctl, "--user", "show", unit,
                               "--property=ActiveState,MainPID,ControlPID,TasksCurrent,ControlGroup"])
        if self.dry:
            return
        props = dict(line.split("=", 1) for line in output.splitlines() if "=" in line)
        require(props.get("ActiveState") in ("inactive", "failed") and
                props.get("MainPID") == "0" and props.get("ControlPID") == "0" and
                (props.get("TasksCurrent") == "0" or props.get("ControlGroup") == ""),
                f"unit still active or process drain not established: {unit}")

    def units(self):
        raw = self.command([self.paths.systemctl, "--user", "list-units", "--all", "--plain", "--no-legend", "--no-pager", "ltx*-stream-*.service"])
        if self.dry:
            print("# Discover at most one old client and server; refuse ambiguity. Placeholders below resolve at execution.")
            return ["<old-client.service>", "<old-server.service>", "ltx117-stream-sink.service"], {"<old-packet>"}
        rows = []
        for line in raw.splitlines():
            if not line.strip():
                continue
            name = line.split()[0]
            columns = line.split()
            require(len(columns) >= 4, "malformed unit listing")
            require(UNIT.fullmatch(name) is not None or name == "ltx117-stream-sink.service",
                    f"unrecognized stream unit: {name}")
            if columns[2] in ("inactive", "failed"):
                self.stopped_unit(name)
            rows.append((name, columns[2]))
        # Historical inactive/failed units are not live candidates. After a
        # halt, retain a uniquely identified old packet even if its sink lives.
        live = [(name, state) for name, state in rows if state not in ("inactive", "failed")]
        candidates = list(live)
        if not any(UNIT.fullmatch(name) for name, _ in live):
            old_packets = {UNIT.fullmatch(name)["packet"] for name, _ in rows if UNIT.fullmatch(name)}
            selected = next(iter(old_packets)) if len(old_packets) == 1 else self.packet
            candidates += [(name, state) for name, state in rows if (name, state) not in live and
                           ((UNIT.fullmatch(name) and UNIT.fullmatch(name)["packet"] == selected)
                            or name == "ltx117-stream-sink.service")]
        roles, packets, sink = {}, set(), []
        for name, state in candidates:
            if name == "ltx117-stream-sink.service":
                sink = [name]
                continue
            match = UNIT.fullmatch(name)
            require(match is not None, f"unrecognized stream unit: {name}")
            role = match["role"]
            require(role not in roles, f"ambiguous {role} units; review manually")
            roles[role] = name
            packets.add(match["packet"])
        require(len(packets) <= 1, "client/server packet mismatch")
        return [roles[r] for r in ("client", "server") if r in roles] + sink, packets

    def journal(self):
        log = self.command([self.paths.journalctl, "-k", "-b", "--since", self.record["started_utc"], "--no-pager"])
        require(not FAULT.search(log), "kernel fault-class line; evidence retained, no launch")

    def move(self, source, destination):
        require(not source.is_symlink(), f"refuse symlink archive source: {source}")
        plain_path(destination)
        require(not present(destination), f"archive destination exists: {destination}")
        self.command(["mkdir", "-p", str(destination.parent)])
        self.command(["mv", "-T", "--no-clobber", "--", source, destination])
        if not self.dry:
            require(not present(source) and present(destination), "archive move did not complete")
        self.record["moves"].append({"source": str(source), "destination": str(destination)})
        self.save()

    def archive(self, packets):
        for packet in sorted(packets | {self.packet}):
            archive = self.paths.results / "output" / f"archive-stream{packet}-{self.tag}"
            for category in ("output", "output/validation", "requests"):
                directory = self.paths.results / category
                require(not directory.is_symlink(), f"symlink archive directory: {directory}")
                if self.dry and packet == "<old-packet>":
                    print(f"+ mv -- {directory}/stream<old-packet>-* {archive}/{category}/  # each matching name, preserving category")
                for source in sorted(directory.glob(f"stream{packet}-*")):
                    self.move(source, archive / category / source.name)
        if present(self.target_run):
            require(self.target_run.is_dir(), "target run exists but is not a directory")
            self.move(self.target_run, self.target_run.with_name(self.target_run.name + f".completed-{self.tag}"))
        elif self.dry:
            print(f"# If present: mv -- {self.target_run} {self.target_run}.completed-{self.tag}")

    def chain(self):
        units, packets = self.units()
        for unit in units:
            # Inspect every unit before stopping any. Never change live unit policy.
            properties = self.command([self.paths.systemctl, "--user", "show", unit, "--property=KillSignal,SendSIGKILL,KillMode"])
            if not self.dry:
                props = dict(line.split("=", 1) for line in properties.splitlines() if "=" in line)
                require(props.get("KillSignal") in ("2", "SIGINT") and props.get("SendSIGKILL") == "no"
                        and props.get("KillMode") == "control-group", "unit does not guarantee one SIGINT without SIGKILL")
        for unit in units:
            self.command([self.paths.systemctl, "--user", "stop", unit])
            self.stopped_unit(unit)
        stopped = self.clock.monotonic()
        self.record.update(stopped_utc=self.clock.utc(), gap_seconds=305)
        self.save()
        self.journal()
        self.archive(packets)
        self.guards()
        require(not present(self.health), "health receipt appeared during stop/archive; refusing overwrite")
        self.command([self.paths.python, "-B", self.paths.lane / "scripts/check-four-card-health.py", self.health])
        if not self.dry:
            require(json.loads(self.health.read_text()).get("passed") is True, "health receipt did not pass")
        self.command(["bash", self.launcher, *self.args, "--check-only"])
        if self.dry:
            print("+ sleep <max(0, stop_monotonic + 305 - now_monotonic)>  # wait to stop + 305 s")
        else:
            while self.clock.monotonic() < stopped + 305:
                self.clock.sleep(min(60, stopped + 305 - self.clock.monotonic()))
        self.record["gap_elapsed_seconds"] = self.clock.monotonic() - stopped
        self.guards()
        self.journal()
        self.command(["bash", self.launcher, *self.args])
        deadline = self.clock.monotonic() + 1800
        for attempt in range(361):
            require(self.dry or self.clock.monotonic() <= deadline, "status deadline expired; no retry")
            self.guards()
            self.journal()
            raw = self.command([self.paths.curl, "--fail", "--silent", "--show-error", "--connect-timeout", "2", "--max-time", "5",
                                "http://127.0.0.1:8188/ltx-stream/status"], allow_failure=True)
            if self.dry:
                print("# Poll status at 5 s intervals, at most 1800 s / 361 attempts; require explicit phase=stream_setup, halted=null, fault=false.")
                break
            if raw is not None:
                status = json.loads(raw)
                require(isinstance(status, dict) and "halted" in status and "fault" in status,
                        "status lacks explicit halted/fault fields")
                require(status["halted"] is None and status["fault"] is False, "server halted or faulted; no retry")
                if status.get("phase") == "stream_setup":
                    require(str(status.get("packet")) == self.packet and
                            status.get("receipt_dir") == str(self.target_run / "receipts"),
                            "status packet/run identity mismatch")
                    self.record["ready_status"] = status
                    break
            require(self.clock.monotonic() < deadline and attempt < 360, "status deadline expired; no retry")
            self.clock.sleep(min(5, max(0, deadline - self.clock.monotonic())))
        # Same arm environment, remove anchor/receipt, translate the cap spelling.
        client_args = self.args[:1] + self.args[2:12]
        if client_args[6] == "-":
            client_args[6] = "none"
        self.guards()
        self.command(["bash", self.client, *client_args])
        self.command(["bash", self.paths.sink])
        self.record["status"] = "complete"
        self.save()
        print(f"Packet {self.packet}; work {self.work}; receipt {self.receipt}; one launch, no retries.")

    def run(self):
        if self.dry:
            self.validate()
            print("# DRY RUN: no commands, writes, locks, sleeps, health probes or endpoint calls execute.")
            print("# Environment: " + shlex.join(f"{k}={v}" for k, v in sorted(self.env.items()) if k.startswith("LTX_") or k in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "PYTHONDONTWRITEBYTECODE")))
            print(f"# Write progress/refusal/archive receipt: {self.receipt}")
            self.chain()
            return
        plain_path(self.paths.receipts)
        self.paths.receipts.mkdir(parents=True, exist_ok=True)
        with (self.paths.receipts / "stream-ops.lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise Refusal("another stream operation holds the lock") from exc
            self.save()
            try:
                self.validate()
                self.chain()
            except (Exception, KeyboardInterrupt) as exc:
                self.record.update(status="refused", error=str(exc), ended_utc=self.clock.utc())
                self.save()
                print(f"Refusal receipt: {self.receipt}", file=sys.stderr)
                raise


def production(path, ambient):
    arm = json.loads(path.read_text())
    require(isinstance(arm, dict) and {"packet_id", "launcher_args", "env"} <= set(arm)
            and set(arm) <= {"packet_id", "work_dir", "launcher_args", "env"},
            "production arm requires packet_id, launcher_args, env; optional work_dir")
    if "work_dir" not in arm:
        require(isinstance(arm["packet_id"], str) and arm["packet_id"] in SUPPORTED, "unsupported packet_id")
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        arm["work_dir"] = str(Paths().work_root / f"s{arm['packet_id']}-resume-{stamp}-{uuid.uuid4().hex[:10]}")
    require(isinstance(arm["packet_id"], str) and isinstance(arm["work_dir"], str), "packet_id/work_dir must be strings")
    require(isinstance(arm["launcher_args"], list) and len(arm["launcher_args"]) == 13
            and all(isinstance(x, str) for x in arm["launcher_args"]), "launcher_args requires 13 strings")
    require(isinstance(arm["env"], dict) and all(re.fullmatch(r"LTX_[A-Z0-9_]+", k) and isinstance(v, str)
            for k, v in arm["env"].items()), "env requires LTX_* string values")
    require("LTX_STREAM_WORKDIR" not in arm["env"], "use work_dir, not LTX_STREAM_WORKDIR in env")
    # No ambient experimental LTX option may silently change the production arm.
    env = {k: v for k, v in ambient.items() if not k.startswith("LTX_")}
    env.update(arm["env"])
    return arm, env


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    swap = sub.add_parser("swap", usage="swap-to-packet.sh [--dry-run] <packet-id> <work-dir> -- <13 launcher args>")
    swap.add_argument("--dry-run", action="store_true")
    swap.add_argument("packet")
    swap.add_argument("work_dir")
    swap.add_argument("launcher_args", nargs=argparse.REMAINDER)
    resume = sub.add_parser("resume", usage="resume-production.sh [--dry-run] [production-arm.json]")
    resume.add_argument("--dry-run", action="store_true")
    resume.add_argument("arm", nargs="?", type=Path, default=Path(__file__).with_name("production-arm.json"))
    options = parser.parse_args(argv)
    try:
        if options.mode == "resume":
            arm, env = production(options.arm, os.environ)
            operation = Operation(arm["packet_id"], arm["work_dir"], arm["launcher_args"], env, options.dry_run)
        else:
            args = options.launcher_args
            if args[:1] == ["--"]:
                args = args[1:]
            operation = Operation(options.packet, options.work_dir, args, os.environ, options.dry_run)
        operation.run()
    except (Refusal, OSError, ValueError, subprocess.TimeoutExpired, KeyboardInterrupt) as exc:
        print(f"REFUSE: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
