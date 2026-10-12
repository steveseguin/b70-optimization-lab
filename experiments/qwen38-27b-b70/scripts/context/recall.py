#!/usr/bin/env python3
"""recall: search the read-only archive of items that were removed from your context.

Installed as /usr/local/bin/recall by clm_improved.ClmImprovedAgent with archive=true (arm B32ira).
Every item that `ctxfold --drop` removes from the context is first written verbatim to
/tmp/.live_ctx/archive/item-NNN.txt; nothing is ever deleted, only moved out of view. The output of
`recall` lands in your context like any tool output (it counts against your budget), so keep it small.

  recall PATTERN [--before N] [--after N] [--max-lines N]
                                     sentences matching PATTERN (case-insensitive regex; plain text
                                     works too), each with the sentence after it, in item order, as
                                     "item N: <sentence> <next sentence>"; default 40 lines.
                                     --before N / --after N: only items up to N / from N on (inclusive).
                                     When more match than fit, the ones nearest to --before (or to --after,
                                     or else the newest) are shown, and the first line says how many were
                                     left out.
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
    opt = {}
    for name in ("--max-lines", "--before", "--after"):
        if name in args:
            i = args.index(name)
            try:
                opt[name] = int(args[i + 1])
            except (IndexError, ValueError):
                print(f"recall: {name} needs a whole number"); return
            del args[i:i + 2]
    maxl, before, after = opt.get("--max-lines"), opt.get("--before"), opt.get("--after")
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
        if (before is not None and n > before) or (after is not None and n < after):
            continue
        sents = re.split(r"(?<=[.!?])\s+", " ".join(txt.split()))
        for i, s in enumerate(sents):
            if rx.search(s):
                # with the sentence after it: text often names a thing in one sentence and says what happened to it
                # in the next ("Next on the list was abcd12. It was opened at 591.")
                # (not when the next sentence matches too: it gets a line of its own, and printing it twice would
                # read as two changes)
                more = (" " + sents[i + 1][:200]) if i + 1 < len(sents) and not rx.search(sents[i + 1]) else ""
                hits.append(f"item {n}: {s[:300]}{more}")
    if not hits:
        print(f"recall: no archived sentence matches {pat!r}" + (f" up to item {before}" if before is not None else "")
              + (f" from item {after} on" if after is not None else ""))
        return
    if len(hits) > lim:
        # The count comes first and the matches nearest to where the search is anchored are shown. (The first 40 in
        # item order, with the note last, were read as "that is all": at 1M the model then fetched whole items to
        # find the later changes, the window filled, and the question it was answering was cut out of view.)
        if after is not None and before is None:
            print(f"[{len(hits)} matches; showing the first {lim} from item {after} on; {len(hits) - lim} later ones "
                  f"are not shown: narrow with --before N]")
            hits = hits[:lim]
        else:
            where = f"the {lim} nearest before item {before}" if before is not None else f"the newest {lim}"
            print(f"[{len(hits)} matches; showing {where}; {len(hits) - lim} earlier ones are not shown: narrow with "
                  f"--after N" + ("" if before is not None else " or --before N") + "]")
            hits = hits[-lim:]
    print("\n".join(hits))


if __name__ == "__main__":
    main()
