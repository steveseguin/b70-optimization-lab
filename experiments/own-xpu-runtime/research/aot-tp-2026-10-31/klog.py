#!/usr/bin/env python3
"""Kernel-log check (aot-tp-2026-10-31 copy of two-card-flags-2026-10-31/klog.py; stage-overhead lab, 2026-10-30): all kernel lines since an epoch via `sudo -S journalctl -k`
(password file on stdin, never printed); fail on any xe/GuC/fault/reset/coredump line.
Usage: klog.py LABEL SINCE_EPOCH OUTFILE. Exit 0 clean, 1 fault lines, 2 journalctl failed."""
import re, subprocess, sys, time
label, since, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
FAULT = re.compile(r"xe 0000:|GuC|CAT error|Engine reset|engine reset|Fault response|Faulted|Timedout|devcoredump|coredump|page fault|i915", re.I)
pw = open('/home/steve/SUDOPASSWORD.txt').read()
p = subprocess.run(["sudo", "-S", "-p", "", "journalctl", "-k", f"--since=@{since}", "--no-pager", "-o", "short-iso"],
                   input=pw + "\n", capture_output=True, text=True, timeout=60)
lines = [l for l in p.stdout.splitlines() if l.strip() and not l.startswith("-- ")]
hits = [l for l in lines if FAULT.search(l)]
with open(out, "w") as f:
    f.write(f"# kernel-log check '{label}' at {time.strftime('%Y-%m-%dT%H:%M:%S%z')} (epoch {int(time.time())}), "
            f"since @{since}; journalctl rc={p.returncode}; {len(lines)} kernel lines, {len(hits)} xe/fault lines\n")
    for l in lines:
        f.write(l + "\n")
print(f"[klog {label}] since @{since}: rc={p.returncode} {len(lines)} lines, {len(hits)} xe/fault lines" + ("" if not hits else " -> HALT"))
for l in hits:
    print("  " + l)
sys.exit(2 if p.returncode else (1 if hits else 0))
