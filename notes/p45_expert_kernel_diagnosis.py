#!/usr/bin/env python3
"""CPU/read-only evidence extraction; run with python3 -B. No runtime imports."""
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "experiments/own-xpu-runtime/stage2"
P45 = STAGE / "packet45-merged3"


def readonly(event, args):
    if event == "open":
        _, mode, flags = args
        if (mode and any(c in mode for c in "wax+")) or flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
            raise RuntimeError("read-only helper: write refused")
    if event.startswith(("subprocess.", "socket.", "os.exec", "os.spawn", "os.posix_spawn")) or event in {"os.system", "os.remove", "os.rename", "os.mkdir", "os.rmdir", "os.chmod", "os.chown", "os.truncate", "os.link", "os.symlink"}:
        raise RuntimeError("read-only helper: mutation/child/network refused")


sys.addaudithook(readonly)
assert sys.dont_write_bytecode, "use python3 -B"
assert os.getpriority(os.PRIO_PROCESS, 0) == 19
assert set(os.sched_getaffinity(0)) <= set(range(4, 16)) | set(range(20, 32))


def read_json(p):
    return json.loads(p.read_text())


def digest(p):
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def us(comparison, arm, mode="rotated"):
    return comparison[mode][arm]["execution_sum"]["median_ns"] / 1000


def fusion(s, name):
    row = s["classes"]["fusion:p39." + name]
    c = row["comparisons"]["p39.epilogue"]
    assert c["bytes_equal"] and not c["same_kernel"]
    return c, "specialised" if row["selected"] == "p39.epilogue" else "packet18"


print("SPEED6/7 selected class costs: IQ2/IQ3/IQ4 us; rank0/rank1 ms")
primary = None
for speed in (6, 7):
    for cards in ("01", "23"):
        path = P45 / f"build/speed{speed}-c4096-dr1-s23-cards{cards}-gpu/K2/run0/summary.json"
        s = read_json(path)
        assert s["passed"]
        ts = [us(*fusion(s, n)) for n in ("expert-checks-iq2", "expert-checks-iq3", "down-status")]
        a, b, d = ts
        print(speed, cards, ts, [(22*a+b+23*d)/1000, 25*(a+d)/1000], digest(path))
        if speed == 7 and cards == "01":
            primary = s
            primary_path = path

print("\nSelected useful bytes, GB/s, 600 GB/s floor us")
weights = {"IQ2": 10*640*2*(2560//256)*82, "IQ3": 10*640*2*(2560//256)*110, "IQ4": 10*2560*(640//32)*18}
baseline = {}
for typ, name in zip(weights, ("expert-checks-iq2", "expert-checks-iq3", "down-status")):
    c, arm = fusion(primary, name)
    baseline[typ] = us(c, arm)
    print(typ, weights[typ], baseline[typ], weights[typ]/(baseline[typ]*1000), weights[typ]/600000)

print("\nRelevant generic comparisons: rotated baseline/candidate us; reread aggregate")
for klass in ("gemv:expsgate", "gemv:expsdown"):
    for name, c in primary["classes"][klass]["comparisons"].items():
        if not name.startswith(("p28.", "p33.", "p42.")):
            continue
        for workload, w in c["workloads"].items():
            pair = [w["variants"][a]["execution_sum"]["median_ns"]/1000 for a in ("packet18", "specialised")]
            print(klass, name, workload, pair)
        print("  reread", [us(c, a, "reread") for a in ("packet18", "specialised")])

# Stream raw JSONL: do not materialize the large decompressed timing table.
events = primary_path.parent / "events.jsonl.gz"
if not events.exists():
    events = primary_path.parent / "events.jsonl"
opener = gzip.open if events.suffix == ".gz" else open
h = hashlib.sha256()
groups = {}
counts = {}
with opener(events, "rb") as f:
    for line in f:
        h.update(line)
        r = json.loads(line)
        if r.get("class") not in {"fusion:p39.expert-checks-iq2", "fusion:p39.expert-checks-iq3", "fusion:p39.down-status"}:
            continue
        assert r["exact"] is True and r["end_ns"] > r["start_ns"]
        assert r["timing_mode"] == "rotated" and r["rotation_copies"] == 8
        assert r["buffer_copy"] == (r["repetition"] + (4 if r["variant"] == "specialised" else 0)) % 8
        key = r["class"], r["variant"], r["repetition"]
        groups[key] = groups.get(key, 0) + r["end_ns"] - r["start_ns"]
        counts[key] = counts.get(key, 0) + 1
        expected = 1 if r["variant"] == "specialised" else (2 if "down-status" in r["class"] else 3)
        assert r["stage_count"] == expected
assert h.hexdigest() == primary["events_sha256"]
for klass in sorted({k[0] for k in groups}):
    c = primary["classes"][klass]["comparisons"]["p39.epilogue"]
    for arm in ("packet18", "specialised"):
        values = [groups[klass, arm, i] for i in range(200)]
        expected = 1 if arm == "specialised" else (2 if "down-status" in klass else 3)
        assert all(counts[klass, arm, i] == expected for i in range(200))
        assert statistics.median(values) == c["rotated"][arm]["execution_sum"]["median_ns"]
print("\nRaw primary event hash/stage/rotation/median verification PASS", h.hexdigest())

p42 = STAGE / "packet42-codegen2"
print("\nP42 matched expert timing (historical, not P45 fused bodies)")
for r in read_json(p42 / "receipts-card2-20261012/summary.json")["rows"]:
    if r["klass"] in ("expsgate", "expsdown"):
        print(r["candidate"], r["workload"], r["incumbent"]["gpu"]["median_us"], r["alternative"]["gpu"]["median_us"], r["passed"], r["selected"])

print("\nP42 hash-verified GEN paths: instructions/messages; GRF/SIMD; spill annotations")
for r in read_json(p42 / "expert-codegen.json")["rows"]:
    p = p42 / r["asm"]
    data = gzip.decompress(p.read_bytes())
    assert hashlib.sha256(data).hexdigest() == r["asm_sha256"]
    asm = data.decode()
    kernel = r["kernel"].removeprefix("//.kernel ")
    z = gzip.decompress(p.with_name(p.name.replace(".asm.gz", ".zeinfo.gz")).read_bytes()).decode()
    blocks = re.split(r"(?=^  - name:)", z, flags=re.M)
    metadata = [b for b in blocks if kernel in b.splitlines()[0] and "execution_env:" in b]
    assert len(metadata) == 1
    fields = [line.strip() for line in metadata[0].splitlines() if any(k in line for k in ("grf_count:", "simd_size:", "barrier_count:", "slm_size:"))]
    spills = [line.strip() for line in asm.splitlines() if ".spill " in line]
    cfg = r["conditional_cfg_sum"]
    print(r["name"], cfg["instructions"], cfg["memory_messages"], fields, spills, r["asm_sha256"])

p11 = STAGE / "packet11-kopt6"
print("\nP11 layer0 two fresh owners, full span and gate/down stage medians ms")
for r in read_json(p11 / "receipts-card3-20261011/timing.json")["layers"]:
    if r["layer"] == 0:
        for v in r["summary"]["fused"]:
            print(r["repeat"], v["variant"], v["median_ms"], v["stage_median_ms"])
for r in read_json(p11 / "assembly-receipt.json")["kernels"]:
    p = p11 / r["scratch_artifact"]
    if p.exists():
        assert digest(p) == r["gzip_sha256"]
        assert hashlib.sha256(gzip.decompress(p.read_bytes())).hexdigest() == r["asm_sha256"]
print("P11 retained assembly hashes PASS")

print("\nPlanning scenarios ONLY: central/range us, GB/s, savings ms rank0/rank1")
# Anchored body transfers use half the bare delta. Novel scheduling has a no-effect prior.
packed = primary["classes"]["gemv:expsgate"]["comparisons"]["p42.gate.packed"]["workloads"]
def bare_us(workload, arm):
    return packed[workload]["variants"][arm]["execution_sum"]["median_ns"]/1000
g = (bare_us("expsgate.iq2", "packet18") - bare_us("expsgate.iq2", "specialised"))/2
q = (bare_us("expsgate.iq3", "packet18") - bare_us("expsgate.iq3", "specialised"))/2
down = primary["classes"]["gemv:expsdown"]["comparisons"]
d = (us(down["p33.down.select"], "specialised") - us(down["p33.down.bank"], "specialised"))/2
iq3_fused = us(fusion(primary, "expert-checks-iq3")[0], "specialised")
scenarios = [
    ("D1 fused bank/vector", "IQ4", baseline["IQ4"]-d, (baseline["IQ4"]-2*d, 102), (23, 25)),
    ("G1 IQ2 fused packed", "IQ2", baseline["IQ2"]-g, (baseline["IQ2"]-2*g, 86), (22, 25)),
    ("Q1 IQ3 fused packed", "IQ3", iq3_fused-q, (79, 94), (1, 0)),
    ("G2 IQ2 bounded-live packed", "IQ2", baseline["IQ2"], (70, 95), (22, 25)),
    ("D2 IQ4 virtual32 on SG16", "IQ4", baseline["IQ4"], (75, 115), (23, 25)),
    ("Q2 IQ3 bounded-live fused", "IQ3", baseline["IQ3"], (76, 105), (1, 0)),
]
for name, typ, center, (lo, hi), multiplicities in scenarios:
    saved = [(baseline[typ]-center)*n/1000 for n in multiplicities]
    interval = [[(baseline[typ]-hi)*n/1000, (baseline[typ]-lo)*n/1000] for n in multiplicities]
    print(name, "us", center, [lo, hi], "GB/s", weights[typ]/center/1000, [weights[typ]/hi/1000, weights[typ]/lo/1000], "saved", saved, interval)

print("\nSource/receipt identities")
paths = [p42 / "expert-codegen.json", p42 / "receipts-card2-20261012/summary.json", p11 / "analysis.json", p11 / "assembly-receipt.json", p11 / "receipts-card3-20261011/timing.json"]
paths += [P45/n for n in ("p39_sycl.hpp", "p39_fused.hpp", "p28/expert.hpp", "p28/submit.cpp", "p33_candidates.hpp", "p42_expert.hpp", "p39_fixture.cpp", "p39_fixture_data.hpp", "k2_summary.py")]
for p in paths:
    print(digest(p), p.relative_to(ROOT))
