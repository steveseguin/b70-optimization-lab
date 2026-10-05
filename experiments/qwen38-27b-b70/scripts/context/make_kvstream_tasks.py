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
  * the verifier compares against the expected values (copied into the sandbox only at
    verification time) and writes the fraction of exact matches to reward.txt.

Two size modes:
  --pressure P   (first comparison, kept for reproducibility) stream ~ P x --limit tokens,
                 old instruction text, no storage rule, legacy `next`.
  --tokens N     (second comparison) stream of about N tokens of the SERVED model's
                 tokenizer (Qwen3.8 tokenizer.json via `tokenizers`; fallback o200k x 1.09),
                 with --mode memory|notes:
      memory  stream data may live only in the agent's context. Enforced by `next` (it refuses
              to write into a regular file or into a `tee`, without consuming the item) and
              audited by the grader: any file created/changed after the image build (except
              /app/answers.json, the harness mirror /tmp/.live_ctx/LIVE_CTX_MAIN.txt and the
              improved agent's pinned state /tmp/.live_ctx/STATE.txt, both shown to the model
              every call and counted in its context) that
              holds any 4 consecutive words of any SET value voids the run (reward 0; the raw
              score is still reported). Exported shell variables land in the harness state
              file, so they are caught too. Files written and deleted again before the end
              are not seen by the grader; summarize_results.py flags commands that redirect
              or tee `next` output.
      notes   files are explicitly allowed (external memory is its own strategy); the grader
              reports how many queried values were stored in files ("stored_frac").
  Both modes: `next` logs every delivery (stdout kind, sibling processes, broken pipe) to
  /opt/kvstream/delivery.log; the grader reports correct / blank / wrong / stale answers
  (stale = an older value of the same key) and the delivery stats.

Usage:
  make_kvstream_tasks.py OUT_DIR [--pressure 1 2 4] [--seeds 0 1] [--batch-size 100]
                         [--n-get 24] [--overwrite-frac 0.1] [--limit 32768]
  make_kvstream_tasks.py OUT_DIR --tokens 60000 120000 180000 --mode memory [--seeds 0 1]
  make_kvstream_tasks.py OUT_DIR --smoke [--mode memory]   # one tiny task (1 batch of 8 SETs, 3 GETs)
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import shutil
import stat
from pathlib import Path

SYLL = ["ka", "lo", "mi", "ne", "ru", "ta", "vo", "zi", "pe", "su", "do", "fa", "gu", "hi",
        "ja", "ke", "ba", "co", "di", "ro", "sa", "tu", "we", "yo", "xa", "qi", "mo", "ni"]

# tokens per SET line, measured with tiktoken o200k_base (the harness ruler): ~59
TOK_PER_SET = 60
# Qwen3.8 tokens / o200k tokens on this text, measured on the first comparison's p4 stream.
QWEN_PER_O200K = 1.09
DEFAULT_TOKENIZER = "/mnt/fast-ai/llm-models/qwen3.8-27b-fp8/tokenizer.json"

# ----------------------------------------------------------------------------------------
# `next`, legacy (first comparison) and v2 (storage rule + delivery log)
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

NEXT_SCRIPT_V2 = r'''#!/usr/bin/env python3
"""Deliver the next item of the stream (and delete it from disk)."""
import json, os, stat, sys, time
D = "/opt/kvstream"
P, STATE, LOG = D + "/stream.jsonl", D + "/delivered", D + "/delivery.log"
MODE = open(D + "/mode").read().strip() if os.path.exists(D + "/mode") else "notes"
END = open(D + "/end_text").read() if os.path.exists(D + "/end_text") else "STREAM END: no more items."


def dest():
    try:
        m = os.fstat(1).st_mode
    except OSError:
        return "closed"
    return ("file" if stat.S_ISREG(m) else "pipe" if stat.S_ISFIFO(m) else
            "chardev" if stat.S_ISCHR(m) else "socket" if stat.S_ISSOCK(m) else "other")


def siblings():
    me, pp, out = os.getpid(), os.getppid(), []
    for p in os.listdir("/proc"):
        if not p.isdigit() or int(p) == me:
            continue
        try:
            s = open(f"/proc/{p}/stat").read()
            comm, rest = s[s.index("(") + 1:s.rindex(")")], s[s.rindex(")") + 2:].split()
            if int(rest[1]) == pp:
                out.append(comm)
        except Exception:
            continue
    return sorted(out)


def log(rec):
    rec["t"] = round(time.time(), 3)
    with open(LOG, "a") as f:
        f.write(json.dumps(rec) + "\n")


where, sib = dest(), siblings()
if MODE == "memory" and (where == "file" or "tee" in sib):
    log({"refused": True, "stdout": where, "siblings": sib})
    sys.stderr.write("STORAGE RULE: in this task the stream may not be written to files (no `>`, "
                     "`>>` or `tee` on `next`). Nothing was delivered and the item is still "
                     "waiting; run `next` on its own.\n")
    sys.exit(3)
try:
    lines = open(P).read().splitlines()
except FileNotFoundError:
    lines = []
if not lines:
    log({"end": True, "stdout": where, "siblings": sib})
    print(END)
    sys.exit(0)
item = json.loads(lines[0])
tmp = P + ".tmp"
with open(tmp, "w") as f:
    f.write("\n".join(lines[1:]) + ("\n" if len(lines) > 1 else ""))
os.replace(tmp, P)
n = int(open(STATE).read()) + 1 if os.path.exists(STATE) else 1
open(STATE, "w").write(str(n))
text = f"ITEM {n}/{item['total']} ({item['kind']})\n{item['text']}\n"
if item.get("last"):
    text += "\n" + item["last"] + "\n"
ok = True
try:
    sys.stdout.write(text)
    sys.stdout.flush()
except BrokenPipeError:
    ok = False
log({"n": n, "kind": item["kind"], "chars": len(text), "complete": ok, "stdout": where,
     "siblings": sib})
if not ok:
    try:
        sys.stdout = open(os.devnull, "w")
    except Exception:
        pass
'''

# ----------------------------------------------------------------------------------------
# Instructions
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

INSTRUCTION_V2 = """\
You are connected to a key-value stream. Run the command `next` to receive the next item
of the stream. There are {total} items: {n_batches} batch(es) of {batch_size} SET operations
(`SET <key> = <value>`, each value is 24 words; one batch is about {batch_tokens:,} tokens),
then one final item that lists {n_get} GET queries. The whole stream is about
{stream_tokens:,} tokens.

Rules:
- Each item is printed once and then deleted; it cannot be fetched again.
- A later SET of the same key overrides the earlier value (the latest value wins).
- Every queried key was SET at least once in the stream. You do not know in advance which
  keys will be queried.
- Do not read or copy anything under /opt/kvstream directly; only use `next`.
- When you have received the GET item, write /app/answers.json: a JSON object mapping
  each queried key to its exact value string (the words after `= `, single spaces, no
  trailing spaces). If you no longer know a value, map the key to "" — a blank scores the
  same as a wrong value, but blanks are reported separately as admitted losses.

{storage_rule}
Your score is the fraction of GET keys whose value is exactly right.
"""

STORAGE_MEMORY = """\
Storage rule (enforced, memory-only task): the stream's contents may be kept ONLY in your own
context (this conversation). Do not write stream data — values, keys, SET lines, or notes or
tables derived from them — into any file, environment variable or other storage, except the
final /app/answers.json. Do not redirect (`>`, `>>`) or `tee` the output of `next` (`next`
refuses to run that way). You may compute with inline commands that read nothing from disk
(for example `python3 - <<'EOF' ... EOF`). If your harness gives you a conversation mirror
file (/tmp/.live_ctx/LIVE_CTX_MAIN.txt), that file IS your context and editing it is allowed.
A run that stores stream data anywhere else scores 0.
"""

STORAGE_NOTES = """\
Storage: you may keep notes and copies of stream data in files (for example under
/app/notes/); this is allowed and not penalised. Only /app/answers.json is graded.
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

# Shared v2 grader (kv and ledger). Reads /tests/spec.json.
GRADE_PY_V2 = r'''import json, os, re, stat
spec = json.load(open("/tests/spec.json"))
kind, mode, exp = spec["kind"], spec["mode"], spec["expected"]
MIRROR = "/tmp/.live_ctx/LIVE_CTX_MAIN.txt"
STATE = "/tmp/.live_ctx/STATE.txt"  # clm_improved: harness-owned pinned state = context
ANS = "/app/answers.json"
try:
    got = json.load(open(ANS))
    if not isinstance(got, dict):
        got = {}
except Exception:
    got = None
answers = got or {}
norm = lambda s: " ".join(str(s).split())
status = {}
if kind == "kv":
    hist = spec.get("history", {})
    for k, v in exp.items():
        a = norm(answers.get(k, "")) if answers.get(k) is not None else ""
        if a == norm(v):
            status[k] = "correct"
        elif a == "":
            status[k] = "blank"
        elif a in {norm(h) for h in hist.get(k, [])}:
            status[k] = "stale"
        else:
            status[k] = "wrong"
else:
    def as_int(x):
        if isinstance(x, bool):
            return None
        if isinstance(x, int):
            return x
        if isinstance(x, float) and x.is_integer():
            return int(x)
        if isinstance(x, str) and re.fullmatch(r"\s*[+-]?\d+\s*", x):
            return int(x)
        return None
    DELETED = {"", "null", "none", "deleted", "del"}
    for k, v in exp.items():
        present = k in answers
        a = answers.get(k)
        is_del = a is None or (isinstance(a, str) and a.strip().lower() in DELETED)
        if v is None:
            status[k] = "correct" if (present and is_del) else ("blank" if not present else "wrong")
        elif not present or (isinstance(a, str) and a.strip() == ""):
            status[k] = "blank"
        elif as_int(a) == v:
            status[k] = "correct"
        elif as_int(a) is not None and as_int(a) in set(spec.get("history", {}).get(k, [])):
            status[k] = "stale"
        else:
            status[k] = "wrong"
counts = {s: sum(1 for x in status.values() if x == s) for s in ("correct", "blank", "wrong", "stale")}
score = counts["correct"] / max(len(exp), 1)

# ---- files created or changed after the image build
built = os.stat("/opt/kvstream/.built").st_mtime
SKIP = {"/proc", "/sys", "/dev", "/tests", "/logs", "/opt/kvstream", "/run"}
new_files = []
for root, dirs, files in os.walk("/"):
    dirs[:] = [d for d in dirs if os.path.join(root, d) not in SKIP]
    for f in files:
        p = os.path.join(root, f)
        try:
            st = os.lstat(p)
        except OSError:
            continue
        if stat.S_ISREG(st.st_mode) and st.st_mtime > built and st.st_size < (64 << 20):
            new_files.append(p)
WORD = re.compile(r"[a-z]+")
grams, names = set(), set()
if kind == "kv":
    for v in spec["all_values"]:
        w = v.split()
        grams.update(" ".join(w[i:i + 4]) for i in range(len(w) - 3))
else:
    names = set(spec["all_names"])
NAME = re.compile(r"\b[a-z]+[0-9]{2}\b")
holders = []
for p in new_files:
    if p in (MIRROR, STATE):
        continue
    try:
        txt = open(p, "rb").read().decode("utf-8", "replace")
    except Exception:
        continue
    if kind == "kv":
        w = WORD.findall(txt)
        hits = sum(1 for i in range(len(w) - 3) if " ".join(w[i:i + 4]) in grams)
        if hits:
            holders.append({"path": p, "hits": hits})
    else:
        hits = len(set(NAME.findall(txt)) & names)
        if hits >= 3:
            holders.append({"path": p, "hits": hits})
violations = []
if mode == "memory":
    for h in holders:
        if h["path"] == ANS:
            extra = [k for k in answers if k not in exp]
            if extra:
                violations.append({"path": ANS, "reason": f"{len(extra)} keys beyond the queried ones"})
        else:
            violations.append({"path": h["path"], "reason": f"holds stream data ({h['hits']} hits)"})
stored = None
if kind == "kv" and mode == "notes":
    blob = ""
    for p in new_files:
        if p not in (MIRROR, STATE, ANS):
            try:
                blob += open(p, "rb").read().decode("utf-8", "replace") + "\n"
            except Exception:
                pass
    blob = norm(blob)
    stored = sum(1 for v in exp.values() if norm(v) in blob) / max(len(exp), 1)

# ---- delivery log written by `next`
deliv = []
try:
    deliv = [json.loads(l) for l in open("/opt/kvstream/delivery.log")]
except Exception:
    pass
items = [d for d in deliv if "n" in d]
dl = {"items_total": spec["n_items"], "items_delivered": len(items),
      "items_broken_pipe": sum(1 for d in items if not d.get("complete", True)),
      "items_to_file": sum(1 for d in items if d.get("stdout") == "file"),
      "items_with_tee": sum(1 for d in items if "tee" in d.get("siblings", [])),
      "refused": sum(1 for d in deliv if d.get("refused")),
      "calls_after_end": sum(1 for d in deliv if d.get("end"))}
void = bool(violations)
reward = 0.0 if void else score
open("/logs/verifier/reward.txt", "w").write(f"{reward:.6f}\n")
json.dump({"score": reward, "score_raw": score, "void": void, "kind": kind, "mode": mode,
           "n": len(exp), "correct": counts["correct"], "counts": counts,
           "answers_file_ok": got is not None, "per_key": status, "violations": violations,
           "files_holding_data": holders[:50], "n_new_files": len(new_files),
           "new_files": sorted(new_files)[:200],
           "stored_frac": stored, "delivery": dl},
          open("/logs/verifier/details.json", "w"), indent=1)
print(f"{kind} score {reward:.4f} raw {score:.4f} ({counts}) void={void} {violations[:3]} delivery={dl}")
'''

TASK_TOML = """\
schema_version = "1.3"
artifacts = []

[task]
name = "local/{name}"
description = "{description}"
authors = []
keywords = ["context", "{kind}"]

[metadata]
{metadata}

[verifier]
timeout_sec = {verifier_timeout}
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

DOCKERFILE_V2 = """\
FROM python:3.12-slim
COPY stream.jsonl mode end_text /opt/kvstream/
COPY next /usr/local/bin/next
RUN chmod +x /usr/local/bin/next && mkdir -p /app && sleep 1 && touch /opt/kvstream/.built
WORKDIR /app
"""


# ----------------------------------------------------------------------------------------
def word(rng: random.Random) -> str:
    return "".join(rng.choice(SYLL) for _ in range(rng.randint(2, 3)))


class TokenCounter:
    """Counts tokens of the served model (Qwen3.8 tokenizer.json) when available."""

    def __init__(self, path: str | None):
        self.kind = "chars/2.5"
        self._tok = self._enc = None
        if path and os.path.exists(path):
            try:
                from tokenizers import Tokenizer
                self._tok = Tokenizer.from_file(path)
                self.kind = f"tokenizer:{path}"
                return
            except Exception:
                pass
        try:
            os.environ.setdefault("TIKTOKEN_CACHE_DIR", "/mnt/fast-ai/cache/tiktoken")
            import tiktoken
            self._enc = tiktoken.get_encoding("o200k_base")
            self.kind = f"o200k_base x {QWEN_PER_O200K}"
        except Exception:
            pass

    def __call__(self, text: str) -> int:
        if self._tok is not None:
            return len(self._tok.encode(text).ids)
        if self._enc is not None:
            return int(len(self._enc.encode(text, disallowed_special=())) * QWEN_PER_O200K)
        return int(len(text) / 2.5)


def write_task(d: Path, *, items: list[dict], spec: dict, answers_oracle: dict, instruction: str,
               mode: str, end_text: str, metadata: dict, description: str, kind: str) -> None:
    """Write one v2 Harbor task directory (shared by the kv and ledger generators)."""
    if d.exists():
        shutil.rmtree(d)
    (d / "environment").mkdir(parents=True)
    (d / "tests").mkdir()
    (d / "solution").mkdir()
    (d / "environment" / "stream.jsonl").write_text("\n".join(json.dumps(i) for i in items) + "\n")
    (d / "environment" / "next").write_text(NEXT_SCRIPT_V2)
    (d / "environment" / "mode").write_text(mode + "\n")
    (d / "environment" / "end_text").write_text(end_text + "\n")
    (d / "environment" / "Dockerfile").write_text(DOCKERFILE_V2)
    (d / "tests" / "spec.json").write_text(json.dumps(spec))
    (d / "tests" / "expected.json").write_text(json.dumps(spec["expected"], indent=1))
    (d / "tests" / "grade.py").write_text(GRADE_PY_V2)
    (d / "tests" / "test.sh").write_text(TEST_SH)
    (d / "solution" / "solve.sh").write_text(
        "#!/bin/bash\n# oracle (harbor -a oracle): writes the expected answers; checks the grader\n"
        "cat > /app/answers.json <<'EOF'\n" + json.dumps(answers_oracle, indent=1) + "\nEOF\n")
    for p in (d / "tests" / "test.sh", d / "solution" / "solve.sh"):
        p.chmod(p.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    (d / "instruction.md").write_text(instruction)
    n_items = len(items)
    agent_timeout = max(3600, 900 * n_items)
    md = dict(metadata)
    md.update(n_items=n_items, n_batches=n_items - 1, mode=mode, kind=kind,
              max_item_chars=max(len(i["text"]) for i in items) + 200)
    md_txt = "\n".join(f"{k} = {json.dumps(v)}" for k, v in md.items())
    (d / "task.toml").write_text(TASK_TOML.format(
        name=d.name, description=description, kind=kind, metadata=md_txt,
        agent_timeout=float(agent_timeout), verifier_timeout=300.0))


def build(out: Path, name: str, pressure: float, seed: int, batch_size: int, n_get: int,
          overwrite_frac: float, limit: int, n_batches: int | None = None) -> dict:
    """Legacy (first comparison) task: pressure x limit, no storage rule."""
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
    md = (f"pressure = {pressure}\nseed = {seed}\nn_batches = {n_batches}\nbatch_size = {batch_size}\n"
          f"n_get = {len(queried)}\napprox_stream_tokens = {approx}")
    (d / "task.toml").write_text(TASK_TOML.format(
        name=name, kind="kvstream", metadata=md, agent_timeout=float(agent_timeout), verifier_timeout=120.0,
        description=f"kvstream approximation of ContextBench KV Store (pressure {pressure}x, seed {seed})"))
    return {"name": name, "n_batches": n_batches, "items": total, "approx_stream_tokens": approx}


def build_v2(out: Path, name: str, target_tokens: int, seed: int, batch_size: int, n_get: int,
             overwrite_frac: float, mode: str, count: TokenCounter,
             n_batches: int | None = None) -> dict:
    """Second-comparison kv task: about `target_tokens` served-model tokens of SET batches."""
    rng = random.Random(f"kv2-{seed}-{target_tokens}-{batch_size}")
    store: dict[str, str] = {}
    history: dict[str, list[str]] = {}
    keys: list[str] = []
    batches: list[str] = []
    tokens = 0
    while True:
        lines = []
        for _ in range(batch_size):
            if keys and rng.random() < overwrite_frac:
                k = rng.choice(keys)
                history.setdefault(k, []).append(store[k])
            else:
                k = f"k-{rng.getrandbits(32):08x}"
                keys.append(k)
            v = " ".join(word(rng) for _ in range(24))
            store[k] = v
            lines.append(f"SET {k} = {v}")
        text = "\n".join(lines)
        t = count(text)
        batches.append(text)
        tokens += t
        if n_batches is not None:
            if len(batches) >= n_batches:
                break
        elif tokens + t / 2 >= target_tokens:
            break
    # Query a mix: about a third of the queried keys were overwritten at least once.
    over = [k for k in keys if k in history]
    n_over = min(len(over), n_get // 3)
    queried = rng.sample(over, n_over) + rng.sample([k for k in keys if k not in history],
                                                    min(n_get - n_over, len(keys) - len(over)))
    rng.shuffle(queried)
    total = len(batches) + 1
    items = [{"kind": "SET", "total": total, "text": b} for b in batches]
    items.append({"kind": "GET", "total": total,
                  "text": "GET queries (answer all in /app/answers.json):\n"
                          + "\n".join(f"GET {k}" for k in queried),
                  "last": "This was the last item. Write /app/answers.json now."})
    exp = {k: store[k] for k in queried}
    all_values = sorted({v for b in batches for v in
                         (ln.split(" = ", 1)[1] for ln in b.splitlines())})
    spec = {"kind": "kv", "mode": mode, "expected": exp,
            "history": {k: history.get(k, []) for k in queried},
            "all_values": all_values, "n_items": total}
    batch_tokens = tokens // len(batches)
    instr = INSTRUCTION_V2.format(
        total=total, n_batches=len(batches), batch_size=batch_size, batch_tokens=batch_tokens,
        n_get=len(queried), stream_tokens=tokens,
        storage_rule=STORAGE_MEMORY if mode == "memory" else STORAGE_NOTES)
    write_task(out / name, items=items, spec=spec, answers_oracle=exp, instruction=instr, mode=mode,
               end_text="STREAM END: no more items. Answer the GET queries in /app/answers.json, then submit.",
               metadata={"seed": seed, "target_tokens": target_tokens, "stream_tokens": tokens,
                         "token_counter": count.kind, "batch_size": batch_size,
                         "batch_tokens": batch_tokens, "n_get": len(queried),
                         "n_overwritten_queried": n_over},
               description=f"kvstream v2, {mode}, ~{tokens} tokens, seed {seed}", kind="kvstream")
    return {"name": name, "mode": mode, "n_batches": len(batches), "items": total,
            "stream_tokens": tokens, "token_counter": count.kind}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out")
    ap.add_argument("--pressure", type=float, nargs="+", default=None)
    ap.add_argument("--tokens", type=int, nargs="+", default=None,
                    help="v2: target stream sizes in served-model tokens (e.g. 60000 120000 180000)")
    ap.add_argument("--mode", choices=["memory", "notes"], default="memory", help="v2 storage rule")
    ap.add_argument("--tokenizer", default=DEFAULT_TOKENIZER)
    ap.add_argument("--seeds", type=int, nargs="+", default=[0])
    ap.add_argument("--batch-size", type=int, default=100)
    ap.add_argument("--n-get", type=int, default=24)
    ap.add_argument("--overwrite-frac", type=float, default=0.1)
    ap.add_argument("--limit", type=int, default=32768)
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--refresh-graders", action="store_true",
                    help="only rewrite tests/grade.py of the v2 tasks under OUT_DIR (stream untouched)")
    a = ap.parse_args()
    out = Path(a.out)
    if a.refresh_graders:
        n = 0
        for g in sorted(out.glob("**/tests/grade.py")):
            if (g.parent / "spec.json").exists() and g.read_text() != GRADE_PY_V2:
                g.write_text(GRADE_PY_V2)
                n += 1
        print(json.dumps({"refreshed_graders": n, "root": str(out)}))
        return
    out.mkdir(parents=True, exist_ok=True)
    made = []
    if a.smoke:
        if a.tokens is not None:  # v2 smoke: one tiny task with the storage rule
            made.append(build_v2(out, f"kv-{a.mode}-smoke", 0, 0, 8, 3, 0.0, a.mode,
                                 TokenCounter(a.tokenizer), n_batches=1))
        else:
            made.append(build(out, "kvstream-smoke", 0.0, 0, 8, 3, 0.0, a.limit, n_batches=1))
    elif a.tokens is not None:
        count = TokenCounter(a.tokenizer)
        for n in a.tokens:
            for s in a.seeds:
                made.append(build_v2(out, f"kv-{a.mode}-t{n // 1000}k-s{s}", n, s, a.batch_size,
                                     a.n_get, a.overwrite_frac, a.mode, count))
    else:
        for p in (a.pressure or [1.0, 2.0, 4.0]):
            for s in a.seeds:
                tag = f"{p:g}".replace(".", "p")
                made.append(build(out, f"kvstream-p{tag}-s{s}", p, s, a.batch_size, a.n_get,
                                  a.overwrite_frac, a.limit))
    for m in made:
        print(json.dumps(m))


if __name__ == "__main__":
    main()
