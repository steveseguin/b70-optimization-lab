#!/usr/bin/env python3
"""Per-token GPU work census from two `sycl-trace --ur.call` logs of llama-bench (-n A and -n B tokens).

Counts kernel launches by kernel name (and USM memcpy/fill enqueues) in each log; the per-token count is
(count_B - count_A) / (B - A), which cancels model load, warm-up and the prompt.
  census_parse.py census-trace-n16.txt 16 census-trace-n48.txt 48 [--top 40]
"""
import argparse
import collections
import re
import subprocess

CREATE = re.compile(r"\.pKernelName = 0x[0-9a-f]+ \(([^)]*)\), \.phKernel = 0x[0-9a-f]+ \((0x[0-9a-f]+)\)")
LAUNCH = re.compile(r"\.hKernel = (0x[0-9a-f]+)")


def census(path):
    names = {}
    counts = collections.Counter()
    pending = None
    with open(path, errors="replace") as f:
        for line in f:
            if line.startswith("[UR] "):
                pending = line[5:].split("(")[0]
                continue
            if pending is None:
                continue
            if pending == "urKernelCreate":
                m = CREATE.search(line)
                if m:
                    names[m.group(2)] = m.group(1)
            elif pending.startswith("urEnqueueKernelLaunch"):
                m = LAUNCH.search(line)
                if m:
                    counts["kernel " + names.get(m.group(1), m.group(1))] += 1
            elif pending.startswith("urEnqueueUSM") or pending.startswith("urEnqueueMem"):
                counts[pending] += 1
            pending = None
    return counts


def demangle(names):
    try:
        out = subprocess.run(["c++filt"], input="\n".join(names), capture_output=True, text=True, check=True).stdout
        return out.splitlines()
    except Exception:
        return names


def short(name):
    # keep the lambda's enclosing function: "...(anonymous)::foo_sycl(...)::{lambda...}" -> foo_sycl
    m = re.search(r"([A-Za-z_][A-Za-z0-9_<>:]*)\([^()]*(?:\([^()]*\)[^()]*)*\)::\{lambda", name)
    if m:
        return m.group(1).split("::")[-1]
    return name[:90]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("log_a")
    ap.add_argument("n_a", type=int)
    ap.add_argument("log_b")
    ap.add_argument("n_b", type=int)
    ap.add_argument("--top", type=int, default=40)
    args = ap.parse_args()
    a, b = census(args.log_a), census(args.log_b)
    keys = sorted(set(a) | set(b))
    per_tok = {k: (b[k] - a[k]) / (args.n_b - args.n_a) for k in keys}
    kernel_keys = [k for k in keys if k.startswith("kernel ")]
    pretty = dict(zip(kernel_keys, demangle([k[7:] for k in kernel_keys])))
    grouped = collections.Counter()
    for k, v in per_tok.items():
        grouped[short(pretty[k]) if k in pretty else k] += v
    total = sum(v for k, v in grouped.items() if not k.startswith("urEnqueue"))
    print(f"kernel launches per token: {total:.1f}")
    for k, v in grouped.most_common(args.top):
        if abs(v) >= 0.05:
            print(f"{v:8.1f}  {k}")


if __name__ == "__main__":
    main()
