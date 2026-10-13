#!/usr/bin/env python3
"""CPU checks of toolchain, model bytes and a fresh coordinator VRAM report.

Does not open DRM nodes or call a device API. A report is admission evidence,
not a reservation; packet44 still performs its own live device memory checks.
"""
import argparse
from pathlib import Path
import shutil
import time
from verify import RECIPE, ROOT, PACKET, read, require, sha

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--model-dir", type=Path, required=True, help="directory containing the three GGUF shards")
p.add_argument("--draft-dir", type=Path, required=True)
p.add_argument("--vram-report", type=Path, required=True, help="fresh coordinator report in the documented schema")
p.add_argument("--card", type=int, choices=(0, 1, 2), required=True)
p.add_argument("--context", type=int, choices=(4096, 32768), default=4096)
a = p.parse_args()
require(shutil.disk_usage("/").free >= 8_000_000_000, "root free space below 8 GB")
compiler = Path("/opt/intel/oneapi/compiler/2026.0/bin/icpx")
require(compiler.is_file(), "sealed build needs compiler 2026.0; a 2026.1 rebuild is not yet qualified")
for command in ("cmake", "g++", "systemd-run"):
    require(shutil.which(command) is not None, "missing " + command)
mem = {line.split(":", 1)[0]: int(line.split()[1]) * 1024 for line in Path("/proc/meminfo").read_text().splitlines() if line.split()[1].isdigit()}
require(mem["MemAvailable"] >= 97 * 1024**3, "model window requires 97 GiB available host memory")
models = read(RECIPE / "manifests/models.json")
for section, directory in (("target", a.model_dir), ("draft", a.draft_dir)):
    for row in models[section]["files"]:
        f = directory / Path(row["path"]).name
        require(f.is_file() and f.stat().st_size == row["bytes"], "model file missing or wrong size: " + str(f))
        require(sha(f) == row["sha256"], "model hash differs: " + str(f))
# Require the lab admission to bind these actual files, not merely equal bytes.
admission = read(ROOT / "experiments/qwen38-flash-next-ud-iq3xxs-b70/packet1/admission-receipt.json")
require(a.model_dir.resolve() == Path(admission["model_dir"]).resolve(), "relocated model requires fresh admission and resealing; see guide")
for row in admission["files"]:
    s = (a.model_dir / Path(row["path"]).name).stat()
    require(dict(bytes=s.st_size, ctime_ns=s.st_ctime_ns, device=s.st_dev, inode=s.st_ino, mtime_ns=s.st_mtime_ns) == row["after"], "target admission is stale; do not replace pins to force a pass")
require(a.draft_dir.resolve() == Path("/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8").resolve(), "draft location differs from sealed runtime; adapt and requalify first")
checked = set()
for line in (PACKET / "mtp-manifest.tsv").read_text().splitlines():
    fields = line.split()
    if fields[1] in checked:
        continue
    checked.add(fields[1])
    s = (a.draft_dir / fields[1]).stat()
    require([s.st_size, s.st_dev, s.st_ino, s.st_mtime_ns, s.st_ctime_ns] == list(map(int, fields[8:13])), "draft file admission is stale: " + fields[1])
report = read(a.vram_report)
require(report["schema"] == "ownrt.coordinator-vram.v1", "unknown VRAM report")
require(report["boot_id"] == Path("/proc/sys/kernel/random/boot_id").read_text().strip(), "VRAM report from another boot")
require(0 <= time.time() - report["captured_unix"] <= 600, "VRAM report must be at most ten minutes old after model hashing")
require(report.get("source") and report.get("raw_evidence"), "coordinator measurement provenance required")
ranks = read(PACKET / "memory-plan.json")["capacities"][str(a.context)]["ranks"]
require(len(report["cards"]) == 2, "two card reports required")
for index, row in enumerate(report["cards"]):
    require(row["card"] == a.card + index and row.get("pci"), "card order/identity differs")
    require(row["free_bytes"] >= ranks[index]["total_with_mtp_bytes"] + 1_500_000_000, "insufficient free VRAM")
print("preflight PASS: toolchain, model hashes/admission and coordinator free VRAM; live window gates still required")
