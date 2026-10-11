#!/usr/bin/env python3
"""recall (v2): search the read-only archive of items that were removed from your context.

Same archive as recall.py (/tmp/.live_ctx/archive/item-NNN.txt, written verbatim by `ctxfold --drop`). v1 prints the
first 40 matches in item order; on a long history that is the oldest 40, and the only way to reach newer ones is
to print everything. v2 adds a window over item numbers and "the last K", so the cost of a lookup stays the same
however long the history is. Without the new options it behaves as v1.

  recall PATTERN [--before N] [--after N] [--last K | --first K]
        sentences matching PATTERN (case-insensitive regex; plain text works too) as "item N: <sentence>", in item
        order. --before N keeps items <= N, --after N keeps items >= N. --last K shows the K newest of them,
        --first K the K oldest (default: the first 40). --max-lines K is the same as --first K.
  recall --where PATTERN [--before N] [--after N]
        only the item numbers that hold a match (as ranges), with the number of matching sentences
  recall --item N [--max-lines K]
        the text of item N, one paragraph per line (default 80 lines)

Typical: the value a counter held at the end of item 412 ->  recall NAME --before 412 --last 6
"""
import os
import re
import sys

D = os.environ.get("RECALL_ARCHIVE", "/tmp/.live_ctx/archive")
USAGE = __doc__.strip().split("\n\n", 2)[2]


def items(lo=None, hi=None):
    out = []
    for f in sorted(os.listdir(D)) if os.path.isdir(D) else []:
        m = re.fullmatch(r"item-(\d+)\.txt", f)
        if m and (lo is None or int(m.group(1)) >= lo) and (hi is None or int(m.group(1)) <= hi):
            out.append((int(m.group(1)), open(os.path.join(D, f), errors="replace").read()))
    return sorted(out)


def take(args, flag, cast=int):
    """Remove `flag VALUE` from args and return VALUE (None if absent)."""
    if flag not in args:
        return None
    i = args.index(flag)
    try:
        value = cast(args[i + 1])
    except (IndexError, ValueError):
        raise SystemExit(f"recall: {flag} needs a number")
    del args[i:i + 2]
    return value


def ranges(numbers):
    out, start, prev = [], None, None
    for n in numbers:
        if start is None:
            start = prev = n
        elif n == prev + 1:
            prev = n
        else:
            out.append((start, prev)); start = prev = n
    if start is not None:
        out.append((start, prev))
    return ", ".join(str(a) if a == b else f"{a}-{b}" for a, b in out)


def search(pattern, lo=None, hi=None):
    try:
        rx = re.compile(pattern, re.I)
    except re.error:
        rx = re.compile(re.escape(pattern), re.I)
    hits = []
    for n, txt in items(lo, hi):
        for s in re.split(r"(?<=[.!?])\s+", " ".join(txt.split())):
            if rx.search(s):
                hits.append((n, s[:300]))
    return hits


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    before, after = take(args, "--before"), take(args, "--after")
    last, first, maxl = take(args, "--last"), take(args, "--first"), take(args, "--max-lines")
    where = "--where" in args
    if where:
        args.remove("--where")
    if not args:
        print(USAGE); return
    if args[0] == "--item":
        try:
            n = int(args[1])
        except (IndexError, ValueError):
            print("recall: --item needs an item number"); return
        arch = dict(items())
        txt = arch.get(n)
        if txt is None:
            print(f"recall: item {n} is not in the archive (archived: {ranges(sorted(arch)) or 'none'})")
            return
        paras = [p.strip() for p in txt.split("\n\n") if p.strip()]
        lim = maxl or 80
        print(f"ITEM {n} (archived)")
        print("\n".join(paras[:lim]))
        if len(paras) > lim:
            print(f"[... {len(paras) - lim} more paragraphs; use --max-lines]")
        return
    pat = " ".join(args)
    hits = search(pat, after, before)
    span = (f" in items {after or 1}-{before}" if before else f" in items {after} onward" if after else "")
    if not hits:
        print(f"recall: no archived sentence matches {pat!r}{span}")
        return
    if where:
        nums = sorted({n for n, _ in hits})
        print(f"{len(hits)} matching sentences in {len(nums)} items{span}: {ranges(nums)}")
        return
    if last:
        shown, which = hits[-last:], "last"
    else:
        shown, which = hits[:first or maxl or 40], "first"
    print("\n".join(f"item {n}: {s}" for n, s in shown))
    if len(shown) < len(hits):
        print(f"[{len(hits)} matches{span}, items {hits[0][0]}-{hits[-1][0]}; showing the {which} {len(shown)}. "
              f"Move the window with --before N / --after N, or take the newest with --last K]")


if __name__ == "__main__":
    main()
