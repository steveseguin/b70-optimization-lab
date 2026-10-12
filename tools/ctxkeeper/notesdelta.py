"""The pure part of changes-only notes: parsing a NEW RULES / CHANGES / OPEN reply, applying it to the NOTES, and the
checks that keep it honest. Standard library only. Used by ctxkeeper.py (--notes-mode inplace).

Everything between the two marker lines below is copied, unchanged, from the test-harness keeper
(experiments/qwen38-27b-b70/scripts/context/clm_keeper.py), where it was measured (arm N32u: 313 of 313 answers
over two 240K streams and a 1M stream; lab note 2026-10-10-context-16k-baseline.md, campaigns 10 and 10b), and
test_notesdelta.py fails if the two copies drift apart. The comments inside it name runs of that harness. The three
functions after the second marker are the harness's, rewritten to take plain texts instead of harness messages.

Regenerate after a change to the harness copy: `python3 tools/ctxkeeper/sync_notesdelta.py`.
"""
from __future__ import annotations

import re
from typing import Any

# ---- copied from clm_keeper.py (do not edit here) ----
DELTA_RETRY = ("Your reply did not use the layout. Reply with the sections only: first line NEW RULES, then the new "
               "rules or (none), then a line CHANGES, then one `name: value` line per change or (none), then a line OPEN.")


DELTA_HEADS = ("NEW RULES", "CHANGES", "OPEN")


RESULT = re.compile(r"\s*(-?\d+)\.?(?:\s*\(.*\))?\s*$")        # the last part of working: `= 169`, `= 169 (item 4)`


_UNITS = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
                                     "fifteen sixteen seventeen eighteen nineteen".split())}


_TENS = {w: 10 * (i + 2) for i, w in enumerate("twenty thirty forty fifty sixty seventy eighty ninety".split())}


def numbers_in(text: str, signed: bool = False) -> set[int]:
    """Every whole number the text states, in digits or in English words ("four hundred and two", "forty-nine").
    Default: each with both signs (for "lost forty-nine" the sign is in the verb). With `signed`, as stated: negative
    only after "minus" / "negative" or a leading "-" ("at -106", "minus ninety-seven"); that is what a value SET by
    the text has to match. Digits inside a name (`abcd62`) and the numbers of an `ITEM 132/147 (UPDATE)` heading
    are not numbers the text states, and number words do not run on across punctuation ("one hundred. Two birds")."""
    text = re.sub(r"ITEM \d+/\d+ \(\w+\)", " ", text).replace("\u2212", "-")
    out: set[int] = set()
    total = part = 0
    open_ = neg = False

    def emit(n: int, minus: bool) -> None:
        out.update((-n,) if signed and minus else (n,) if signed else (n, -n))

    def close() -> None:
        nonlocal total, part, open_, neg
        if open_:
            emit(total + part, neg)
        total, part, open_, neg = 0, 0, False, False

    minus_next = False
    for tok in re.findall(r"[a-z_]+\d\w*|[a-z]+|(?<![\w)])-(?=\d)|\d[\d,]*|[.!?;:,]", text.lower()):
        if tok in ("minus", "negative", "-"):
            close()
            minus_next = True
            continue
        if tok[0].isalpha() and tok[-1].isdigit() or "_" in tok:
            close()                                  # a name such as abcd62
        elif tok[0].isdigit():
            close()
            emit(int(tok.replace(",", "") or 0), minus_next)
        elif tok in _UNITS or tok in _TENS:
            if not open_:
                neg = minus_next
            part, open_ = part + (_UNITS[tok] if tok in _UNITS else _TENS[tok]), True
        elif tok == "hundred" and open_:
            part *= 100
        elif tok == "thousand" and open_:
            total, part = total + part * 1000, 0
        elif tok == "and" and open_:
            continue
        else:
            close()
        minus_next = False
    close()
    return out


def _plain(line: str) -> str:
    return line.strip().lstrip("-*\u2022 ").strip()


def _is_none(line: str) -> bool:
    return _plain(line).lower().strip("().") in ("", "none", "nothing", "empty")


def delta_section_of(line: str) -> str:
    """NEW RULES, CHANGES or OPEN if the line is that heading, else ''."""
    head = " ".join(line.strip().strip("#*_ ").rstrip(":").strip("*_ ").upper().split())
    return head if head in DELTA_HEADS else ""


def fact_of(line: str) -> tuple[str, str]:
    """(name, value) of a STATE or CHANGES line: `name: value`, `name = value`, or `name rest` when it has neither.
    The name is lower-cased; bullets and backticks are dropped."""
    s = _plain(line)
    m = re.match(r"`?([^:=`]+?)`?\s*[:=]\s*(.*)$", s)
    if m and m.group(1).strip() and len(m.group(1).split()) <= 6:
        key, val = m.group(1), m.group(2)
    else:
        key, _, val = s.partition(" ")
    return key.strip().strip("`*_ ").lower(), val.strip().strip("`")


def number_of(value: str) -> int | None:
    """The whole number a STATE value holds now: the last number in it once bracketed remarks are set aside
    (`75 (60, gained 15 in item 606)` -> 75, `-107 -> -31` -> -31, `opened at 402` -> 402,
    `-58 - 35 = -93, then set to 82 (item 48)` -> 82); None for `removed ...` and for a value without a whole number.
    (A model that thinks writes such lines; reading the first number instead sent correct replies to the fallback.)"""
    v = re.sub(r"\([^()]*\)", " ", value).replace("\u2212", "-").strip()
    v = re.split(r"\u2192|->|=>", v)[-1].strip()         # `286 -> removed`: what it is now comes last
    if re.match(r"(removed|closed|struck|deleted|gone)\b", v.lower()):
        return None
    nums = re.findall(r"(?<![\w.])-?\d[\d,]*(?![\d.]*\d)", v)
    return int(nums[-1].replace(",", "")) if nums else None


def _calc(expr: str) -> float | None:
    """The value of plain arithmetic (numbers, + - * /, brackets); None for anything else."""
    import ast
    def ev(n: Any) -> float:
        if isinstance(n, ast.Constant) and type(n.value) in (int, float):
            return n.value
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.USub, ast.UAdd)):
            return -ev(n.operand) if isinstance(n.op, ast.USub) else ev(n.operand)
        if isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            x, y = ev(n.left), ev(n.right)
            return {ast.Add: x + y, ast.Sub: x - y, ast.Mult: x * y}.get(type(n.op)) if not isinstance(n.op, ast.Div) else x / y
        raise ValueError(n)
    try:
        return ev(ast.parse(expr.strip(), mode="eval").body)
    except (ValueError, SyntaxError, ZeroDivisionError, RecursionError):
        return None


def work_out(value: str) -> tuple[int | None, int | None, int] | None:
    """(start, result, stated result) of a value written as working that ends in `= number`, such as
    `120 + 49 - 3 = 166`, `40 x 2 = 80` or `90 - 90/3 = 60`; None when the value is not working. `start` is the
    number the working begins with (None if it begins with something else). `result` is computed when the working
    is plain arithmetic; it is None when plain arithmetic has no whole-number value (`7 / 2`, `7 / 0`): such a line
    cannot be right. Working in words (`119 + what efgh34 holds (402) = 521`) cannot be checked: `result` is then
    the stated result."""
    v = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", value.strip())
    v = v.replace("\u2212", "-").replace("\u00d7", "*").replace("\u00f7", "/")
    if re.fullmatch(r"(-?\d+)\s*(?:\u2192|->|=>)\s*(-?\d+)\.?", v):
        return None                                  # `-107 -> -31` is an assignment of -31, checked as one; not working
    v = re.sub(r"(?<=[\d)])\s*x\s*(?=[\d(-])", " * ", v)
    parts = v.split("=")
    m = RESULT.fullmatch(parts[-1]) if len(parts) > 1 else None
    expr = parts[-2].strip() if m else ""
    if not m or not re.match(r"\(?\s*-?\d", expr) or not re.search(r"[\d)]\s*[-+*/]\s*\S", expr):
        return None
    stated = int(m.group(1))
    first = re.match(r"\(?\s*(-?\d+)(?![\d.])", parts[0].strip())
    total: int | None = stated
    if re.fullmatch(r"[\d\s+\-*/().]+", expr):
        val = _calc(expr)
        total = int(val) if val is not None and float(val).is_integer() else None
    return (int(first.group(1)) if first else None), total, stated


def parse_delta(reply: str, need_changes: bool = True) -> dict | None:
    """{'rules': [...], 'changes': [(name, value), ...], 'open': [...]} from a reply in the NEW RULES / CHANGES / OPEN
    layout (text before NEW RULES is dropped); None if the layout is missing. 'open' is None when the reply has no
    OPEN heading: the old OPEN section then stays."""
    lines = reply.splitlines()
    at = next((i for i, ln in enumerate(lines) if delta_section_of(ln) == "NEW RULES"), None)
    if at is None:
        return None
    sec, seen = "NEW RULES", {"NEW RULES"}
    out: dict[str, list[str]] = {h: [] for h in DELTA_HEADS}
    for ln in lines[at + 1:]:
        head = delta_section_of(ln)
        if head:
            sec = head
            seen.add(head)
        elif ln.strip():
            out[sec].append(ln.strip())
    if need_changes and "CHANGES" not in seen:
        return None
    return {"rules": [_plain(ln) for ln in out["NEW RULES"] if not _is_none(ln)],
            "changes": [fact_of(ln) for ln in out["CHANGES"] if not _is_none(ln) and fact_of(ln)[0]],
            "open": [ln for ln in out["OPEN"] if not _is_none(ln)] if "OPEN" in seen else None}


REMARK = re.compile(r"\([^()]*[A-Za-z][^()]*\)")      # `(item 451)`, `(struck off the books)`; not `(5)` in working


# the words a part may use to say "the value is now N"; anything else with a number in it is not read as a set
SET_WORDS = frozenset("opened reopened re set reset recorded now stands starts started start at to as is was back again new page value".split())


def steps_in(value: str) -> int:
    """How many changes one CHANGES line writes. A model packs several onto a line in its own ways:
    `578 + 62 = 640, then set to 174`, `opened at 117, set to -190, +46 = -144`, `539 - 31 = 508 - 48 = 460, then
    removed`, `468 - 19 = 449, set to 473 (item 449); +31 = 504 (item 450)`, `112 + 16 + 45 = 173`. Each part between
    commas, semicolons and "then" that holds a number or a removal is a change; a part with working counts once per
    operation. Remarks in parentheses are not read. (Counting a line as one change made the count check ask again on
    a third of the notes calls at 1M, harness and proxy alike; 14 of 25 such questions in the proxy run were this.)"""
    n = 0
    for part in PARTS.split(REMARK.sub(" ", value)):
        part = part.strip()
        if not (re.search(r"\d", part) or re.match(r"(removed|closed|struck|deleted|gone)\b", part.lower())):
            continue
        ops = len(re.findall(r"(?<=[\d)])\s*[-+*/x\u00d7\u2212]\s*(?=[\d(-])", part))
        # `+5 = 132`: the line goes on from the value before (one change); `-10 + 5 = -5` starts from minus ten
        lead = 1 if "=" in part and re.fullmatch(r"[-+\u2212]\s*\d+", part.split("=")[0].strip()) else 0
        n += max(ops + lead, 1)
    return max(n, 1)


def amounts_ok(working: str, amounts: set[int] | None) -> bool:
    """Every number in this stretch of working (what is added to or taken from the value it starts from) is one the
    turns state for the thing, whatever its sign there; the caller adds every value a thing of STATE holds or held
    while the reply was applied ("went up by as much as bamo35 held at that moment"), and times or divided by a
    small whole number passes ("was doubled"). Working that is right as arithmetic can still be made up:
    X32m at 1M read "recorded katu85 at five hundred and twenty-three" as 623 and wrote `650 - 27 = 623`, which
    starts from the value held and adds up; 27 is nowhere in the turns."""
    if amounts is None:
        return True
    have = {abs(a) for a in amounts}
    text = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", working).replace("\u2212", "-").replace("\u00d7", "*").replace("\u00f7", "/")
    for op, k in re.findall(r"([-+*/x]?)\s*\(?\s*-?(\d+)", text):
        # "was doubled", "lost a third": times or divided by a small whole number is said in words, not in figures
        if int(k) not in have and not (op in ("*", "/", "x") and 2 <= int(k) <= 10):
            return False
    return True


PARTS = re.compile(r",(?!\d{3}\b)|;|\bthen\b")       # what separates the changes packed onto one line


def chain_of(value: str, held: int | None, stated: set[int], amounts: set[int] | None = None) -> tuple[int | None, list[int], int] | None:
    """A CHANGES line that packs several changes, followed part by part from the value the NOTES hold:
    (the value at the end, or None after a removal; the sets it took from the turns; how many of those open a part
    of working instead of standing as a part of their own). None when a part cannot be followed, and the line is
    then judged as before. A part is a set (`opened at 117`, `set to -190`: one number, which the turns must state),
    working from the value so far (`292 - 67 = 225`, also `539 - 31 = 508 - 48 = 460`), working that goes on from
    it (`+46 = -144`), working from a value the turns state (a set and a change in one), or a removal. Remarks in
    parentheses are set aside; brackets inside working are part of the sum.
    Every line in the 1M proxy run that the working check questioned and then accepted was such a line.
    With `amounts` (see amounts_ok) every amount added or taken in the working must be one of them."""
    v = REMARK.sub(" ", value)
    v = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", v).replace("\u2212", "-").replace("\u00d7", "*").replace("\u00f7", "/")
    v = re.sub(r"(?<=[\d)])\s*x\s*(?=[\d(-])", " * ", v)
    cur, sets, opening, parts = held, [], 0, 0
    for part in PARTS.split(v):
        part = part.strip().rstrip(".").strip()
        if not part:
            continue
        parts += 1
        if re.match(r"(removed|closed|struck|deleted|gone)\b", part.lower()):
            cur = None
            continue
        if "=" not in part:
            nums = re.findall(r"(?<![\w.])-?\d+(?![\d.]*\d)", part)
            # one number, and nothing round it but words that say "the value is now" (`increased by 5` is a change
            # written without working, not a set to 5: such a line is judged as before)
            if len(nums) != 1 or re.search(r"[()\u2192>]", part) or not set(re.findall(r"[a-z]+", part.lower())) <= SET_WORDS:
                return None
            n = int(nums[0])
            if n != cur:
                if n not in stated or n in sets:
                    return None
                sets.append(n)
            cur = n
            continue
        pieces = [x.strip() for x in part.split("=")]
        if not re.fullmatch(r"-?\d+", pieces[-1]):
            return None
        for expr, after in zip(pieces, pieces[1:]):
            first = re.match(r"\(?\s*(-?\d+)(?![\d.])", expr)
            taken = expr[first.end():] if first else expr
            if first and cur is not None and int(first.group(1)) == cur:
                pass                                 # working from the value so far
            elif re.match(r"[-+*/]\s*\(?\d", expr) and cur is not None:
                taken, expr = expr, f"({cur}) {expr}"     # working that goes on from it
            elif first and int(first.group(1)) in stated and int(first.group(1)) not in sets:
                sets.append(int(first.group(1)))     # the turns set this value and the working starts from it
                opening += 1
            else:
                return None
            if not amounts_ok(taken, amounts):
                return None
            val = _calc(expr) if re.fullmatch(r"[\d\s+\-*/().]+", expr) else None
            head = re.match(r"\(?\s*(-?\d+)(?![\d.])", after)
            if val is None or not float(val).is_integer() or not head or int(head.group(1)) != int(val):
                return None                          # not plain arithmetic, or a sum that is wrong: judged as before
            cur = int(val)
    return (cur, sets, opening) if parts > 1 else None


def apply_delta(notes: str, delta: dict, seen: set[int] | None = None, strict: bool = False,
                near: dict[str, set[int]] | None = None) -> tuple[str, dict]:
    """The NOTES after the changes, and what happened: lines changed and added, sums corrected, and `mismatch`:
    working that cannot be trusted (it starts from a value the NOTES do not hold, it starts from a number although
    the NOTES say the thing was removed, or it is arithmetic without a whole-number value); the caller then falls
    back to a full rewrite. `seen` is every number the turns being moved out state (numbers_in): working may start
    from one of those instead of the NOTES value, because the turns can set a thing and then change it and the
    model writes both on one line (`abcd12: 294 + 12 = 306`). The first run of arm N32d (rules stream, seed 0) sent
    8 of 23 cuts to the full rewrite for exactly that; all eight were such lines. With `strict`, a bare number that
    the turns do not state is `mismatch` too: a worked-out value has to show its working. With `near` (see
    numbers_near) "the turns state it" means: in a sentence that names the thing, or the one after it. RULES lines are never removed; a new rule that rewords an existing one is not added.
    A STATE line keeps its place; a value given as working is stored as its result. The OPEN section is replaced
    when the reply has one and kept otherwise."""
    rules, state, opened, sec = [], [], [], ""
    for ln in notes.splitlines():
        head = section_of(ln)
        if head:
            sec = head
        elif ln.strip() and sec == "RULES" and not _is_none(ln):
            rules.append(ln.rstrip())
        elif ln.strip() and sec == "STATE":
            state.append(ln.rstrip())
        elif ln.strip() and sec == "OPEN":
            opened.append(ln.rstrip())
    info: dict[str, Any] = {"changed": 0, "added": 0, "sums_corrected": [], "mismatch": [], "new_rules": 0}
    steps: dict[str, int] = {}                       # changes each name's lines account for (a line, or a step of its working)
    used: dict[str, set[int]] = {}                   # values of a name already taken from the turns as a set
    have = [_plain(r) for r in rules]
    for r in delta.get("rules", []):
        if not any(same_rule(r, h) for h in have):
            rules.append("- " + r)
            have.append(r)
            info["new_rules"] += 1
    where = {fact_of(ln)[0]: i for i, ln in enumerate(state)}
    ever = {v for v in (number_of(fact_of(ln)[1]) for ln in state) if v is not None}     # every value held, then and since
    for name, value in delta.get("changes", []):
        if NO_CHANGE.fullmatch(value.strip()):           # `name: (no change)`: mentioned, not changed
            steps[name] = steps.get(name, 0) + 1
            continue
        old = fact_of(state[where[name]])[1] if name in where else None
        held = number_of(old) if old is not None else None
        counted, asked = steps_in(value), len(info["mismatch"])
        if strict and seen is not None:
            # several changes on one line: followed part by part; a line that can be followed is right as it stands
            ch = chain_of(value, held, (seen if near is None else near.get(name, set())) - used.get(name, set()),
                          None if near is None else near.get(name, set()) | ever)
            if ch is not None:
                final, sets, opening = ch
                used.setdefault(name, set()).update(sets)
                steps[name] = steps.get(name, 0) + counted + opening
                info["chained"] = info.get("chained", 0) + 1
                line = f"{name}: {final}" if final is not None else f"{name}: removed"
                ever.update(n for n in map(int, re.findall(r"(?<![\w.])-?\d+(?![\d.]*\d)", REMARK.sub(" ", value).replace("\u2212", "-"))))
                if name in where:
                    state[where[name]] = line
                    info["changed"] += 1
                else:
                    where[name] = len(state)
                    state.append(line)
                    info["added"] += 1
                continue
        w = work_out(value)
        if w:
            start, total, stated = w
            # the steps the line writes, plus the set it starts from when the line opens with working from a value
            # that is not the one the NOTES hold (`585 - 79 = 506` after "opened at 585", "went down by 79")
            if start is not None and start != held and re.match(r"\s*[-\u2212]?\d+\s*[-+*/x\u00d7\u2212]", value):
                counted += 1
        steps[name] = steps.get(name, 0) + counted
        if w:
            if total is None:
                info["mismatch"].append(f"{name}: `{value}` has no whole-number value")
                total = stated
            elif start is not None and start == held:
                pass
            elif (start is not None and seen is not None and start in (seen if near is None else near.get(name, set()))
                  and start not in used.get(name, ())):
                # the turns set this value and the line starts from it; a set is good for one start
                info["set_in_turns"] = info.get("set_in_turns", 0) + 1
                used.setdefault(name, set()).add(start)
            elif start is not None and held is not None and total == held:
                # The line ends at the value the NOTES already hold, from another start: a change that was noted
                # before and is written again (with in-place notes through the proxy the newest exchange stays in
                # view, and its thought about the item just noted is read again at the next call: 6 such lines at
                # 1M, each one a reply asked for again). Applying it or not gives the same value; it is no change.
                info["renoted"] = info.get("renoted", 0) + 1
                steps[name] -= counted
                if not steps[name]:
                    del steps[name]
                continue
            elif start is not None and held is not None and held != start:
                info["mismatch"].append(f"{name}: working starts from {start}, NOTES hold {held}")
            elif start is not None and old is not None and re.match(r"(removed|closed|struck|deleted|gone)\b", old.lower()):
                info["mismatch"].append(f"{name}: working starts from {start}, NOTES say {old.split()[0]}")
            if near is not None and strict and start is not None and len(info["mismatch"]) == asked:
                expr = value.replace("\u2212", "-").split("=")[-2]
                first = re.match(r"\(?\s*-?\d+", expr.strip())
                if first and not amounts_ok(expr.strip()[first.end():], near.get(name, set()) | ever):
                    info["mismatch"].append(f"{name}: `{value}` adds or takes an amount the turns do not state for it; read the item again")
            if total != stated:
                info["sums_corrected"].append(f"{name}: {value} -> {total}")
            value = str(total)
        elif seen is not None and strict and re.search(r"[\d_]", name) and " " not in name:
            # a new number without working must be one the turns state for this thing (a set), whatever is written
            # round it (`402`, `opened at 402`, `402 (item 7)`, `-107 -> 402`); anything worked out must show its
            # working, so that the sum can be checked (N32w seed 0: `rumi16: -132` for 29 - 73, without working)
            old = fact_of(state[where[name]])[1] if name in where else None
            held, now = (number_of(old) if old is not None else None), number_of(value)
            stated = seen if near is None else near.get(name, set())
            if now is not None and now != held:
                if now not in stated:
                    info["mismatch"].append(f"{name}: {now} is not a value the turns state; write the working"
                                            + (f" from the value the NOTES hold, {held}" if held is not None else ""))
                else:
                    used.setdefault(name, set()).add(now)
        line = f"{name}: {value}" if value else name
        if number_of(value) is not None:
            ever.add(number_of(value))
        if name in where:
            state[where[name]] = line
            info["changed"] += 1
        else:
            where[name] = len(state)
            state.append(line)
            info["added"] += 1
    if delta.get("open") is not None:
        opened = list(delta["open"])
    info["steps"] = steps
    return "\n".join(["RULES"] + (rules or ["(none)"]) + ["STATE"] + state + ["OPEN"] + opened), info


def respell(delta: dict, mentions: dict[str, int]) -> tuple[dict, dict[str, str]]:
    """A line for an identifier-like name that the turns never mention, a letter or two from a name they do mention
    and for which the reply has no line, is that name misspelled: the line is given to it. Returns the reply and
    {written: meant}. (X32n2 at 1M wrote `vozi36` for `vozimi36`; the line was left out as unsupported, the count
    question about vozimi36 got an 8,192-token reply that could not be used, and the change was lost.)
    `mentions`: how often the turns mention each identifier-like name (mention_counts)."""
    import difflib
    names = list(dict.fromkeys(k for k, _ in delta["changes"]))
    free = [m for m in mentions if m not in names]
    fixed: dict[str, str] = {}
    for n in names:
        if n in mentions or len(n) < 3 or not re.search(r"[\d_]", n) or " " in n:
            continue
        tail = re.search(r"\d*$", n).group(0)
        close = [m for m in free if re.search(r"\d*$", m).group(0) == tail
                 and difflib.SequenceMatcher(None, n, m).ratio() >= 0.75]
        if len(close) == 1:
            fixed[n] = close[0]
            free.remove(close[0])
    if not fixed:
        return delta, {}
    return dict(delta, changes=[(fixed.get(k, k), v) for k, v in delta["changes"]]), fixed


DROPPABLE = ("is not a value the turns state", "adds or takes an amount the turns do not state")


def without_doubtful(notes: str, delta: dict, seen: set[int] | None, strict: bool, near: dict | None) -> tuple[dict, list[str]]:
    """The reply without the lines the checks still question because the turns do not state their number
    (DROPPABLE): after a second reply such a line was wrong or pointless every time it was looked at (campaign 12),
    so it is left out and the old value stays. One line at a time: the line of that name whose removal makes the
    question go away. Returns the reply and the lines left out."""
    changes, dropped = list(delta["changes"]), []
    for _ in range(12):
        _, info = apply_delta(notes, dict(delta, changes=changes), seen, strict=strict, near=near)
        bad = [m for m in info["mismatch"] if any(d in m for d in DROPPABLE)]
        if not bad:
            break
        name = bad[0].split(":", 1)[0]
        before = sum(m.split(":", 1)[0] == name for m in info["mismatch"])
        for i in [i for i, (k, _) in enumerate(changes) if k == name]:
            trial = changes[:i] + changes[i + 1:]
            _, t = apply_delta(notes, dict(delta, changes=trial), seen, strict=strict, near=near)
            if sum(m.split(":", 1)[0] == name for m in t["mismatch"]) < before:
                dropped.append(f"{changes[i][0]}: {changes[i][1]}")
                changes = trial
                break
        else:                                        # no single line explains it: every line of that name goes
            dropped += [f"{k}: {v}" for k, v in changes if k == name]
            changes = [(k, v) for k, v in changes if k != name]
    return dict(delta, changes=changes), dropped


def merge_replies(first: dict | None, second: dict) -> dict:
    """What to apply when a reply was asked for again: the second reply's lines for every name it mentions (also
    `name: (no change)`, which withdraws the first reply's lines for that name), and the first reply's lines for
    the names the second does not mention; rules from both; the newer OPEN section if it has one.
    Why: the retry asks for "the three complete sections again", but a model sometimes answers with only the lines
    that were in question, or with (none). The proxy's second 240K run (campaign 11, X32i seed 1) applied such a
    reply on its own and lost every change of nine items: 15 counters wrong in the NOTES, 6 answers."""
    if not first:
        return second
    named = {k for k, _ in second["changes"]}
    rules = list(first["rules"]) + [r for r in second["rules"] if not any(same_rule(r, x) for x in first["rules"])]
    return {"rules": rules, "changes": [(k, v) for k, v in first["changes"] if k not in named] + list(second["changes"]),
            "open": second["open"] if second.get("open") is not None else first.get("open")}


def section_of(line: str) -> str:
    """RULES, STATE or OPEN if the line is that heading (plain, with a colon, or as a markdown heading), else ''."""
    head = line.strip().strip("#*_ ").rstrip(":").strip("*_ ").upper()
    return head if head in ("RULES", "STATE", "OPEN") else ""


# `name: (no change)`, also with a remark after it: `(no change - the mention is the rule itself)`. A run with six items
# per notes call stored such a remark as the value of a counter and lost its number (2026-10-12, arm N32u6).
NO_CHANGE = re.compile(r"\(?\s*(no change|unchanged|not changed|no changes)\b.*", re.I | re.S)


MISMATCH_RETRY = ("Check these lines of your CHANGES against the NOTES and the turns: {lines}. Working must start from the "
                  "value the NOTES hold, or from a value the turns set; when the turns set a new value and then change "
                  "it, write the set as a line of its own first. Then reply with the three complete sections again.")


def state_keys(notes: str) -> list[str]:
    """The names of the STATE lines of the NOTES."""
    keys, sec = [], ""
    for ln in notes.splitlines():
        head = section_of(ln)
        if head:
            sec = head
        elif ln.strip() and sec == "STATE":
            keys.append(fact_of(ln)[0])
    return keys


COUNT_RETRY = ("The turns mention these names more often than your CHANGES account for: {names}. Go through the turns again "
               "for each of them, one mention at a time. Then reply with the three complete sections again, every change "
               "included: a change is a line of its own or one step in the working of a line. For a mention that changes "
               "nothing, write `name: (no change)`.")


def under_accounted(mentions: dict[str, int], steps: dict[str, int]) -> list[str]:
    """`name (mentioned 3 times, 2 changes written)` for every name whose lines account for fewer changes than the
    items mention it. N32z seed 0: three counters went wrong in the NOTES although each had a line (the second of two
    changes in one item was left out twice); a check for names without any line cannot see that."""
    return [f"{n} (mentioned {c} times, {steps.get(n, 0)} changes written)" for n, c in mentions.items() if steps.get(n, 0) < c]


def rule_lines(notes: str) -> list[str]:
    """Lines of the RULES section (between the line RULES and the line STATE), bullets stripped."""
    lines, on = [], False
    for ln in notes.splitlines():
        s, head = ln.strip(), section_of(ln)
        if head:
            on = head == "RULES"
        elif on and s:
            lines.append(s.lstrip("-* ").strip())
    return [ln for ln in lines if ln and ln.lower().strip("().") != "none"]


def same_rule(a: str, b: str) -> bool:
    """Two wordings of one rule: most of the words of the shorter are in the longer, and both name the same things
    (every word with a digit in it: names such as abcd12, and numbers). "abcd12 is secret" and "efgh34 is secret"
    share all but one word and are two rules."""
    wa, wb = set(re.findall(r"\w+", a.lower())), set(re.findall(r"\w+", b.lower()))
    named = lambda w: {t for t in w if any(c.isdigit() for c in t)}
    return bool(wa and wb) and named(wa) == named(wb) and len(wa & wb) >= 0.8 * min(len(wa), len(wb))

# ---- end of the copy ----


TRAILER = re.compile(r"\n*\(exit_code=-?\d+\)\s*$")       # a shell tool's status line is not part of what was said


def _sentences(text: str) -> list[str]:
    text = re.sub(r"ITEM \d+/\d+ \(\w+\)", " ", TRAILER.sub("", text))
    return [s for s in re.split(r"(?<=[.!?])\s+", " ".join(text.split())) if s]


def statements(texts: list[str]) -> list[list[str]]:
    """Each text as its sentences, questions left out (a mention inside a question changes nothing)."""
    return [[s for s in _sentences(t) if not s.endswith("?")] for t in texts]


def _checked(names: list[str]) -> list[str]:
    """Only names that look like identifiers (a digit or an underscore in them) are checked: a plain word can turn
    up anywhere."""
    return [n for n in dict.fromkeys(names) if len(n) >= 3 and re.search(r"[\d_]", n) and " " not in n]


def identifiers_in(texts: list[str]) -> list[str]:
    """Identifier-like words (letters then digits: abcd12, build_7) that the texts mention outside questions:
    things a reply may have left out altogether."""
    seen: dict[str, None] = {}
    for sents in statements(texts):
        for sent in sents:
            for w in re.findall(r"(?<![\w])[a-z]{2,}_?\d+[a-z0-9_]*(?![\w])", sent.lower()):
                seen.setdefault(w)
    return list(seen)


def mention_counts(names: list[str], texts: list[str]) -> dict[str, int]:
    """How often each (identifier-like) name is mentioned in the texts, outside questions."""
    low = " ".join(s for sents in statements(texts) for s in sents).lower()
    out = {n: len(re.findall(rf"(?<![\w]){re.escape(n)}(?![\w])", low)) for n in _checked(names)}
    return {n: c for n, c in out.items() if c}


def numbers_near(names: list[str], texts: list[str], signed: bool = True) -> dict[str, set[int]]:
    """For each (identifier-like) name: the numbers stated in a sentence that mentions it, or in the sentence right
    after one ("Next on the list was abcd12. It was opened at 591."), with the sign as stated. Neighbours are taken
    in the text as written (a question between two statements stays between them)."""
    want, out = set(_checked(names)), {}
    for t in texts:
        sents = _sentences(t)
        for i, sent in enumerate(sents):
            here = want & set(re.findall(r"[a-z0-9_]+", sent.lower()))
            if here:
                nums = numbers_in(sent, signed) | (numbers_in(sents[i + 1], signed) if i + 1 < len(sents) else set())
                for n in here:
                    out.setdefault(n, set()).update(nums)
    return out
