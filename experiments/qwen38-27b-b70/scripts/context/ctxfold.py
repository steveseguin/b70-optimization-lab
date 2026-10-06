#!/usr/bin/env python3
"""ctxfold: fold every delivered item still in your context into /tmp/.live_ctx/STATE.txt with
YOUR /tmp/.live_ctx/FOLD.py, verify it, and remove the folded item turns from your context.

Installed into the sandbox by clm_improved.ClmImprovedAgent as /usr/local/bin/ctxfold.

FOLD.py (written once by the model, shown to it every turn with STATE.txt) must define
    fold(state: str, lines: list[str]) -> (new_state: str, tally: dict)
        state  = current STATE.txt text; lines = the item's non-empty lines (header removed)
        tally  = {first word of a line: number of lines of that kind applied}
    selftest() -> list[str]
        assert-based checks on a tiny MADE-UP example; returns the first words it covered.
Before writing anything ctxfold checks, per item: selftest() passes and covers every first word
present in the item, and fold()'s tally equals the item's line count per first word. On any
failure NOTHING is changed (STATE.txt and the context stay as they were) and it says why.
Usage: ctxfold [FINAL_KIND ...]   (items of these kinds are never folded; default GET QUERY)
       ctxfold --events [FINAL_KIND ...] <<EOF   (quoted events, arm B32iq: one line per change,
            `name | op | amount | "exact quote"`; the harness checks the quotes and does the arithmetic;
            the result depends only on the delivered text and STATE.txt, so batches could be read in parallel)
       ctxfold --drop [--force] [FINAL_KIND ...]   (reports read by the model: check that every
                       mentioned counter has a STATE.txt line, then remove the item turns)
"""
import collections
import os
import importlib.util
import re
import sys

sys.dont_write_bytecode = True
D = "/tmp/.live_ctx"
MIRROR, STATE, FOLD = D + "/LIVE_CTX_MAIN.txt", D + "/STATE.txt", D + "/FOLD.py"
HDR = re.compile(r"(\[\[CTX_TURN \d+ [^\]]*\]\])")
ITEM = re.compile(r"\s*ITEM (\d+)/(\d+) \((\w+)\)\n")
ITEMS = re.compile(r"(?m)^ITEM (\d+)/(\d+) \((\w+)\)\n")
ARCH = "/tmp/.live_ctx/archive"


def die(msg):
    print("ctxfold: REFUSED: " + msg + " (nothing was changed)")
    sys.exit(2)


def drop(final, force=False):
    """`ctxfold --drop`: for reports you read yourself. Checks that every counter name the delivered
    items mention has a line in STATE.txt (`name value`, or `name removed` for a counter removed on
    purpose); if not, it REFUSES and changes nothing. Otherwise it removes every delivered item turn
    from the context. STATE.txt is never touched and no value is checked: the reading is yours.
    `--force` drops even with missing names (e.g. names a report says are not in the ledger)."""
    s = open(MIRROR).read()
    try:
        state = open(STATE).read()
    except FileNotFoundError:
        state = ""
    held = set(re.findall(r"(?m)^\s*([a-z]+\d\d)\b", state))
    parts = HDR.split(s)
    out, done, named, texts = [parts[0]], [], set(), {}
    for i in range(1, len(parts), 2):
        h, b = parts[i], (parts[i + 1] if i + 1 < len(parts) else "")
        m = ITEM.match(b)
        if m and "role=tool" in h and m.group(3) not in final:
            body = b.split("\n\n(exit_code=")[0]
            heads = list(ITEMS.finditer(body))       # one turn can hold several items (`next && next`)
            for j, hm in enumerate(heads):
                end = heads[j + 1].start() if j + 1 < len(heads) else len(body)
                if hm.group(3) in final:
                    continue
                done.append(int(hm.group(1)))
                texts[int(hm.group(1))] = body[hm.end():end].strip()
            named |= set(re.findall(r"\b[a-z]+\d\d\b", b))
            continue
        out += [h, b]
    if not done:
        print("ctxfold: no delivered item in your context")
        return
    missing = sorted(named - held)
    if missing and not force:
        die(f"items {done} mention counters with no line in STATE.txt: {' '.join(missing)}. Add each "
            f"(`name value`, or `name removed` if it was removed) and run `ctxfold --drop` again")
    archived = 0
    if os.path.exists(ARCH + "/.on"):            # archive-on-drop (arm B32ira): verbatim, never overwritten
        for n, t in texts.items():
            f = f"{ARCH}/item-{n:03d}.txt"
            if not os.path.exists(f):
                with open(f, "w") as fh:
                    fh.write(t + "\n")
                os.chmod(f, 0o444)
                archived += 1
    open(MIRROR, "w").write("".join(out))
    print(f"ctxfold: removed items {done} from your context"
          + (f" (archived verbatim: {archived}; `recall` searches them)" if archived else "")
          + f"; STATE.txt has {len(held)} counter lines"
          + (f" (forced; missing: {' '.join(missing)})" if missing else ""))


UNITS = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve "
                                     "thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split())}
UNITS.update({w: 10 * i for i, w in enumerate("_ _ twenty thirty forty fifty sixty seventy eighty ninety".split())
              if i > 1})
EVENT = re.compile(r'^\s*([a-z]+\d\d)\s*\|\s*(set|add|sub|remove|reopen)\s*\|\s*(-?\d+)?\s*\|\s*"(.+)"\s*$')


def numbers(text):
    """Integers written in digits or in words ("minus forty-two", "three hundred and six")."""
    toks = re.findall(r"-?\d+|[a-z]+(?:-[a-z]+)*", text.lower())
    out, i = [], 0
    while i < len(toks):
        t = toks[i]
        if re.fullmatch(r"-?\d+", t):
            out.append(int(t))
            i += 1
            continue
        neg = t == "minus"
        j = i + 1 if neg else i
        total, cur, used = 0, 0, False
        while j < len(toks):
            w = toks[j]
            ps = w.split("-")
            if all(p in UNITS for p in ps):
                cur += sum(UNITS[p] for p in ps)
                used = True
            elif w == "hundred" and used:
                cur *= 100
            elif w == "thousand" and used:
                total += cur * 1000
                cur = 0
            elif w == "and" and used and j + 1 < len(toks) and toks[j + 1].split("-")[0] in UNITS:
                pass
            else:
                break
            j += 1
        if used:
            out.append(-(total + cur) if neg else total + cur)
            i = j
        else:
            i += 1
    return out


def refuse(reason, msg):
    print(f"ctxfold: REFUSED ({reason}): {msg}. Nothing was applied; fix it and send the whole list again.")
    sys.exit(2)


def events(final):
    """`ctxfold --events` (quoted events, arm B32iq): the model sends, on stdin, one line per change in the
    delivered item(s): `name | op | amount | "exact quote"`, op in set/add/sub/remove/reopen, amount in
    digits (empty for remove). The harness checks every line (format; the quote is verbatim in the
    delivered text, whitespace aside; the amount is written in the quote's paragraph, in digits or words;
    the counter is live for set/add/sub/remove and new or removed for reopen; afterwards every counter the
    text names has a STATE line), then does the arithmetic itself, writes STATE.txt, archives the items
    (when the archive is on) and removes them from the context. Any failure refuses the WHOLE list."""
    s = open(MIRROR).read()
    try:
        state_txt = open(STATE).read()
    except FileNotFoundError:
        state_txt = ""
    st = {}
    for ln in state_txt.splitlines():
        p = ln.split()
        if len(p) == 2 and re.fullmatch(r"[a-z]+\d\d", p[0]):
            st[p[0]] = None if p[1] == "removed" else int(p[1]) if re.fullmatch(r"-?\d+", p[1]) else None
    parts = HDR.split(s)
    out, done, named, texts = [parts[0]], [], set(), {}
    for i in range(1, len(parts), 2):
        h, b = parts[i], (parts[i + 1] if i + 1 < len(parts) else "")
        m = ITEM.match(b)
        if m and "role=tool" in h and m.group(3) not in final:
            body = b.split("\n\n(exit_code=")[0]
            heads = list(ITEMS.finditer(body))
            for j, hm in enumerate(heads):
                end = heads[j + 1].start() if j + 1 < len(heads) else len(body)
                if hm.group(3) in final:
                    continue
                done.append(int(hm.group(1)))
                texts[int(hm.group(1))] = body[hm.end():end].strip()
                named |= set(re.findall(r"\b[a-z]+\d\d\b", body[hm.end():end]))
            continue
        out += [h, b]
    if not done:
        print("ctxfold: no delivered item in your context")
        return
    batch = " ".join(" ".join(texts[n].split()) for n in sorted(texts))
    paras = [" ".join(p.split()) for n in sorted(texts) for p in texts[n].split("\n\n") if p.strip()]
    # (a bare EOF line: an indented here-document terminator that bash did not see as one)
    lines = [ln for ln in sys.stdin.read().splitlines() if ln.strip() and ln.strip().lower() != "none"
             and ln.strip() != "EOF"]
    new = dict(st)
    applied = collections.Counter()
    for k, ln in enumerate(lines, 1):
        m = EVENT.match(ln)
        if not m:
            refuse("format", f'line {k} {ln.strip()[:120]!r} is not `name | op | amount | "quote"` (op: set, add, '
                             f'sub, remove, reopen; amount in digits, empty for remove; quote in double quotes)')
        nm, op, amt, q = m.groups()
        qn = " ".join(q.split())
        if not qn or qn not in batch:
            refuse("bad quote", f"line {k}: the quote {q[:100]!r} is not verbatim in the delivered text")
        a = None
        if op != "remove":
            if amt is None:
                refuse("format", f"line {k}: {op} needs an amount in digits")
            a = int(amt)
            if op in ("add", "sub") and a <= 0:
                refuse("format", f"line {k}: the amount for {op} must be a positive number")
            nums = set()
            for p in paras:
                if qn in p:
                    nums.update(numbers(p))
            if a not in nums:
                refuse("amount not in text", f"line {k}: {a} is not written in the paragraph of the quote")
        elif amt is not None:
            refuse("format", f"line {k}: remove takes no amount")
        live = new.get(nm) is not None
        if op in ("set", "add", "sub", "remove") and not live:
            refuse("unknown counter", f"line {k}: {nm} is not a live counter in STATE.txt "
                                      f"(use reopen for a new or removed counter)")
        if op == "reopen" and live:
            refuse("unknown counter", f"line {k}: {nm} is already live; use set")
        if op in ("set", "reopen"):
            new[nm] = a
        elif op == "add":
            new[nm] = new[nm] + a
        elif op == "sub":
            new[nm] = new[nm] - a
        else:
            new[nm] = None
        applied[op] += 1
    missing = sorted(n for n in named if n not in new)
    if missing:
        refuse("unknown counter", f"the delivered text names counters that have no STATE line after these events: "
                                  f"{' '.join(missing)} (add a reopen event for each one that was opened)")
    with open(STATE, "w") as fh:
        fh.write("".join(f"{n} {'removed' if v is None else v}\n" for n, v in new.items()))
    archived = 0
    if os.path.exists(ARCH + "/.on"):
        for n, t in texts.items():
            f = f"{ARCH}/item-{n:03d}.txt"
            if not os.path.exists(f):
                with open(f, "w") as fh:
                    fh.write(t + "\n")
                os.chmod(f, 0o444)
                archived += 1
    open(MIRROR, "w").write("".join(out))
    print(f"ctxfold: applied {sum(applied.values())} events "
          f"({', '.join(f'{k} {v}' for k, v in sorted(applied.items())) or 'none'}) from items {done}"
          + (f"; archived verbatim: {archived}" if archived else "")
          + f"; STATE.txt now has {len(new)} counter lines")


def main():
    if sys.argv[1:2] == ["--events"]:
        return events(set(sys.argv[2:] or ["GET", "QUERY"]))
    if sys.argv[1:2] == ["--drop"]:
        rest = [a for a in sys.argv[2:] if a != "--force"]
        return drop(set(rest or ["GET", "QUERY"]), force="--force" in sys.argv[2:])
    final = set(sys.argv[1:] or ["GET", "QUERY"])
    try:
        spec = importlib.util.spec_from_file_location("fold_mod", FOLD)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    except FileNotFoundError:
        die(f"{FOLD} does not exist; write it once: fold(state, lines) -> (new_state, tally) and selftest()")
    except Exception as e:
        die(f"FOLD.py failed to load: {type(e).__name__}: {e}")
    for fn in ("fold", "selftest"):
        if not callable(getattr(mod, fn, None)):
            die(f"FOLD.py must define {fn}()")
    try:
        covered = set(mod.selftest() or [])
    except Exception as e:
        die(f"selftest() failed: {type(e).__name__}: {e}")
    s = open(MIRROR).read()
    try:
        state = open(STATE).read()
    except FileNotFoundError:
        state = ""
    parts = HDR.split(s)
    out, done, total = [parts[0]], [], 0
    for i in range(1, len(parts), 2):
        h, b = parts[i], (parts[i + 1] if i + 1 < len(parts) else "")
        m = ITEM.match(b)
        if m and "role=tool" in h and m.group(3) not in final:
            body = b[m.end():].split("\n\n(exit_code=")[0]
            lines = [ln for ln in body.splitlines() if ln.strip()]
            want = collections.Counter(ln.split()[0] for ln in lines)
            missing = sorted(set(want) - covered)
            if missing:
                die(f"item {m.group(1)} has lines starting with {missing}, which selftest() does not cover")
            try:
                new, tally = mod.fold(state, lines)
            except Exception as e:
                die(f"fold() raised on item {m.group(1)}: {type(e).__name__}: {e}")
            if not isinstance(new, str):
                die("fold() must return (new_state_text, tally_dict)")
            try:
                got = {k: int(v) for k, v in dict(tally).items() if int(v)}
            except Exception:
                die("fold()'s tally must be a dict {first_word: count}")
            if got != dict(want):
                die(f"item {m.group(1)} has {dict(want)} lines by first word, fold() reported {got}")
            state, total = new, total + len(lines)
            done.append(int(m.group(1)))
            continue  # the folded item turn is removed from the context
        out += [h, b]
    if not done:
        print("ctxfold: no unfolded item in your context")
        return
    open(STATE, "w").write(state if state.endswith("\n") else state + "\n")
    open(MIRROR, "w").write("".join(out))
    print(f"ctxfold: folded items {done} ({total} lines); STATE.txt now {len(state.splitlines())} lines")


if __name__ == "__main__":
    main()
