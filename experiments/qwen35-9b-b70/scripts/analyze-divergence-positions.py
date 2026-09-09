#!/usr/bin/env python3
"""Characterise where and how concurrent requests diverge from the sequential oracle.

The powered arms establish a divergence rate but say nothing about the divergences themselves. This
reads the token arrays already captured in each ladder and reports, for every divergent request, the
position of the first differing token and the pair of token ids substituted there.

That is the cheap half of the question the identity ladders cannot answer: whether these are single
isolated substitutions or the point where two continuations part, and whether the same token pairs
recur - which is what a near-tie between two specific candidates would look like.

Needs no GPU: everything is already in the ladder files.

usage: analyze-divergence-positions.py ROOT [ROOT ...] [--lane ladder-mtp0] [--json OUT]
"""
from __future__ import annotations

import collections
import difflib
import json
import sys
from pathlib import Path


def classify(ref: list[int], got: list[int]) -> dict:
    """Align two token streams and name the edit that separates them.

    First-differing-index alone cannot tell a substitution from a shift: when a token is inserted, every
    later position differs even though the content after it is unchanged, and the request is then filed
    as "rest differs" alongside genuine content divergence. That misread hid the inserted-token signature
    in the 4B c64 MTP0 flips (2026-09-09), so classification here is alignment-based.

    Both streams are capped at the same max_tokens, so an insertion of n tokens necessarily pushes n
    tokens off the end of the response. A trailing edit that only removes that overhang is the cap
    showing through, not a second defect, and is discounted before the edit is named.
    """
    sm = difflib.SequenceMatcher(a=ref, b=got, autojunk=False)
    ops = [o for o in sm.get_opcodes() if o[0] != "equal"]
    ratio = sm.ratio()
    trimmed = list(ops)
    if len(trimmed) > 1:
        tag, i1, i2, j1, j2 = trimmed[-1]
        at_end = i2 == len(ref) and j2 == len(got)
        net = sum((j2_ - j1_) - (i2_ - i1_) for _, i1_, i2_, j1_, j2_ in trimmed[:-1])
        if at_end and tag in ("delete", "insert") and (i2 - i1) + (j2 - j1) == abs(net):
            trimmed = trimmed[:-1]
    if len(trimmed) == 1:
        tag, i1, i2, j1, j2 = trimmed[0]
        n_ref, n_got = i2 - i1, j2 - j1
        if tag == "insert":
            kind = f"insertion({n_got})"
        elif tag == "delete":
            kind = f"deletion({n_ref})"
        elif n_ref == n_got == 1:
            kind = "substitution(1)"
        else:
            kind = f"replacement({n_ref}->{n_got})"
    elif trimmed and trimmed[0][0] in ("insert", "delete"):
        kind = "shift-then-drift"
    else:
        kind = "content-divergence"
    return {
        "kind": kind,
        "similarity": round(ratio, 4),
        "edit_count": len(trimmed),
        "edits": [{"op": t, "oracle": [a, b], "got": [c, d]} for t, a, b, c, d in trimmed[:6]],
    }


def analyse(root: Path, lane: str):
    p = root / lane / "ladder.json"
    if not p.exists():
        return None
    d = json.loads(p.read_text())
    oracle = {r["prompt_id"]: r.get("token_ids") or [] for r in (d.get("oracle") or {}).get("rows", [])}
    out = []
    for b in d["batches"]:
        for r in b["rows"]:
            ref = oracle.get(r["prompt_id"])
            got = r.get("token_ids") or []
            if not ref or ref == got:
                continue
            first = next((i for i, (x, y) in enumerate(zip(ref, got)) if x != y), min(len(ref), len(got)))
            out.append({
                "pass": b["repeat"], "prompt_id": r["prompt_id"],
                "concurrency": b["concurrency"],
                "first_diff_index": first,
                "oracle_len": len(ref), "got_len": len(got),
                "oracle_token": ref[first] if first < len(ref) else None,
                "got_token": got[first] if first < len(got) else None,
                "tail_identical_after_diff": ref[first + 1:] == got[first + 1:],
                **classify(ref, got),
            })
    return out


def main() -> int:
    argv = sys.argv[1:]
    lane = "ladder-mtp0"
    out_path = None
    roots: list[Path] = []
    i = 0
    while i < len(argv):
        if argv[i] == "--lane":
            lane = argv[i + 1]; i += 2
        elif argv[i] == "--json":
            out_path = Path(argv[i + 1]); i += 2
        else:
            roots.append(Path(argv[i])); i += 1
    if not roots:
        print(__doc__)
        return 2
    report = {}
    for root in roots:
        ev = analyse(root, lane)
        if ev is None:
            print(f"{root.name}: no {lane}")
            continue
        report[root.name] = ev
        print(f"=== {root.name}: {len(ev)} divergent request(s) ===")
        for e in ev:
            frac = e["first_diff_index"] / max(e["oracle_len"], 1)
            print(f"  pass{e['pass']} c{e['concurrency']:<4} {e['prompt_id'][:26]:28} first diff at token "
                  f"{e['first_diff_index']:>3}/{e['oracle_len']:<4} ({frac:>4.0%})  "
                  f"{e['oracle_token']} -> {e['got_token']}  "
                  f"{e['kind']:<20} sim={e['similarity']:.3f}")
    allev = [e for ev in report.values() for e in ev]
    if allev:
        pairs = collections.Counter((e["oracle_token"], e["got_token"]) for e in allev)
        prompts = collections.Counter(e["prompt_id"] for e in allev)
        kinds = collections.Counter(e["kind"] for e in allev)
        single = sum(1 for e in allev if e["tail_identical_after_diff"])
        shifts = sum(n for k, n in kinds.items() if k.startswith(("insertion", "deletion")))
        print(f"\nacross {len(allev)} divergences in {len(report)} arm(s):")
        print(f"  single-token substitutions (rest identical): {single}/{len(allev)}")
        print(f"  pure alignment shifts (insertion/deletion):  {shifts}/{len(allev)}")
        for k, n in kinds.most_common():
            print(f"    {k:<22} {n}")
        print(f"  distinct token pairs: {len(pairs)}; most common: {pairs.most_common(3)}")
        print(f"  distinct prompts: {len(prompts)}; most common: {prompts.most_common(3)}")
        report["_summary"] = {"divergences": len(allev), "single_token_substitutions": single,
                              "alignment_shifts": shifts,
                              "kind_counts": dict(kinds.most_common()),
                              "distinct_token_pairs": len(pairs),
                              "token_pair_counts": {f"{a}->{b}": n for (a, b), n in pairs.most_common()},
                              "prompt_counts": dict(prompts.most_common())}
    if out_path is not None:
        out_path.write_text(json.dumps(report, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
