#!/usr/bin/env python3
"""memwatch.py CONTAINER OUT.json [--every S]: sample an agent container's memory from the host side.

Reads the container's cgroup v2 files directly (the path comes from /proc/<pid>/cgroup of its first process), so
sampling costs nothing inside the container. Keeps the maxima and rewrites OUT.json after every sample, so it can
simply be killed when the agent is done:

  peak_bytes          the kernel's own memory.peak (all charged memory, page cache included)
  max_current_bytes   largest memory.current seen
  max_nonfile_bytes   largest (anon + kernel) seen: memory that cannot be dropped as page cache; this is the number
                      to hold against the host's free RAM
  max_anon_bytes      largest anon seen
"""
import json, os, subprocess, sys, time


def cgroup_dir(container):
    pid = subprocess.run(["docker", "inspect", "-f", "{{.State.Pid}}", container], capture_output=True, text=True).stdout.strip()
    for ln in open(f"/proc/{pid}/cgroup"):
        if ln.startswith("0::"):
            return "/sys/fs/cgroup" + ln[3:].strip()
    raise SystemExit("memwatch: no cgroup v2 path")


def stat(d):
    out = {}
    for ln in open(d + "/memory.stat"):
        k, v = ln.split()
        out[k] = int(v)
    return out


def main():
    container, path = sys.argv[1], sys.argv[2]
    every = float(sys.argv[sys.argv.index("--every") + 1]) if "--every" in sys.argv else 1.0
    d = cgroup_dir(container)
    best = {"cgroup": d, "samples": 0, "peak_bytes": 0, "max_current_bytes": 0, "max_nonfile_bytes": 0, "max_anon_bytes": 0}
    while os.path.exists(d + "/memory.current"):
        try:
            cur = int(open(d + "/memory.current").read())
            st = stat(d)
            peak = int(open(d + "/memory.peak").read()) if os.path.exists(d + "/memory.peak") else 0
        except (OSError, ValueError):
            break
        best["samples"] += 1
        best["peak_bytes"] = max(best["peak_bytes"], peak)
        best["max_current_bytes"] = max(best["max_current_bytes"], cur)
        best["max_anon_bytes"] = max(best["max_anon_bytes"], st.get("anon", 0))
        best["max_nonfile_bytes"] = max(best["max_nonfile_bytes"], st.get("anon", 0) + st.get("kernel", 0))
        best["mib"] = {k[:-6]: round(v / 2**20, 1) for k, v in best.items() if k.endswith("_bytes")}
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(best, f, indent=1)
        os.replace(tmp, path)
        time.sleep(every)


if __name__ == "__main__":
    main()
