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
import difflib
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
# quoted-events line; forgiving about the common slips (quoted-fix, 2026-10-06): smart or single quotes,
# a missing closing quote, an amount in words or with a sign, op synonyms
EVENT = re.compile(r'^\s*([a-z]+\d\d)\s*\|\s*([a-z]+)\s*\|\s*([^|]*?)\s*\|\s*(.*?)\s*$')
OPS = {"set": "set", "add": "add", "sub": "sub", "remove": "remove", "reopen": "reopen",
       "correct": "set", "correction": "set", "plus": "add", "increase": "add", "gain": "add",
       "subtract": "sub", "minus": "sub", "decrease": "sub", "lose": "sub",
       "del": "remove", "delete": "remove", "removed": "remove", "strike": "remove",
       "open": "reopen", "opened": "reopen", "new": "reopen"}
QUOTES = "\"'“”‘’`"


def numbers(text):
    """Integers written in digits or in words ("minus forty-two", "three hundred and six"). A number in
    words ends at punctuation and where the next word cannot continue it (quoted, 2026-10-06: "went down
    by eighty-three. Two of the packers..." was read as 85, which refused correct lists 37 times)."""
    text = re.sub(r"\b[a-z]+\d\d\b", " ", text.lower())   # counter names are not numbers
    toks = re.findall(r"-?\d+|[a-z]+(?:-[a-z]+)*|[.,;:!?]", text)
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
                val = sum(UNITS[p] for p in ps)
                if used and cur % 100 and (val >= 10 or cur % 10):
                    break                      # "eighty-three two": a new number
                cur += val
                used = True
            elif w == "hundred" and used and cur < 100:
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
    msg = msg.rstrip(".")
    print(f"ctxfold: REFUSED ({reason}): {msg}{'' if msg.endswith('?') else '.'} Nothing was applied; fix that line "
          f"and send the whole list again.")
    sys.exit(2)


def _sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def _closest(q, sents, nm):
    """The delivered sentence(s) the quote most likely meant: those naming the counter, else the nearest."""
    by_name = [s for s in sents if re.search(r"\b" + re.escape(nm) + r"\b", s)]
    if by_name:
        return by_name[:3]
    return difflib.get_close_matches(q, sents, n=2, cutoff=0.4)


def events(final):
    """`ctxfold --events` (quoted events, arm B32iq): the model sends, on stdin, one line per change in the
    delivered item(s): `name | op | amount | "exact quote"`, op in set/add/sub/remove/reopen, amount in
    digits (empty for remove). The harness checks every line (format; the counter name occurs in the
    delivered text; the quote is verbatim in it, whitespace aside; the amount is written in the quote's
    sentence or paragraph, in digits or words; the counter is live for add/sub/remove and new or removed
    for reopen; afterwards every counter the text names has a STATE line), then does the arithmetic
    itself, writes STATE.txt, archives the items (when the archive is on) and removes them from the
    context. Any failure refuses the WHOLE list, with the delivered sentence that the line should quote.
    The result depends only on the delivered text and STATE.txt (seam for reading batches in parallel)."""
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
    sents = _sentences(batch)
    raw = sys.stdin.read().splitlines()
    # skipped: blank lines, `none`, comments, a bare EOF (an indented here-document terminator)
    lines = [ln for ln in raw if ln.strip() and ln.strip().lower() != "none" and ln.strip() != "EOF"
             and not ln.lstrip().startswith("#") and not re.match(r"\s*none\s*\|", ln, re.I)]
    if not lines and not any(ln.strip().lower() == "none" or re.match(r"\s*none\s*\|", ln, re.I) for ln in raw):
        refuse("format", "the list is empty; send one line `none` if the item changes nothing")
    new = dict(st)
    applied = collections.Counter()
    for k, ln in enumerate(lines, 1):
        m = EVENT.match(ln)
        if not m:
            refuse("format", f'line {k} {ln.strip()[:120]!r} is not `name | op | amount | "quote"`; for example '
                             f'`abcd12 | sub | 83 | "abcd12 went down by eighty-three."`')
        nm, op_raw, amt_raw, q = m.groups()
        op = OPS.get(op_raw.lower())
        if not op:
            refuse("format", f"line {k}: op {op_raw!r} is not one of set, add, sub, remove, reopen")
        q = q.strip()
        if q[:1] in QUOTES:
            q = q[1:]
        if q[-1:] in QUOTES:
            q = q[:-1]
        qn = " ".join(q.split())
        if nm not in named:
            near = difflib.get_close_matches(nm, sorted(named | set(st)), n=2, cutoff=0.6)
            refuse("unknown counter", f"line {k}: {nm} does not occur in the delivered text"
                                      + (f"; did you mean {' or '.join(near)}?" if near else ""))
        if qn and qn not in batch and qn.rstrip(".") in batch:
            qn = qn.rstrip(".")
        if not qn or qn not in batch:
            cl = _closest(qn, sents, nm)
            refuse("bad quote", f"line {k}: the quote {q[:100]!r} is not verbatim in the delivered text"
                                + ("; the delivered sentence(s) naming " + nm + ": "
                                   + " | ".join(f'"{c}"' for c in cl) if cl else ""))
        a = None
        if op != "remove":
            amt = amt_raw.strip().replace(",", "")
            if re.fullmatch(r"[+-]?\d+", amt):
                a = int(amt)
            else:
                vals = numbers(amt)
                if len(vals) != 1:
                    refuse("format", f"line {k}: {op} needs an amount in digits, not {amt_raw!r}")
                a = vals[0]
            if op in ("add", "sub") and a < 0:
                a = -a
            if op in ("add", "sub") and a == 0:
                refuse("format", f"line {k}: the amount for {op} must not be 0")
            # the amount must be written in the quoted sentence(s) or in a sentence of the same paragraph
            # that names the counter (a plan's amount precedes its outcome; a correction names it again);
            # a number elsewhere in the paragraph does not count (B32iq s1 got "2" past the old check from
            # "Two of the packers ..." after the word-number bug refused its correct list)
            nums = {x for sn in sents if qn in sn or sn in qn for x in numbers(sn)}
            for p in paras:
                if qn in p:
                    for sn in _sentences(p):
                        if qn in sn or sn in qn or re.search(r"\b" + re.escape(nm) + r"\b", sn):
                            nums.update(numbers(sn))
            if a not in nums:
                hint = "; did you drop or add a minus sign?" if -a in nums else ""
                in_sent = sorted({x for sn in sents if qn in sn or sn in qn for x in numbers(sn)})
                refuse("amount not in text", f"line {k}: {a} is not written in the quote or in a sentence of its "
                                             f"paragraph that names {nm}"
                                             + (f" (the quoted sentence holds {', '.join(map(str, in_sent))})"
                                                if in_sent else "") + hint)
        live = new.get(nm) is not None
        if op == "set" and not live:
            op = "reopen"                          # a value given outright for a new or removed counter
        if op in ("add", "sub", "remove") and not live:
            refuse("unknown counter", f"line {k}: {nm} is {'removed' if nm in new else 'not in STATE.txt'}, "
                                      f"so it cannot be {op}{'ed' if op == 'add' else 'bed' if op == 'sub' else 'd'}; "
                                      f"if the report opens it again, use reopen with its value")
        if op == "reopen" and live:
            refuse("unknown counter", f"line {k}: {nm} is already live ({new[nm]}); use set for a value given "
                                      f"outright, or add/sub for a change")
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
        where = "; ".join(f'{n}: "{(_closest("", sents, n) or ["?"])[0]}"' for n in missing[:4])
        refuse("unknown counter", f"the delivered text names counters that have no STATE line after these events: "
                                  f"{' '.join(missing)} (add a reopen event for each one that was opened: {where})")
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
