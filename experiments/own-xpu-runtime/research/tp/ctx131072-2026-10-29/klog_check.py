#!/usr/bin/env python3
"""Kernel-log check for the 2026-10-28 direct-store lab: save all kernel lines since an epoch and fail on any xe/GuC/fault
line. Usage: klog_check.py LABEL SINCE_EPOCH OUTFILE. Exit 0 clean, 1 fault lines found, 2 journalctl failed."""
import re, subprocess, sys, time
label, since, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
FAULT = re.compile(r"xe 0000:|GuC|CAT error|Engine reset|Faulted|Timedout|devcoredump|page fault|i915")
p = subprocess.run(["journalctl", "-k", f"--since=@{since}", "--no-pager", "-o", "short-iso"], capture_output=True,
                   text=True, timeout=60)
lines = [l for l in p.stdout.splitlines() if l.strip() and not l.startswith("-- ")]
hits = [l for l in lines if FAULT.search(l)]
with open(out, "w") as f:
    f.write(f"# kernel-log check '{label}' at {time.strftime('%Y-%m-%dT%H:%M:%S%z')} (epoch {int(time.time())}), "
            f"since @{since}; journalctl rc={p.returncode}; {len(lines)} kernel lines, {len(hits)} xe/fault lines\n")
    for l in lines:
        f.write(l + "\n")
print(f"[klog {label}] since @{since}: {len(lines)} lines, {len(hits)} xe/fault lines" + ("" if not hits else " -> HALT"))
for l in hits:
    print("  " + l)
sys.exit(2 if p.returncode else (1 if hits else 0))
