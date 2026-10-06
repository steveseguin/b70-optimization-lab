#!/usr/bin/env python3
"""recall: search the read-only archive of items that were removed from your context.

Installed as /usr/local/bin/recall by clm_improved.ClmImprovedAgent with archive=true (arm B32ira).
Every item that `ctxfold --drop` removes from the context is first written verbatim to
/tmp/.live_ctx/archive/item-NNN.txt; nothing is ever deleted, only moved out of view. The output of
`recall` lands in your context like any tool output (it counts against your budget), so keep it small.

  recall PATTERN [--max-lines N]     sentences matching PATTERN (case-insensitive regex; plain text
                                     works too), in item order, as "item N: <sentence>"; default 40 lines
  recall --item N [--max-lines N]    the text of item N, one paragraph per line; default 80 lines
"""
import os
import re
import sys

D = "/tmp/.live_ctx/archive"


def items():
    out = []
    for f in sorted(os.listdir(D)) if os.path.isdir(D) else []:
        m = re.fullmatch(r"item-(\d+)\.txt", f)
        if m:
            out.append((int(m.group(1)), open(os.path.join(D, f), errors="replace").read()))
    return out


def main():
    args = sys.argv[1:]
    maxl = None
    if "--max-lines" in args:
        i = args.index("--max-lines")
        maxl = int(args[i + 1]); del args[i:i + 2]
    if not args:
        print(__doc__.strip().split("\n\n")[-1]); return
    arch = items()
    if args[0] == "--item":
        n = int(args[1])
        txt = dict(arch).get(n)
        if txt is None:
            print(f"recall: item {n} is not in the archive (archived: {', '.join(str(k) for k, _ in arch[-10:]) or 'none'})")
            return
        paras = [p.strip() for p in txt.split("\n\n") if p.strip()]
        lim = maxl or 80
        print(f"ITEM {n} (archived)")
        print("\n".join(paras[:lim]))
        if len(paras) > lim:
            print(f"[... {len(paras) - lim} more paragraphs; use --max-lines]")
        return
    pat = " ".join(args)
    try:
        rx = re.compile(pat, re.I)
    except re.error:
        rx = re.compile(re.escape(pat), re.I)
    lim = maxl or 40
    hits = []
    for n, txt in arch:
        for s in re.split(r"(?<=[.!?])\s+", " ".join(txt.split())):
            if rx.search(s):
                hits.append(f"item {n}: {s[:300]}")
    print("\n".join(hits[:lim]) if hits else f"recall: no archived sentence matches {pat!r}")
    if len(hits) > lim:
        print(f"[{len(hits)} matches; showing the first {lim}; narrow the pattern or use --max-lines]")


if __name__ == "__main__":
    main()
