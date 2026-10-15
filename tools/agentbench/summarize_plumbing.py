#!/usr/bin/env python3
"""summarize_plumbing.py [ROOT]: one Markdown table of every agent's plumbing results (basic, slow, stress at ~1 MB
and at 4M+ characters), from the plumbing-result.json files under ROOT
(default /mnt/fast-ai/bench-results/agentbench-plumbing-20261014). Memory is "non-file / total peak" in MiB of the
agent container (non-file = anon + kernel: what cannot be dropped as page cache)."""
import json, os, sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else "/mnt/fast-ai/bench-results/agentbench-plumbing-20261014"


def load(name):
    try:
        return json.load(open(os.path.join(ROOT, name, "plumbing-result.json")))
    except (OSError, ValueError):
        return None


def mem(d):
    m = (d or {}).get("memory_mib") or {}
    return f"{m.get('max_nonfile', 0):.0f} / {m.get('peak', 0):.0f}" if m else "-"


def ok(d, ignore=()):
    if not d:
        return "-"
    bad = [k for k, v in d["checks"].items() if not v and k not in ignore]
    return "pass" if not bad else "FAIL: " + ", ".join(bad)


agents = sorted({n.split("-stress")[0].split("-slow")[0] for n in os.listdir(ROOT)
                 if os.path.isfile(os.path.join(ROOT, n, "plumbing-result.json")) and "-1mb" not in n or n.endswith("-1mb")}
                - {""})
agents = sorted({a[:-4] if a.endswith("-1mb") else a for a in agents})
print("| agent | version | image | basic | slow reply (330 s) | stress 4M+ chars | memory basic | memory ~1 MB | memory 4M+ | fixed tokens | stream | resends reasoning |")
print("|---|---|---|---|---|---|---|---|---|---|---|---|")
for a in agents:
    b, s, st, m1 = load(a), load(a + "-slow"), load(a + "-stress"), load(a + "-stress-1mb")
    if not b:
        continue
    big = f"{ok(st)} ({st['largest_request_bytes'] / 1e6:.1f} MB)" if st else "-"
    print(f"| {a} | {b.get('agent_version') or ''} | {b.get('image_size')} | {ok(b)} | {ok(s)} | {big} | {mem(b)} | "
          f"{mem(m1)} | {mem(st)} | {b.get('approx_fixed_tokens')} | {','.join(b.get('stream') or [])} | "
          f"{(b.get('history_shape') or {}).get('resends_reasoning')} |")
