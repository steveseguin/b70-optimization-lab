#!/usr/bin/env python3
"""Generate "kvstream" Harbor tasks: a local stand-in for ContextBench's KV Store task.

ContextBench (arXiv 2609.37725) is NOT released (README "Coming soon", upstream issue #2).
The paper describes its KV Store task as "batches of 100 SET operations with random
24-word values" followed by "24 GET queries", graded on exact-value accuracy, at a
32,768-token limit with context pressure (input volume / limit) from 1x to 24x.
This generator builds Harbor tasks that follow that description. It is OUR
approximation, not the paper's data or grader, so scores are not comparable to the paper.

How a task works:
  * the sandbox holds a stream at /opt/kvstream/stream.jsonl; the agent runs `next`
    to receive the next item, which is removed from disk as it is delivered
    (past items survive only in the agent's context or in notes the agent wrote);
  * items are SET batches, then one final item listing the GET keys;
  * the agent writes /app/answers.json ({key: value}) and submits;
  * the verifier compares against tests/expected.json (copied into the sandbox only at
    verification time) and writes the fraction of exact matches to reward.txt.
Reading /opt/kvstream directly is against the task rules; summarize_results.py flags
any command that names that path.

Usage:
  make_kvstream_tasks.py OUT_DIR [--pressure 1 2 4] [--seeds 0 1] [--batch-size 100]
                         [--n-get 24] [--overwrite-frac 0.1] [--limit 32768]
  make_kvstream_tasks.py OUT_DIR --smoke      # one tiny task (1 batch of 8 SETs, 3 GETs)
"""
from __future__ import annotations

import argparse
import json
import math
import random
import shutil
import stat
from pathlib import Path

SYLL = ["ka", "lo", "mi", "ne", "ru", "ta", "vo", "zi", "pe", "su", "do", "fa", "gu", "hi",
        "ja", "ke", "ba", "co", "di", "ro", "sa", "tu", "we", "yo", "xa", "qi", "mo", "ni"]

# tokens per SET line, measured with tiktoken o200k_base (the harness ruler): ~59
TOK_PER_SET = 60

NEXT_SCRIPT = r'''#!/usr/bin/env python3
"""Deliver the next item of the KV stream (and delete it from disk)."""
import json, os, sys
P = "/opt/kvstream/stream.jsonl"
STATE = "/opt/kvstream/delivered"
try:
    lines = open(P).read().splitlines()
except FileNotFoundError:
    lines = []
if not lines:
    print("STREAM END: no more items. Answer the GET queries in /app/answers.json, then submit.")
    sys.exit(0)
item = json.loads(lines[0])
tmp = P + ".tmp"
with open(tmp, "w") as f:
    f.write("\n".join(lines[1:]) + ("\n" if len(lines) > 1 else ""))
os.replace(tmp, P)
n = int(open(STATE).read()) + 1 if os.path.exists(STATE) else 1
open(STATE, "w").write(str(n))
print(f"ITEM {n}/{item['total']} ({item['kind']})")
print(item["text"])
if item["kind"] == "GET":
    print("\nThis was the last item. Write /app/answers.json now.")
'''

INSTRUCTION = """\
You are connected to a key-value stream. Run the command `next` to receive the next item
of the stream. There are {total} items: {n_batches} batch(es) of SET operations
(`SET <key> = <value>`), then one final item that lists GET queries.

Rules:
- Each item is printed once and then deleted; it cannot be fetched again.
- A later SET of the same key overrides the earlier value (the latest value wins).
- Do not read or copy anything under /opt/kvstream directly; only use `next`.
- When you have received the GET item, write /app/answers.json: a JSON object mapping
  each queried key to its exact value string (the words after `= `, single spaces, no
  trailing spaces). A key you cannot recall may map to "".

Your score is the fraction of GET keys whose value is exactly right.
"""

TEST_SH = """\
#!/bin/bash
mkdir -p /logs/verifier
python3 /tests/grade.py
"""

GRADE_PY = r'''import json
exp = json.load(open("/tests/expected.json"))
try:
    got = json.load(open("/app/answers.json"))
    if not isinstance(got, dict):
        got = {}
except Exception:
    got = {}
norm = lambda s: " ".join(str(s).split())
ok = {k: norm(got.get(k, "")) == norm(v) for k, v in exp.items()}
score = sum(ok.values()) / max(len(ok), 1)
open("/logs/verifier/reward.txt", "w").write(f"{score:.6f}\n")
json.dump({"score": score, "n": len(ok), "correct": sum(ok.values()), "per_key": ok},
          open("/logs/verifier/details.json", "w"), indent=1)
print(f"kvstream score {score:.4f} ({sum(ok.values())}/{len(ok)})")
'''

TASK_TOML = """\
schema_version = "1.3"
artifacts = []

[task]
name = "local/{name}"
description = "kvstream approximation of ContextBench KV Store (pressure {pressure}x, seed {seed})"
authors = []
keywords = ["context", "kvstream"]

[metadata]
pressure = {pressure}
seed = {seed}
n_batches = {n_batches}
batch_size = {batch_size}
n_get = {n_get}
approx_stream_tokens = {approx_tokens}

[verifier]
timeout_sec = 120.0
collect = []

[verifier.env]

[agent]
timeout_sec = {agent_timeout}

[environment]
network_mode = "public"  # "no-network" needs Harbor's egress sidecar, built with docker buildx (not installed here)
build_timeout_sec = 600.0
os = "linux"
mcp_servers = []

[environment.env]

[solution.env]
"""

DOCKERFILE = """\
FROM python:3.12-slim
COPY stream.jsonl /opt/kvstream/stream.jsonl
COPY next /usr/local/bin/next
RUN chmod +x /usr/local/bin/next && mkdir -p /app
WORKDIR /app
"""


def word(rng: random.Random) -> str:
    return "".join(rng.choice(SYLL) for _ in range(rng.randint(2, 3)))


def build(out: Path, name: str, pressure: float, seed: int, batch_size: int, n_get: int,
          overwrite_frac: float, limit: int, n_batches: int | None = None) -> dict:
    rng = random.Random(f"{seed}-{pressure}-{batch_size}")
    if n_batches is None:
        n_batches = max(1, math.ceil(pressure * limit / (batch_size * TOK_PER_SET)))
    store: dict[str, str] = {}
    keys: list[str] = []
    batches: list[list[str]] = []
    for _ in range(n_batches):
        lines = []
        for _ in range(batch_size):
            if keys and rng.random() < overwrite_frac:
                k = rng.choice(keys)
            else:
                k = f"k-{rng.getrandbits(32):08x}"
                keys.append(k)
            v = " ".join(word(rng) for _ in range(24))
            store[k] = v
            lines.append(f"SET {k} = {v}")
        batches.append(lines)
    queried = rng.sample(keys, min(n_get, len(keys)))
    total = n_batches + 1
    items = [{"kind": "SET", "total": total, "text": "\n".join(b)} for b in batches]
    items.append({"kind": "GET", "total": total,
                  "text": "GET queries (answer all in /app/answers.json):\n"
                          + "\n".join(f"GET {k}" for k in queried)})
    d = out / name
    if d.exists():
        shutil.rmtree(d)
    (d / "environment").mkdir(parents=True)
    (d / "tests").mkdir()
    (d / "solution").mkdir()
    (d / "environment" / "stream.jsonl").write_text("\n".join(json.dumps(i) for i in items) + "\n")
    (d / "environment" / "next").write_text(NEXT_SCRIPT)
    (d / "environment" / "Dockerfile").write_text(DOCKERFILE)
    (d / "tests" / "expected.json").write_text(json.dumps({k: store[k] for k in queried}, indent=1))
    (d / "tests" / "grade.py").write_text(GRADE_PY)
    (d / "tests" / "test.sh").write_text(TEST_SH)
    (d / "solution" / "solve.sh").write_text(
        "#!/bin/bash\n# oracle (harbor -a oracle): writes the expected answers; checks the grader\n"
        "cat > /app/answers.json <<'EOF'\n"
        + json.dumps({k: store[k] for k in queried}, indent=1) + "\nEOF\n")
    for p in (d / "tests" / "test.sh", d / "solution" / "solve.sh"):
        p.chmod(p.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    (d / "instruction.md").write_text(INSTRUCTION.format(total=total, n_batches=n_batches))
    approx = n_batches * batch_size * TOK_PER_SET
    agent_timeout = max(1800, 600 * total)
    (d / "task.toml").write_text(TASK_TOML.format(
        name=name, pressure=pressure, seed=seed, n_batches=n_batches, batch_size=batch_size,
        n_get=len(queried), approx_tokens=approx, agent_timeout=float(agent_timeout)))
    return {"name": name, "n_batches": n_batches, "items": total, "approx_stream_tokens": approx}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out")
    ap.add_argument("--pressure", type=float, nargs="+", default=[1.0, 2.0, 4.0])
    ap.add_argument("--seeds", type=int, nargs="+", default=[0])
    ap.add_argument("--batch-size", type=int, default=100)
    ap.add_argument("--n-get", type=int, default=24)
    ap.add_argument("--overwrite-frac", type=float, default=0.1)
    ap.add_argument("--limit", type=int, default=32768)
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    made = []
    if a.smoke:
        made.append(build(out, "kvstream-smoke", 0.0, 0, 8, 3, 0.0, a.limit, n_batches=1))
    else:
        for p in a.pressure:
            for s in a.seeds:
                tag = f"{p:g}".replace(".", "p")
                made.append(build(out, f"kvstream-p{tag}-s{s}", p, s, a.batch_size, a.n_get,
                                  a.overwrite_frac, a.limit))
    for m in made:
        print(json.dumps(m))


if __name__ == "__main__":
    main()
