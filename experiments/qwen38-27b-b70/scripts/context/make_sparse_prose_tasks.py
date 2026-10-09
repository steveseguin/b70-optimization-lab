#!/usr/bin/env python3
"""Generate "sparse prose" ledger tasks: ordinary narrative with only a FEW real counter changes.

Why: the dense prose ledger was too hard in ONE step (single-call probe, thinking off: 38 % of
changed counters right at 6.4K-token batches, 53 % at 2K), so a long run on it measures step
difficulty, not context management. Here each batch is mostly irrelevant narrative filler (varied,
template/grammar generated, never naming a counter) with a dialled number of real changes, and the
difficulties are switched on one at a time, so the single-step accuracy can be calibrated first
(calibrate-reading.sh) and the long run then tests reading more text than the window holds.

Real changes (default: name stated explicitly, digits):
  set / open (a new or removed counter), add, subtract, remove from the ledger.
Difficulty switches (each adds ONE kind of difficulty):
  --words        numbers in change sentences written as words ("forty-two", "minus seven")
  --pronouns     every change names its counter in one sentence and changes it in the next one by
                 "it" / "that counter" (one pronoun reference per change)
  --corrections  some sets are corrected later in the same batch ("Correction: the figure for X given
                 above should have been 40, not 14.") -> the corrected value counts
  --plans        some changes are announced as plans; a later sentence says whether the plan went
                 ahead (applies) or was cancelled (nothing changes)
  --relative     some changes are relative: doubled, lost a third (only when divisible by 3),
                 went up by as much as another named counter holds at that moment
  --all          all of the above
--surprise K   K hidden retention questions in the final item (keys s1..sK): the value a counter held at
               the end of item b (later overwritten), who did X at Y in item b, a small number in item b.
               Answers are graded exactly (numbers as integers; names case- and article-insensitive). The
               report text is identical with and without --surprise.
--density D = mean real changes per 2,000 tokens of text (default 3).
Same grader, layout and per-batch reference (tests/reference.json: state and operations after every
batch) as make_prose_ledger_tasks.py; task metadata kind = "sparse".

Usage:
  make_sparse_prose_tasks.py OUT_DIR --tokens 60000 120000 480000 [--density 3] [--words] ...
                             [--mode memory|notes] [--seeds 0 1] [--batch-tokens 2000] [--n-batches N]
"""
from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path

from make_kvstream_tasks import DEFAULT_TOKENIZER, STORAGE_MEMORY, STORAGE_NOTES, word, write_task
from make_prose_ledger_tasks import words as num_words

PEOPLE = ["the night porter", "the head clerk", "a young apprentice", "the foreman", "the cook", "the driver",
          "the new bookkeeper", "a visiting inspector", "the caretaker", "two of the packers", "the signalman",
          "the stable hand", "the telegraph boy", "the quartermaster", "an elderly customer", "the ferryman"]
ACTS = ["swept the loading bay", "repainted the north door", "argued about the radio", "found a lost glove",
        "mended a torn sack", "fed the yard cat", "oiled the big scale", "read the morning paper aloud",
        "carried the empty crates outside", "complained about the draught", "polished the brass bell",
        "counted the windows twice for no reason", "hummed an old song", "fixed the squeaking hinge",
        "brewed a pot of strong tea", "chased a pigeon out of the hall", "rearranged the coat hooks",
        "wrote a letter home", "lost a pencil and found it again", "watched the barges go by"]
PLACES = ["near the canal", "behind the depot", "on the second floor", "by the east gate", "in the back office",
          "under the old clock", "beside the coal shed", "at the top of the stairs", "in the courtyard",
          "next to the weighbridge"]
TIMES = ["after lunch", "at dawn", "before the rain", "around eleven o'clock", "late in the evening",
         "during the tea break", "just after the bell", "while the kettle boiled", "on the way home",
         "before anyone else arrived"]
WEATHER = ["A cold wind came off the river.", "It rained for most of the morning.", "The fog lifted slowly.",
           "The sun came out briefly around noon.", "Snow had settled on the roofs overnight.",
           "The afternoon was warm and still.", "A storm was forecast but never came."]
SMALL = ["The bus was {n} minutes late.", "Someone counted {n} gulls on the roof.",
         "The kettle took {n} minutes to boil.", "The walk to the station took {n} minutes.",
         "There were {n} chairs in the meeting room.", "The old clock was {n} seconds fast."]

INSTRUCTION = """\
You are connected to a ledger stream. Run the command `next` to receive the next item of the
stream. There are {total} items: {n_batches} batch(es) of a narrative day book (one batch is
about {batch_tokens:,} tokens){probe_note}, then one final item that lists {n_get} counters to report. The
whole stream is about {stream_tokens:,} tokens and concerns {n_counters} named counters (names such
as `{example}`).

Most of the day book is ordinary narrative that changes nothing. Only sentences about the named
counters change them: a counter can be set to a value, opened (new or removed counter) at a value,
increased, decreased{rel}, or removed from the ledger (a later sentence may open it again).
{extra}
Rules:
- Each item is printed once and then deleted; it cannot be fetched again.
- You do not know in advance which counters will be asked for.
- Do not read or copy anything under /opt/kvstream directly; only use `next`.
- When you have received the final item, write /app/answers.json: a JSON object mapping each
  listed counter to its current integer value, or null if the counter has been removed at the
  end of the stream. If you no longer know a value, map it to "" — a blank scores the same as a
  wrong value, but blanks are reported separately as admitted losses.

{storage_rule}
Your score is the fraction of listed counters whose value is exactly right.
"""


class Sparse:
    def __init__(self, rng: random.Random, n_counters: int, opts: dict):
        self.r, self.o = rng, opts
        names: list[str] = []
        while len(names) < n_counters:
            nm = f"{word(rng)}{rng.randint(10, 99)}"
            if nm not in names:
                names.append(nm)
        self.names = names
        self.state: dict[str, int] = {}
        self.history: dict[str, list[int]] = {n: [] for n in names}
        self.ever: set[str] = set()
        self.ops: list[list] = []
        self.fill_log: list[dict] = []     # structured record of this batch's filler (for --surprise)

    def num(self, n: int) -> str:
        return num_words(n) if self.o["words"] and self.r.random() < 0.7 else str(n)

    def apply(self, nm, op, arg):
        old = self.state.get(nm)
        if op in ("set", "correct"):
            self.state[nm] = arg
        elif op == "add":
            self.state[nm] += arg
        elif op == "del":
            self.state.pop(nm)
        elif op == "double":
            self.state[nm] *= 2
        elif op == "third":
            self.state[nm] -= self.state[nm] // 3
        elif op == "from":
            self.state[nm] += self.state[arg]
        if old is not None:
            self.history[nm].append(old)
        self.ever.add(nm)
        self.ops.append([nm, op, arg, self.state.get(nm), 0])

    def filler(self) -> str:
        r = self.r
        k = r.random()
        if k < 0.15:
            return r.choice(WEATHER)
        if k < 0.25:
            t, n = r.choice(SMALL), r.randint(2, 40)
            self.fill_log.append({"kind": "small", "t": t, "n": n})
            return t.format(n=n)
        who, act, place, when = r.choice(PEOPLE), r.choice(ACTS), r.choice(PLACES), r.choice(TIMES)
        self.fill_log.append({"kind": "act", "who": who, "act": act, "place": place})
        s = f"{who} {act} {place} {when}."
        return s[0].upper() + s[1:]

    def change(self) -> list[str]:
        """One real change (or a plan with its outcome), as one to three sentences."""
        r, o = self.r, self.o
        live = sorted(self.state)
        # mostly change existing counters once a few exist (otherwise early batches are all openings)
        nm = r.choice(live) if len(live) >= 8 and r.random() < 0.8 else r.choice(self.names)
        if nm not in self.state:
            v = r.randint(-200, 600)
            sents = self._say(nm, "set", v, opening=True)
            self.apply(nm, "set", v)
            return sents
        kinds = ["set", "add", "add", "sub", "sub", "del"]
        if o["relative"]:
            kinds += ["double", "third", "from"]
        if o["plans"]:
            kinds += ["plan"]
        k = r.choice(kinds)
        v = self.state[nm]
        if k == "third" and (v == 0 or v % 3):
            k = "add"
        if k == "double" and abs(v) > 3000:
            k = "sub"
        others = [x for x in self.state if x != nm and self.state[x] > 0]
        if k == "from" and not others:
            k = "add"
        if k == "plan":
            amt = r.randint(2, 90)
            add = r.random() < 0.5
            ahead = r.random() < 0.5
            s1 = r.choice(["There were plans to {v} {n} {p} {x}.", "Someone proposed to {v} {n} {p} {x}."]).format(
                v="add" if add else "take", n=self.num(amt), p="to" if add else "from", x=nm)
            gap = [self.filler() for _ in range(r.randint(0, 2))]
            if ahead:
                s2 = r.choice(["The planned change to {x} went ahead.", "In the end the plan for {x} was carried out."])
                self.apply(nm, "add", amt if add else -amt)
            else:
                s2 = r.choice(["The plan for {x} was cancelled.", "In the end nothing came of the plan for {x}."])
            return [s1] + gap + [s2.format(x=nm)]
        if k == "set":
            n = r.randint(-200, 600)
            sents = self._say(nm, "set", n)
            self.apply(nm, "set", n)
            if o["corrections"] and r.random() < 0.35:
                new = n + r.choice([-1, 1]) * r.randint(1, 60)
                sents += [self.filler() for _ in range(r.randint(0, 2))]
                sents.append(r.choice([
                    "Correction: the figure for {x} given above should have been {new}, not {old}.",
                    "The figure written above for {x} was a slip; it is {new}, not {old}."]).format(
                    x=nm, new=self.num(new), old=self.num(n)))
                self.apply(nm, "correct", new)
            return sents
        if k in ("add", "sub"):
            n = r.randint(2, 90)
            sents = self._say(nm, k, n)
            self.apply(nm, "add", n if k == "add" else -n)
            return sents
        if k == "del":
            sents = self._say(nm, "del", None)
            self.apply(nm, "del", None)
            return sents
        if k == "from":
            src = r.choice(others)
            sents = self._say(nm, "from", src)
            self.apply(nm, "from", src)
            return sents
        sents = self._say(nm, k, None)
        self.apply(nm, k, None)
        return sents

    def _say(self, nm, op, arg, opening=False) -> list[str]:
        r, o = self.r, self.o
        ref = nm
        pre: list[str] = []
        if o["pronouns"]:
            pre = [r.choice(["Attention then turned to {x}.", "Next on the list was {x}.",
                             "The clerk opened the page for {x}.", "Then someone asked about {x}."]).format(x=nm)]
            ref = r.choice(["it", "that counter"])
        n = self.num(arg) if isinstance(arg, int) else None
        if op == "set" and opening:
            t = r.choice(["{R} was opened at {n}.", "A new page was started for {r}, at {n}.",
                          "{R} came onto the books at {n}."])
        elif op == "set":
            t = r.choice(["{R} was set to {n}.", "{R} now stands at {n}.", "The clerk recorded {r} at {n}."])
        elif op == "add":
            t = r.choice(["{R} went up by {n}.", "{R} gained {n}.", "Another {n} went into {r}."])
        elif op == "sub":
            t = r.choice(["{R} went down by {n}.", "{R} lost {n}.", "{N} were taken from {r}."])
        elif op == "del":
            t = r.choice(["{R} was removed from the ledger.", "{R} was struck off the books."])
        elif op == "double":
            t = r.choice(["{R} doubled.", "{R} was doubled."])
        elif op == "third":
            t = r.choice(["{R} lost a third of its value.", "A third of {r} was written off."])
        else:  # from
            t = r.choice(["{R} went up by as much as {s} held at that moment.",
                          "{R} received exactly what {s} stood at then."]).format(R="{R}", r="{r}", s=arg, n="{n}", N="{N}")
        cap = (ref[0].upper() + ref[1:]) if ref in ("it", "that counter") else ref
        out = t.format(R=cap, r=ref, n=n, N=(n[0].upper() + n[1:]) if n and not n[0].isdigit() and n[0] != "-" else n)
        return pre + [out]


def surprise_questions(srng: random.Random, k: int, refs: list, fills: list, final: dict) -> list:
    """k questions, half about old values (a counter's value at the end of item b that a later item
    overwrote), half about filler details that occur exactly once in their item (who did X at Y; a small
    number). Returns (key, question, answer, type, item)."""
    nb = len(refs)
    old = []
    for b in range(1, nb - 1):
        for c, v in refs[b - 1]["state"].items():
            if final.get(c) != v and refs[b - 1]["state"].get(c) != (refs[b - 2]["state"].get(c) if b >= 2 else None):
                old.append((b, c, v))
    det = []
    for b, fl in enumerate(fills, 1):
        acts = [f for f in fl if f["kind"] == "act"]
        for f in acts:
            if sum(1 for x in acts if x["act"] == f["act"] and x["place"] == f["place"]) == 1:
                det.append((b, "who", f))
        smalls = [f for f in fl if f["kind"] == "small"]
        for f in smalls:
            if sum(1 for x in smalls if x["t"] == f["t"]) == 1:
                det.append((b, "small", f))
    out = []
    n_old = min(len(old), k // 2)
    for b, c, v in srng.sample(old, n_old):
        out.append((f"What value did {c} hold at the end of item {b}?", v, "old_value", b))
    picks = srng.sample(det, min(len(det), k - n_old))
    small_q = {"The bus was {n} minutes late.": "how many minutes late was the bus",
               "Someone counted {n} gulls on the roof.": "how many gulls were counted on the roof",
               "The kettle took {n} minutes to boil.": "how many minutes did the kettle take to boil",
               "The walk to the station took {n} minutes.": "how many minutes did the walk to the station take",
               "There were {n} chairs in the meeting room.": "how many chairs were in the meeting room",
               "The old clock was {n} seconds fast.": "how many seconds fast was the old clock"}
    for b, kind, f in picks:
        if kind == "who":
            out.append((f"In item {b}, who {f['act']} {f['place']}?", f["who"], "who", b))
        else:
            out.append((f"In item {b}, {small_q[f['t']]}?", f["n"], "small", b))
    srng.shuffle(out)
    return [(f"s{i}", q, a, t, b) for i, (q, a, t, b) in enumerate(out, 1)]


PROBE_BINS = ((1, 4), (5, 24), (25, 99), (100, 399), (400, 10 ** 9))


def probe_questions(prng: random.Random, after_batch: int, k: int, refs: list, fills: list, bt: list,
                    item_no: dict, used: set) -> list:
    """k questions delivered as a PROBE item right after batch `after_batch`, about earlier batches at
    controlled distances (one per distance bin, cycling through the bins that exist yet). Types:
    current (a counter's value now; distance = since its last change), old_value (a value later
    overwritten), who / small (a filler detail that occurs once in its batch). Returns
    (question, answer, type, ref_batch, distance_items, tokens_back)."""
    b = after_batch
    state = lambda i: refs[i - 1]["state"]          # state after batch i (1-based)
    now = state(b)
    cands = {}
    # current: counters alive now, keyed by the batch of their last change
    last = {}
    for i in range(1, b + 1):
        prev = state(i - 1) if i > 1 else {}
        for c, v in state(i).items():
            if prev.get(c) != v:
                last[c] = i
    for c, i in last.items():
        if c in now:
            cands.setdefault(b - i, []).append(("current", c, i, now[c], f"What value does {c} hold now?"))
    # old values: v held by c at the end of batch i, set at i, and no longer the value now
    for i in range(1, b):
        prev = state(i - 1) if i > 1 else {}
        for c, v in state(i).items():
            if prev.get(c) != v and now.get(c) != v:
                cands.setdefault(b - i, []).append(("old_value", c, i, v, f"What value did {c} hold at the end of item {item_no[i]}?"))
    small_q = {"The bus was {n} minutes late.": "how many minutes late was the bus",
               "Someone counted {n} gulls on the roof.": "how many gulls were counted on the roof",
               "The kettle took {n} minutes to boil.": "how many minutes did the kettle take to boil",
               "The walk to the station took {n} minutes.": "how many minutes did the walk to the station take",
               "There were {n} chairs in the meeting room.": "how many chairs were in the meeting room",
               "The old clock was {n} seconds fast.": "how many seconds fast was the old clock"}
    for i in range(1, b + 1):
        fl = fills[i - 1]
        acts = [f for f in fl if f["kind"] == "act"]
        for f in acts:
            if sum(1 for x in acts if x["act"] == f["act"] and x["place"] == f["place"]) == 1:
                cands.setdefault(b - i, []).append(("who", None, i, f["who"], f"In item {item_no[i]}, who {f['act']} {f['place']}?"))
        smalls = [f for f in fl if f["kind"] == "small"]
        for f in smalls:
            if sum(1 for x in smalls if x["t"] == f["t"]) == 1:
                cands.setdefault(b - i, []).append(("small", None, i, f["n"], f"In item {item_no[i]}, {small_q[f['t']]}?"))
    out = []
    bins = [(lo, hi) for lo, hi in PROBE_BINS if lo <= b]
    types = (("current",), ("old_value",), ("who", "small"))   # one of each per probe, then repeat
    start = prng.randrange(len(bins))                            # the bin each probe starts from varies
    for j in range(k):
        want = types[j % len(types)]
        picked = None
        for step in range(len(bins)):                            # nearest bin that has a candidate
            lo, hi = bins[(start + j + step) % len(bins)]
            pool = [q for d, qs in cands.items() if lo <= d <= hi for q in qs
                    if q[0] in want and (q[0], q[1], q[2], q[4]) not in used]
            if pool:
                picked = prng.choice(pool)
                break
        if picked is None:
            continue
        t, c, i, a, q = picked
        used.add((t, c, i, q))
        out.append((q, a, t, i, b - i, sum(bt[i:b])))
    return out


def build(out: Path, name: str, target_tokens: int, seed: int, batch_tokens: int, density: float,
          n_get: int, n_counters: int, mode: str, opts: dict, cpt: float, count_exact,
          n_batches: int | None, surprise: int = 0, probes_every: int = 0, probes_k: int = 3) -> dict:
    tag = "".join(k[0] for k in ("words", "pronouns", "corrections", "plans", "relative") if opts[k]) or "plain"
    rng = random.Random(f"sparse-{seed}-{target_tokens}-{batch_tokens}-{density}-{tag}-{n_counters}")
    g = Sparse(rng, n_counters, opts)
    count = count_exact or (lambda t: int(len(t) / cpt))
    batches, refs, tokens = [], [], 0
    fills = []
    bt: list[int] = [0]   # tokens per batch, 1-based
    while True:
        g.ops = []
        g.fill_log = []
        mean = density * batch_tokens / 2000
        k = max(0, round(rng.gauss(mean, max(1.0, mean ** 0.5))))
        units = [g.change() for _ in range(k)]
        # interleave the changes with filler until the batch has its size
        sents: list[str] = []
        budget_chars = batch_tokens * cpt
        filler_needed = max(0, budget_chars - sum(len(" ".join(u)) for u in units))
        fill: list[str] = []
        while sum(len(f) + 1 for f in fill) < filler_needed:
            fill.append(g.filler())
        slots = sorted(rng.sample(range(len(fill) + len(units)), len(units))) if units else []
        ui = fi = 0
        for pos in range(len(fill) + len(units)):   # a change (with its pronoun/plan/correction
            if ui < len(units) and pos == slots[ui]:   # sentences) stays in one paragraph
                sents.append(" ".join(units[ui])); ui += 1
            elif fi < len(fill):
                sents.append(fill[fi]); fi += 1
        paras, i = [], 0
        while i < len(sents):
            n = rng.randint(4, 7)
            paras.append(" ".join(sents[i:i + n])); i += n
        text = "\n\n".join(paras)
        batches.append(text)
        refs.append({"state": dict(g.state), "ops": g.ops})
        fills.append(g.fill_log)
        bt.append(count(text))
        tokens += bt[-1]
        if n_batches is not None:
            if len(batches) >= n_batches:
                break
        elif tokens + count(text) / 2 >= target_tokens:
            break
    gone = sorted(n for n in g.ever if n not in g.state)
    alive = sorted(g.state)
    n_gone = min(len(gone), max(1, n_get // 8)) if gone else 0
    queried = rng.sample(gone, n_gone) + rng.sample(alive, min(n_get - n_gone, len(alive)))
    rng.shuffle(queried)
    exp = {n: g.state.get(n) for n in queried}
    # item numbering: probes (--probes-every N) are delivered as items of their own after every N-th batch
    n_probes = (len(batches) - 1) // probes_every if probes_every else 0
    total = len(batches) + n_probes + 1
    item_no: dict[int, int] = {}
    n_item = 0
    probe_after: list[int] = []
    for bi in range(1, len(batches) + 1):
        n_item += 1
        item_no[bi] = n_item
        if probes_every and bi % probes_every == 0 and bi < len(batches):
            n_item += 1
            probe_after.append(bi)
    # --surprise K: hidden retention questions (asked only in the final item) about OLD values that were
    # later overwritten and about details of the narrative filler. A separate random stream, so the
    # report text is identical with and without --surprise.
    asks = surprise_questions(random.Random(f"surprise-{seed}-{target_tokens}-{density}-{tag}"), surprise,
                              refs, fills, g.state) if surprise else []
    if probes_every:
        asks = [(k, re.sub(r"item (\d+)", lambda m: f"item {item_no[int(m.group(1))]}", q), a, t, b) for k, q, a, t, b in asks]
    for key, q, a, _t, _b in asks:
        exp[key] = a
    probes: dict[str, dict] = {}
    probe_items: dict[int, str] = {}
    if probes_every:
        prng = random.Random(f"probes-{seed}-{target_tokens}-{density}-{tag}-{probes_every}-{probes_k}")
        used: set = set()
        for j, bi in enumerate(probe_after, 1):
            qs = probe_questions(prng, bi, probes_k, refs, fills, bt, item_no, used)
            lines = []
            for i, (q, a, t, rb, dist, back) in enumerate(qs, 1):
                key = f"p{j}_{i}"
                exp[key] = a
                probes[key] = {"q": q, "a": a, "type": t, "item": item_no[bi] + 1, "ref_item": item_no[rb],
                               "distance": item_no[bi] + 1 - item_no[rb], "tokens_back": back}
                lines.append(f"ASK {key}: {q}")
            probe_items[bi] = ("PROBE: answer these questions now, before fetching the next item. Add the keys to "
                               "/app/answers.json (create it if needed; keep every key already in it; a number, or the "
                               "words asked for; \"\" if you no longer know). Then continue with `next`.\n" + "\n".join(lines))
    ask_txt = ("\n\nAlso answer these questions about earlier items in /app/answers.json, under the keys "
               "given (a number, or the words asked for):\n" + "\n".join(f"ASK {k}: {q}" for k, q, _a, _t, _b in asks)
               ) if asks else ""
    items = []
    for bi, b in enumerate(batches, 1):
        items.append({"kind": "UPDATE", "total": total, "text": b})
        if bi in probe_items:
            items.append({"kind": "PROBE", "total": total, "text": probe_items[bi]})
    items.append({"kind": "QUERY", "total": total,
                  "text": "The auditors ask for the current value of each counter below (null if it has "
                          "been removed). Answer in /app/answers.json:\n" + "\n".join(f"QUERY {n}" for n in queried)
                          + ask_txt,
                  "last": "This was the last item. Write /app/answers.json now."})
    spec = {"kind": "ledger", "mode": mode, "expected": exp,
            "history": {n: g.history[n] for n in queried},
            "all_names": sorted(g.ever), "n_items": total}
    extra = []
    if opts["pronouns"]:
        extra.append('A counter may be named in one sentence and changed in the next as "it" or "that counter".')
    if opts["corrections"]:
        extra.append('A correction of a figure given earlier ("should have been 40, not 14") replaces that figure.')
    if opts["plans"]:
        extra.append("A plan changes a counter only if a later sentence says it went ahead.")
    if probes:
        extra.append("Some items are PROBE items: a few questions about earlier items (a counter's value now, "
                     "the value it held at the end of a given item, or a detail of the day book: who did something, "
                     "a small number). Answer them at once in /app/answers.json under the keys given (p1_1, p1_2, ...), "
                     "keeping every key already in the file, then continue with `next`. Items are numbered as "
                     "delivered (ITEM n/total); questions refer to those numbers.")
    if asks:
        extra.append("The final item may also ask questions about earlier items: a value a counter held at the "
                     "end of a given item, or a detail of the day book (who did something, a small number); answer "
                     "them in /app/answers.json under the keys it gives (s1, s2, ...).")
    rel = ", doubled, reduced by a third, or increased by as much as another counter holds" if opts["relative"] else ""
    instr = INSTRUCTION.format(
        total=total, n_batches=len(batches), batch_tokens=tokens // len(batches), n_get=len(queried),
        probe_note=(f", {len(probe_after)} PROBE items with questions in between" if probes else ""),
        stream_tokens=tokens, n_counters=len(g.ever), example=g.names[0], rel=rel,
        extra=("\n".join(extra) + "\n") if extra else "",
        storage_rule=STORAGE_MEMORY.replace("values, keys, SET lines", "counter names, values, report text")
        if mode == "memory" else STORAGE_NOTES)
    d = out / name
    write_task(d, items=items, spec=spec, answers_oracle=exp, instruction=instr, mode=mode,
               end_text="STREAM END: no more items. Answer the final query in /app/answers.json, then submit.",
               metadata={"seed": seed, "target_tokens": target_tokens, "stream_tokens": tokens,
                         "token_counter": "tokenizer" if count_exact else f"chars/{cpt}",
                         "batch_tokens": tokens // len(batches), "density": density, "setting": tag,
                         "n_get": len(queried), "n_counters": len(g.ever), "n_deleted_queried": n_gone,
                         "n_surprise": len(asks), "n_probes": len(probes), "probes_every": probes_every},
               description=f"sparse prose ledger ({tag}, density {density}), {mode}, ~{tokens} tokens, seed {seed}",
               kind="sparse")
    (d / "tests" / "reference.json").write_text(json.dumps({
        "after_batch": refs,
        "surprise": {k: {"q": q, "a": a, "type": t, "item": b} for k, q, a, t, b in asks},
        "probes": probes, "item_no": item_no, "batch_tokens_list": bt[1:]}))
    return {"name": name, "setting": tag, "density": density, "n_batches": len(batches),
            "stream_tokens": tokens, "counters": len(g.ever), "probes": len(probes),
            "changes": sum(len([o for o in r["ops"]]) for r in refs)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out")
    ap.add_argument("--tokens", type=int, nargs="+", default=[120000])
    ap.add_argument("--n-batches", type=int, default=None, help="fixed number of batches (overrides --tokens)")
    ap.add_argument("--mode", choices=["memory", "notes"], default="memory")
    ap.add_argument("--seeds", type=int, nargs="+", default=[0])
    ap.add_argument("--batch-tokens", type=int, default=2000)
    ap.add_argument("--density", type=float, default=3.0)
    for f in ("words", "pronouns", "corrections", "plans", "relative", "all"):
        ap.add_argument(f"--{f}", action="store_true")
    ap.add_argument("--n-get", type=int, default=24)
    ap.add_argument("--probes-every", type=int, default=0,
                    help="deliver a PROBE item (questions about earlier items, answered at once) after every N-th batch")
    ap.add_argument("--probes-k", type=int, default=3, help="questions per PROBE item (one per distance bin, cycling)")
    ap.add_argument("--surprise", type=int, default=0,
                    help="add K hidden retention questions to the final item (old values, filler details)")
    ap.add_argument("--n-counters", type=int, default=60)
    ap.add_argument("--chars-per-token", type=float, default=3.9)
    ap.add_argument("--exact-tokens", action="store_true")
    a = ap.parse_args()
    opts = {k: (getattr(a, k) or a.all) for k in ("words", "pronouns", "corrections", "plans", "relative")}
    count_exact = None
    if a.exact_tokens:
        from tokenizers import Tokenizer
        tok = Tokenizer.from_file(DEFAULT_TOKENIZER)
        count_exact = lambda t: len(tok.encode(t).ids)  # noqa: E731
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for n in ([0] if a.n_batches else a.tokens):
        for s in a.seeds:
            size = f"b{a.n_batches}" if a.n_batches else f"t{n // 1000}k"
            print(json.dumps(build(out, f"sparse-{a.mode}-{size}-s{s}", n, s, a.batch_tokens, a.density,
                                   a.n_get, a.n_counters, a.mode, opts, a.chars_per_token, count_exact,
                                   a.n_batches, a.surprise, a.probes_every, a.probes_k)))


if __name__ == "__main__":
    main()
