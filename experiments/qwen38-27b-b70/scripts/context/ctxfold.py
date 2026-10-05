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
"""
import collections
import importlib.util
import re
import sys

sys.dont_write_bytecode = True
D = "/tmp/.live_ctx"
MIRROR, STATE, FOLD = D + "/LIVE_CTX_MAIN.txt", D + "/STATE.txt", D + "/FOLD.py"
HDR = re.compile(r"(\[\[CTX_TURN \d+ [^\]]*\]\])")
ITEM = re.compile(r"\s*ITEM (\d+)/(\d+) \((\w+)\)\n")


def die(msg):
    print("ctxfold: REFUSED: " + msg + " (nothing was changed)")
    sys.exit(2)


def main():
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
