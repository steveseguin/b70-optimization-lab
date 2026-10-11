#!/usr/bin/env python3
"""What keyword retrieval can reach on a sparse-prose task, measured without a GPU (2026-10-11). AN UPPER BOUND.

For every question of the task, the passages a correct answer needs are worked out from the grader's reference
(every sentence that changed the counter since it was last set, the sentence that names who did something, the rule
sentences, the method sentence), the store is filled with the items that would be out of view (older than --in-view
items; items that only ask questions are not stored, as in the live index, unless --with-questions), and the
question is searched. A question is "covered" when
every needed passage is either still in view, among the retrieved ones, or (with --window N) one of the N sentences
after a retrieved one. Covered is necessary, not sufficient: the model still has to replay the changes correctly,
and the live arm also trims the message to the room left in the window, which this does not model.

  rag_coverage.py TASK_DIR [--k 10 20 40] [--unit sentence] [--in-view 10] [--floor 0] [--window 1]
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from rag_retrieve import Index, sentences, paragraphs   # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("task")
    ap.add_argument("--k", type=int, nargs="+", default=[10, 20, 40])
    ap.add_argument("--unit", default="sentence")
    ap.add_argument("--in-view", type=int, default=10)
    ap.add_argument("--floor", type=float, default=0.0)
    ap.add_argument("--with-questions", action="store_true", help="also store the PROBE items (earlier questions)")
    ap.add_argument("--window", type=int, default=1, help="sentences after a match that are shown with it [1, as the arms]")
    ap.add_argument("--json")
    a = ap.parse_args()
    t = Path(a.task)
    rows = [json.loads(l) for l in open(t / "environment/stream.jsonl")]
    ref = json.load(open(t / "tests/reference.json"))
    spec = json.load(open(t / "tests/spec.json"))
    split = sentences if a.unit == "sentence" else paragraphs
    item_of_batch = {int(b): n for b, n in ref["item_no"].items()}            # batch (1-based) -> item number
    text_of = {n + 1: r["text"] for n, r in enumerate(rows) if r["kind"] == "UPDATE"}
    stored = {n + 1: r["text"] for n, r in enumerate(rows) if r["kind"] == "UPDATE" or (a.with_questions and r["kind"] == "PROBE")}
    # per counter: [(item number, op, passage)] in order
    hist: dict[str, list[tuple[int, str, str]]] = {}
    for b, rec in enumerate(ref["after_batch"], 1):
        item = item_of_batch[b]
        parts = split(text_of[item])
        used: dict[str, int] = {}
        for op in rec["ops"]:
            name, kind = op[0], op[1]
            cands = [p for p in parts if re.search(rf"\b{name}\b", p, re.I)]
            j = used.get(name, 0)
            used[name] = j + 1
            hist.setdefault(name, []).append((item, kind, cands[min(j, len(cands) - 1)] if cands else ""))
    rule_parts = [(n, p) for n in sorted(text_of)[:3] for p in split(text_of[n]) if "confidential" in p or "single word" in p]
    method_parts = [(n, p) for n in sorted(text_of)[:3] for p in split(text_of[n]) if "tally of a counter" in p]

    def needed(name: str, upto: int) -> list[tuple[int, str]]:
        ops = [h for h in hist.get(name, []) if h[0] <= upto]
        last_set = max((i for i, h in enumerate(ops) if h[1] in ("set", "open", "del", "delete", "remove")), default=0)
        return [(h[0], h[2]) for h in ops[last_set:]]

    qs = []      # (key, type, question item, query text, needed passages)
    for key, p in ref["probes"].items():
        q, typ, at, ri = p["q"], p["type"], p["item"], p.get("ref_item") or p["item"]
        m = re.search(r"\b[a-z]{3,8}\d\d\b", q)
        asof = re.search(r"(?:As of|end of) item (\d+)", q)
        upto = int(asof.group(1)) if asof else at
        if typ == "who":
            need = [(ri, s) for s in split(text_of[ri]) if str(p["a"]).lower() in s.lower()
                    and sum(w in s.lower() for w in re.findall(r"[a-z]{4,}", q.lower())) >= 3][:1]
        elif typ == "rule":
            need = rule_parts
        elif typ == "procedure" and m:
            need = method_parts + needed(m.group(0), upto)
        elif m:
            need = needed(m.group(0), upto)
        else:                                    # a small detail of an item (a number in the narrative): not modelled
            continue
        qs.append((key, typ, at, q, need))
    final_item = len(rows)
    for name in [k for k in spec["expected"] if not re.fullmatch(r"p\d+_\d+", k)]:
        prot = name in (spec.get("rules") or {}).get("protected", [])
        qs.append((name, "final-rule" if prot else "final", final_item, name, rule_parts if prot else needed(name, final_item)))

    res = {}
    for k in a.k:
        tab: dict[str, list[int]] = {}
        idx, added = Index(a.unit), 0
        for key, typ, at, q, need in sorted(qs, key=lambda x: x[2]):
            horizon = at - a.in_view                                  # items below this are out of view
            for n in sorted(stored):
                if added < n < horizon:
                    idx.add(n, stored[n])
                    added = n
            got = set()
            for _, n, p, i in idx.search(q, k, a.floor):
                got.add((n, p))
                got.update(idx.docs[j] for j in range(i + 1, min(i + 1 + a.window, len(idx.docs))) if idx.docs[j][0] == n)
            ok = bool(need) and all(n >= horizon or (n, p) in got for n, p in need)
            c = tab.setdefault(typ, [0, 0, 0])
            c[0] += ok
            c[1] += 1
            c[2] += sum(1 for n, _ in need if n < horizon)
        res[k] = tab
        print(f"k={k} ({a.unit}, window {a.window}, newest {a.in_view} items in view): " + "  ".join(
            f"{typ} {c[0]}/{c[1]} (needs {c[2] / c[1]:.1f} from the store)" for typ, c in sorted(tab.items())),
            f"  ALL {sum(c[0] for c in tab.values())}/{sum(c[1] for c in tab.values())}")
    if a.json:
        Path(a.json).write_text(json.dumps(res, indent=1) + "\n")


if __name__ == "__main__":
    main()
