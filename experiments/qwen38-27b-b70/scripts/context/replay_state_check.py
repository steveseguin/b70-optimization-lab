#!/usr/bin/env python3
"""Per-batch state check of a finished ledger or prose-ledger trial (CPU only).

Follow-up item 1 of notes/2026-10-05-context-followup-ideas.md: prove that every delivered update
became committed state. For each context snapshot (one per model call) the agent's working state is
extracted and compared with the generator's reference state after the batches delivered so far.

Agent state, from the snapshot messages (the last one found wins):
  * the improved agent's pinned STATE.txt message ("[[PINNED STATE ...]]", lines "name value");
  * a state block the model keeps itself: JSON {"name": value, ...} (e.g. between ===STATE=== and
    ===ENDSTATE===), @@STn@@ ... @@STnE@@ blocks, or any run of >= 10 lines "name value" /
    "name: value" / "name = value".
Reference: tests/reference.json of a prose-ledger task (state + true operations after every batch,
including recorded distractors), or, for the line-format ledger, recomputed from stream.jsonl.

The snapshot is matched to "after k batches" with k = the number of batches delivered so far, or one
less (the newest batch may not be folded yet), whichever agrees better. Every counter that newly
disagrees is classified, using the operations of that batch on that counter:
  missed update     the agent value equals the truth with one operation (or all) left out
  missed delete     the reference deleted the counter, the agent still holds it
  applied twice     equals the truth with one operation applied twice
  distractor applied equals the truth with a recorded distractor applied as an add/subtract/set
  wrong counter     equals the true value of a different counter
  dropped counter   the agent lost a counter the reference holds
  lost at an edit   the batch did not touch the counter, yet its value changed from a correct one
  wrong arithmetic  none of the above, within 10 % (+5) of the truth
  other             none of the above
A divergence whose counter is right again by the last compared state (repaired, or overwritten by a
later set) is reported as "transient", apart from the persistent ones. Final answers are checked against the last extracted state ("answer lookup"
errors: answers wrong although the final state held the right value).

  replay_state_check.py TRIAL_DIR|JOB_DIR|runs/ [...] [--json out.json]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

NAME = r"[a-z]+\d\d"
PIN_TAG = "[[PINNED STATE"
LINE = re.compile(rf"^\s*[\"']?({NAME})[\"']?\s*[:=]?\s*(-?\d+|null|None|deleted)\s*,?\s*$")
ITEM = re.compile(r"(?:ITEM |\bn=)(\d+)/(\d+)\b")   # "ITEM 3/20 (" or a parser's "n=3/20"
LEDGER_LINE = re.compile(r"^(SET|ADD|DEL) (\S+)(?: (-?\d+))? \|")


def load(p: Path):
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def parse_lines(text: str) -> dict | None:
    st, n = {}, 0
    for ln in text.splitlines():
        m = LINE.match(ln)
        if m:
            v = m.group(2)
            st[m.group(1)] = int(v) if re.fullmatch(r"-?\d+", v) else None
            n += 1
    return st if n >= 10 else None


def extract_state(messages: list) -> dict | None:
    found = None
    for m in messages:
        c = m.get("content") if isinstance(m, dict) else None
        if not isinstance(c, str):
            continue
        if c.startswith(PIN_TAG):
            body = c.split("\n", 1)[1] if "\n" in c else ""
            body = body.split("\n--- ")[0]
            st = parse_lines(body)
            if st is None:
                try:
                    dj = json.loads(body.strip().split("\n[STATE.txt")[0])
                    if isinstance(dj, dict) and len(dj) >= 10:
                        st = dj
                except Exception:
                    pass
            if st is not None:
                found = st
            continue
        for blk in re.findall(r"@@ST\w*@@\n(.*?)\n@@ST\w*E@@", c, re.S):
            st = parse_lines(blk)
            if st is not None:
                found = st
        for js in re.findall(r"\{[^{}]{80,}\}", c, re.S):
            try:
                d = json.loads(js)
            except Exception:
                continue
            if isinstance(d, dict) and sum(1 for k in d if re.fullmatch(NAME, str(k))) >= 10 and \
                    all(v is None or isinstance(v, int) for v in d.values()):
                found = {k: v for k, v in d.items()}
        if found is None or c.count("\n") > 15:
            st = parse_lines(c)
            if st is not None and "ITEM " not in c[:20]:
                found = st
    if found is not None:
        found = {k: v for k, v in found.items() if v is not None}
    return found


def ledger_reference(task: Path) -> list[dict]:
    items = [json.loads(l) for l in (task / "environment" / "stream.jsonl").read_text().splitlines()]
    ref = load(task / "tests" / "reference.json")
    if ref:
        return ref["after_batch"]
    out, st = [], {}
    for it in items[:-1]:
        ops = []
        for ln in it["text"].splitlines():
            m = LEDGER_LINE.match(ln)
            if not m:
                continue
            op, nm, v = m.groups()
            if op == "SET":
                st[nm] = int(v); ops.append([nm, "set", int(v), st[nm], 0])
            elif op == "ADD":
                st[nm] = st.get(nm, 0) + int(v); ops.append([nm, "add", int(v), st[nm], 0])
            else:
                st.pop(nm, None); ops.append([nm, "del", None, None, 0])
        out.append({"state": dict(st), "ops": ops})
    return out


def step(v, op, arg, delta):
    if op in ("set", "correct"):
        return arg
    if v is None:
        return None
    if op == "add":
        return v + arg
    if op == "del":
        return None
    if op == "double":
        return v * 2
    if op == "third":
        return v - v // 3
    if op == "from":
        return v + delta
    return v


def classify(c, agent_v, truth_v, before_v, ops, ref_state):
    """ops: this batch's operations on counter c, in order (incl. distractors)."""
    real = [o for o in ops if o[1] != "distractor"]
    deltas, v = [], before_v
    for o in real:
        nv = o[3] if o[1] != "del" else None
        deltas.append((nv - v) if (o[1] == "from" and nv is not None and v is not None) else None)
        v = nv
    def run(seq):
        v = before_v
        for (o, d) in seq:
            v = step(v, o[1], o[2], d)
        return v
    pairs = list(zip(real, deltas))
    if truth_v is None and agent_v is not None:
        return "missed delete"
    if agent_v is None:
        return "dropped counter"
    if not real:
        return "lost at an edit"
    if run([]) == agent_v:
        return "missed update"
    for i in range(len(pairs)):
        if run(pairs[:i] + pairs[i + 1:]) == agent_v:
            return "missed update"
        if run(pairs[:i + 1] + pairs[i:]) == agent_v:
            return "applied twice"
    for d in (o for o in ops if o[1] == "distractor"):
        n = d[2]
        if agent_v in (truth_v + n, truth_v - n, n):
            return "distractor applied"
    if abs(agent_v) > 9 and any(v == agent_v for k, v in ref_state.items() if k != c):
        return "wrong counter"
    if abs(agent_v - truth_v) <= abs(truth_v) * 0.1 + 5:
        return "wrong arithmetic"
    return "other"


def check_trial(t: Path) -> dict:
    cfg = load(t / "config.json") or {}
    task = Path(cfg["task"]["path"])
    ref = ledger_reference(task)
    states = [{}] + [r["state"] for r in ref]
    nb = len(ref)
    snaps = sorted((t / "agent" / "context_snapshots").glob("turn-*.json"))
    delivered, prev_key, prev_ok = 0, None, {}
    rows, classes, first_div = [], {}, None
    diffsets, events = [], []
    last_state = None
    for s in snaps:
        d = load(s) or {}
        msgs = d.get("messages") or []
        for m in msgs:
            c = m.get("content")
            if isinstance(c, str) and m.get("role") in ("tool", "user"):
                for mm in ITEM.finditer(c):
                    delivered = max(delivered, min(int(mm.group(1)), nb))
        st = extract_state(msgs)
        if st is None:
            continue
        key = json.dumps(st, sort_keys=True)
        if key == prev_key:
            continue
        prev_key = key
        last_state = st
        best = None
        for k in {max(delivered - 1, 0), delivered}:
            diff = [c for c in set(states[k]) | set(st) if states[k].get(c) != st.get(c)]
            if best is None or len(diff) < len(best[1]):
                best = (k, diff)
        k, diff = best
        if len(st) < 0.5 * len(states[k]):
            continue                          # e.g. the final answers JSON (24 keys), not a state
        diffsets.append(set(diff))
        new = []
        for c in diff:
            if prev_ok.get(c) is False:
                continue                      # already counted when it first went wrong
            ops = [o for o in ref[k - 1]["ops"] if o[0] == c] if k >= 1 else []
            cls = classify(c, st.get(c), states[k].get(c), states[k - 1].get(c) if k >= 1 else None,
                           ops, states[k])
            new.append((c, cls, st.get(c), states[k].get(c)))
            events.append((len(diffsets) - 1, c, cls))
            if first_div is None:
                first_div = {"snapshot": s.name, "batch": k, "counter": c, "class": cls,
                             "agent": st.get(c), "truth": states[k].get(c)}
        prev_ok = {c: (c not in diff) for c in set(states[k]) | set(st)}
        rows.append({"snapshot": s.name, "batch": k, "delivered": delivered, "counters": len(st),
                     "wrong": len(diff), "new": new[:8]})
    # a divergence repaired at the next compared state is "transient" (counted apart)
    transient = {}
    for i, c, cls in events:
        if diffsets and c not in diffsets[-1]:   # right again by the last compared state
            transient[cls] = transient.get(cls, 0) + 1
        else:
            classes[cls] = classes.get(cls, 0) + 1
            if first_div is not None and first_div.get("persistent") is None and first_div["counter"] == c:
                first_div["persistent"] = True
    # final answers vs the last extracted state
    ans_lookup = None
    det = load(t / "verifier" / "details.json") or {}
    exp = load(task / "tests" / "expected.json") or {}
    if last_state is not None and det.get("per_key"):
        ans_lookup = sum(1 for k, v in exp.items()
                         if det["per_key"].get(k) != "correct" and last_state.get(k) == v)
    return {"trial": str(t), "batches": nb, "states_compared": len(rows), "first_divergence": first_div,
            "classes": classes, "transient": transient, "final_state_wrong": rows[-1]["wrong"] if rows else None,
            "final_state_batch": rows[-1]["batch"] if rows else None,
            "answers_wrong_though_state_right": ans_lookup, "rows": rows}


def trials(paths):
    out = []
    for p in paths:
        p = Path(p)
        if (p / "agent").is_dir():
            out.append(p)
        elif p.is_dir():
            out += trials(sorted(x for x in p.iterdir() if x.is_dir()))
    return out


def main() -> None:
    args = sys.argv[1:]
    out_json = None
    if "--json" in args:
        i = args.index("--json"); out_json = args[i + 1]; del args[i:i + 2]
    res = []
    for t in trials(args):
        r = check_trial(t)
        res.append(r)
        print(f"{Path(r['trial']).parent.name}: batches={r['batches']} states={r['states_compared']} "
              f"final_state_batch={r['final_state_batch']} final_wrong={r['final_state_wrong']} "
              f"persistent={r['classes']} transient={r['transient']} answer_lookup_errors={r['answers_wrong_though_state_right']}")
        if r["first_divergence"]:
            print("   first divergence:", r["first_divergence"])
    if out_json:
        Path(out_json).write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
