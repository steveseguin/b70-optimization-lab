#!/usr/bin/env python3
"""Generate "prose ledger" Harbor tasks: the ledger task's hidden state machine told as narrative.

Why: on the line-format ledger the model writes a parser once and pipes every batch through it
(478K-token run: 2 of 76 batches read by the model). Here every batch is prose that a regex or a
small script cannot reliably parse, while a careful reader finds exactly one reading, so the task
tests reading more text than the window holds.

Hidden state: ~160 named counters (names like `kesuro41`). Operations (all exact integers):
  set / open          the counter is set to a value (opening a removed or new counter)
  add / subtract      the counter gains or loses an amount
  delete              the counter is removed from the ledger (a later set opens it again)
  double              the counter doubles
  lose a third        only when the value is divisible by 3 and not 0
  gain from other     gains as much as another (positive) counter holds at that point
  correction          "the figure given for X above was a typo: it should have read 40, not 14"
                      (only right after a set of X with nothing else done to X since) -> X = 40
Surface: dozens of templates per operation composed from parts (lead-ins, verbs, number forms,
connectors), numbers as digits or words ("minus forty-two"), counters named once per paragraph
and then referred to as "it", "the former"/"the latter", "the second of these", "the counter named
before the audit", two or three counters interleaved per paragraph. Distractors that change
nothing: hypotheticals ("had ..., X would have gained 30"), negations ("nobody added 12 to X"),
plans that a later sentence cancels (and plans that a later sentence confirms, which DO apply),
old values recalled ("X stood at 412 back in the spring"), and look-alike names that are not in
the ledger. Every paragraph has one correct reading; the generator applies exactly that reading.

Grading is the ledger task's (tests/grade.py from make_kvstream_tasks.GRADE_PY_V2, spec kind
"ledger": exact integers, null for deleted, memory-only / with-notes rule). Hidden extras in
tests/: reference.json = the true state after every batch and the true operations per batch
(op "distractor" entries name a counter and a number a careless reader might apply; they never
change the state), for replay_state_check.py. Task metadata kind = "prose".

Token sizes: chars / --chars-per-token (default 3.9, an estimate for English prose with the Qwen
tokenizer) unless --exact-tokens is given (loads the model's tokenizer.json with `tokenizers`).

Usage:
  make_prose_ledger_tasks.py OUT_DIR --tokens 60000 120000 480000 --mode memory|notes [--seeds 0 1]
  make_prose_ledger_tasks.py OUT_DIR --smoke [--mode memory]
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from make_kvstream_tasks import DEFAULT_TOKENIZER, STORAGE_MEMORY, STORAGE_NOTES, word, write_task

INSTRUCTION = """\
You are connected to a ledger stream. Run the command `next` to receive the next item of the
stream. There are {total} items: {n_batches} batch(es) of narrative reports (one batch is about
{batch_tokens:,} tokens), then one final item that lists {n_get} counters to report. The whole
stream is about {stream_tokens:,} tokens and concerns {n_counters} named counters (names such as
`{example}`).

The reports are written as prose. Each counter holds an integer. A report can set a counter to a
value, open a new or removed counter at a value, add to it or take from it, double it, take a
third of it away, add to it as much as another counter holds at that moment, or remove it from
the ledger (a later report may open it again). A correction of a figure stated earlier ("the
figure given for X above was a typo: it should have read 40, not 14") replaces that figure.
Statements about what would have happened, what did not happen, plans that were abandoned,
values recalled from the past, and names that are said not to be part of the ledger change
nothing. Counters may be named once and then referred to as "it", "the former", "the latter",
"the second of these" and the like; each such reference means exactly one counter.

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

ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
        "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen",
        "nineteen"]
TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]


def words(n: int) -> str:
    if n < 0:
        return "minus " + words(-n)
    if n < 20:
        return ONES[n]
    if n < 100:
        return TENS[n // 10] + ("" if n % 10 == 0 else "-" + ONES[n % 10])
    if n < 1000:
        rest = n % 100
        return ONES[n // 100] + " hundred" + ("" if rest == 0 else " and " + words(rest))
    th, rest = divmod(n, 1000)
    return words(th) + " thousand" + ("" if rest == 0 else (" and " if rest < 100 else " ") + words(rest))


LEAD = ["", "", "", "Later that day, ", "Shortly after, ", "By noon, ", "In the afternoon session, ",
        "Before the shift ended, ", "On the second round, ", "At the morning count, ", "Meanwhile, ",
        "When the clerks checked again, ", "Just before closing, ", "During the stocktake, "]
SCENE = ["The north depot filed its report.", "A courier brought the evening summary.",
         "The clerks compared their sheets.", "Rain held up the second delivery.",
         "The supervisor read the figures aloud.", "Two crates arrived late.",
         "The night shift handed over its notes.", "A new ledger page was started."]
CONDS = ["the van had arrived on time", "the second crate had been opened", "the order had gone through",
         "the supplier had kept its promise", "the weather had held", "the clerk had not been ill"]
SEASONS = ["back in the spring", "last winter", "two seasons ago", "at the start of the year",
           "before the move", "in the old ledger"]


class Gen:
    def __init__(self, rng: random.Random, n_counters: int):
        self.rng = rng
        names: list[str] = []
        while len(names) < n_counters:
            nm = f"{word(rng)}{rng.randint(10, 99)}"
            if nm not in names:
                names.append(nm)
        self.names = names
        self.state: dict[str, int] = {}
        self.history: dict[str, list[int]] = {n: [] for n in names}
        self.ever: set[str] = set()
        self.ops: list[list] = []          # true operations of the current batch

    # ------------------------------------------------------------- helpers
    def num(self, n: int, p_words: float = 0.4) -> str:
        if n in (12, 24, 36, 20, 40) and self.rng.random() < 0.5:
            return {12: "a dozen", 24: "two dozen", 36: "three dozen", 20: "a score", 40: "two score"}[n]
        if self.rng.random() < p_words and abs(n) < 10000:
            return words(n)
        return str(n)

    def lookalike(self, name: str) -> str:
        base, d = name[:-2], name[-2:]
        for cand in (base + d[::-1], base + str((int(d) + 1) % 90 + 10), base[:-1] + d):
            if cand not in self.names and cand != name and len(cand) > 3:
                return cand
        return base + "x" + d

    def apply(self, nm: str, op: str, arg, sentence_no: int):
        old = self.state.get(nm)
        if op == "set":
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
        elif op == "correct":
            self.state[nm] = arg
        if old is not None:
            self.history[nm].append(old)
        self.ever.add(nm)
        self.ops.append([nm, op, arg, self.state.get(nm), sentence_no])

    # ------------------------------------------------------------- one paragraph
    def paragraph(self) -> str:
        r = self.rng
        k = r.choice([2, 2, 3])
        cs = r.sample(self.names, k)
        sent: list[str] = []
        intro_order: list[str] = []
        audit_split = None              # index in intro_order before which the audit happened
        last_subject = None
        last_set: dict[str, int] = {}   # counter -> value of a set with nothing done since
        pending_plan = None

        def ref(c: str) -> str:
            """An unambiguous reference to an already introduced counter."""
            opts = [c]
            if last_subject == c:
                opts += ["it", "it", "the same counter"]
            if len(intro_order) == 2 and len(cs) == 2 and c in intro_order:
                opts.append("the former" if intro_order.index(c) == 0 else "the latter")
            if c in intro_order and len(intro_order) >= 2:
                opts.append(["the first", "the second", "the third"][intro_order.index(c)] + " of these")
            if audit_split is not None and c in intro_order:
                if audit_split == 1 and intro_order.index(c) == 0:
                    opts.append("the counter named before the audit")
                if audit_split == len(intro_order) - 1 == 1 and intro_order.index(c) == 1:
                    opts.append("the one named after the audit")
            return r.choice(opts)

        def cap(s: str) -> str:
            first = s.split(" ", 1)[0].rstrip(",.;:")
            if first in self.names or first[:-2].isalpha() and first[-2:].isdigit():
                return s                # counter names keep their exact spelling
            return s[0].upper() + s[1:]

        def op_sentence(c: str, first: bool) -> str | None:
            nonlocal last_subject
            exists = c in self.state
            rf = c if first else ref(c)
            lead = r.choice(LEAD)
            if not exists:
                v = r.randint(-300, 600)
                t = r.choice(["{r} was opened at {n}", "a new sheet was started for {r}, at {n}",
                              "{r} came back onto the books at {n}", "the clerks opened {r} with {n}",
                              "{r} was entered fresh, holding {n}"])
                s = t.format(r=rf, n=self.num(v))
                self.apply(c, "set", v, len(sent))
                last_set[c] = v
                last_subject = c
                return cap(lead + s) + "."
            v = self.state[c]
            choices = ["set", "add", "add", "sub", "sub", "del", "double", "third", "from", "plan"]
            if abs(v) > 3000:
                choices = ["set", "sub", "add", "del"]
            op = r.choice(choices)
            if op == "third" and (v == 0 or v % 3):
                op = "add"
            others = [o for o in intro_order if o != c and self.state.get(o, 0) > 0]
            if op == "from" and not others:
                op = "sub"
            if op == "plan" and pending_plan is not None:
                op = "add"
            if op == "set":
                n = r.randint(-300, 600)
                t = r.choice(["{r} was set to {n}", "{r} was reset to {n}", "a recount put {r} at {n}",
                              "the clerk recorded {r} at exactly {n}", "{r} now stands at {n}, by fresh count",
                              "{r} was fixed at {n}", "{r} was brought to {n} by the new count",
                              "{r} was counted again and came to {n}", "the sheet for {r} reads {n} now",
                              "{r}: {n}, according to the new tally", "whatever it held before, {r} holds {n} now",
                              "{r} was simply made {n}"])
                s = t.format(r=rf, n=self.num(n))
                self.apply(c, "set", n, len(sent))
                last_set[c] = n
            elif op in ("add", "sub"):
                n = r.randint(1, 120)
                if op == "add":
                    t = r.choice(["{r} gained {n}", "{r} went up by {n}", "{n} more were added to {r}",
                                  "{r} rose by {n}", "{r} received another {n}", "{r} picked up {n}",
                                  "the tally for {r} went up, by {n} to be exact",
                                  "{r} ended the round {n} higher", "an extra {n} went into {r}",
                                  "{r} now holds {n} more than before", "{r} came out {n} up on the morning",
                                  "{r} took in {n}, not the {n2} first reported"])
                else:
                    t = r.choice(["{r} lost {n}", "{r} dropped by {n}", "{n} were taken from {r}",
                                  "{r} fell by {n}", "{r} gave up {n}", "{r} was short {n} after the count",
                                  "the tally for {r} went down, by {n} to be exact",
                                  "{r} ended the round {n} lower", "{n} went out of {r}",
                                  "{r} now holds {n} fewer than before", "{r} is {n} lighter than it was",
                                  "{r} paid out {n}, not the {n2} first reported",
                                  "as the clerk said it would, {r} shed {n}"])
                n2 = n + r.randint(1, 40)
                s = t.format(r=rf, n=self.num(n), n2=self.num(n2))
                self.apply(c, "add", n if op == "add" else -n, len(sent))
                last_set.pop(c, None)
            elif op == "del":
                t = r.choice(["{r} was closed and removed from the ledger", "{r} was struck off",
                              "the books no longer carry {r}", "{r} was retired for good",
                              "{r} was taken off the ledger", "{r} is gone from the books",
                              "{r} was wound up", "{r} will not be counted any more"])
                s = t.format(r=rf)
                self.apply(c, "del", None, len(sent))
                last_set.pop(c, None)
            elif op == "double":
                t = r.choice(["{r} doubled", "{r} was doubled", "{r} grew to twice its size",
                              "the count for {r} doubled overnight", "{r} ended with twice what it had",
                              "the amount in {r} was matched again, doubling it"])
                s = t.format(r=rf)
                self.apply(c, "double", None, len(sent))
                last_set.pop(c, None)
            elif op == "third":
                t = r.choice(["{r} lost a third of its value", "a third of {r} was written off",
                              "{r} shrank by exactly a third", "{r} kept only two thirds of its value",
                              "one part in three of {r} was paid away"])
                s = t.format(r=rf)
                self.apply(c, "third", None, len(sent))
                last_set.pop(c, None)
            elif op == "from":
                o = r.choice(others)
                t = r.choice(["{r} gained as many as {o} held at that point",
                              "{r} was topped up by an amount equal to what {o} held then",
                              "{r} received exactly what {o} stood at in that moment",
                              "{r} grew by the full amount then held in {o}"])
                ro = ref(o)
                s = t.format(r=rf, o=o if ro in ("it", "the same counter") else ro)
                self.apply(c, "from", o, len(sent))
                last_set.pop(c, None)
                last_set.pop(o, None)       # a later correction of o would make this ambiguous
                last_subject = None         # two counters named: no "it" next
                return cap(lead + s) + "."
            else:  # a plan, resolved by a later sentence
                n = r.randint(1, 90)
                kind = r.choice(["add", "sub", "set"])
                if kind == "set":
                    n = r.randint(-200, 500)
                    t = "there was talk of setting {r} to {n}"
                elif kind == "add":
                    t = "plans were made to add {n} to {r}"
                else:
                    t = "a proposal was made to take {n} from {r}"
                s = t.format(r=rf, n=self.num(n))
                return_plan = (c, kind, n, r.random() < 0.5)
                last_subject = c
                return ("PLAN", cap(lead + s) + ".", return_plan)
            last_subject = None if op == "del" else c
            return cap(lead + s) + "."

        def distractor(c: str) -> str:
            nonlocal last_subject
            rf = ref(c) if c in intro_order else c
            n = r.randint(1, 400)
            # recorded (state unchanged) so replay_state_check.py can recognise an applied distractor
            self.ops.append([c, "distractor", n, self.state.get(c), len(sent)])
            kind = r.choice(["hyp", "neg", "old", "look", "scene", "rumour", "rumour"])
            if kind == "hyp":
                s = r.choice(["If {cond}, {r} would have gained {n}",
                              "If {cond}, {r} would now stand at {n}",
                              "If {cond}, {n} would have been taken from {r}"]).format(
                    cond=r.choice(CONDS), r=rf, n=self.num(n))
            elif kind == "neg":
                s = r.choice(["{R} did not lose the {n} that everyone feared",
                              "Nobody added {n} to {r}, despite the rumour",
                              "{R} was not set to {n}, whatever the memo said",
                              "No one took {n} from {r} that day"]).format(r=rf, R=cap(rf), n=self.num(n))
            elif kind == "rumour":
                s = r.choice(["A rumour had {r} gaining {n}, but it was false",
                              "The memo claiming {r} lost {n} turned out to be about another depot",
                              "Someone pencilled {n} next to {r}, then rubbed it out unread",
                              "{R} gaining {n} was only a forecast"]).format(r=rf, R=cap(rf), n=self.num(n))
            elif kind == "old":
                s = r.choice(["{R} stood at {n} {season}, people still remember",
                              "Someone recalled that {r} had held {n} {season}"]).format(
                    r=c, R=c, n=self.num(n), season=r.choice(SEASONS))
            elif kind == "look":
                lk = self.lookalike(c)
                s = r.choice(["The old {lk} sheet, which is not part of this ledger, gained {n}",
                              "{lk}, a name on a supplier list and not a counter here, was set to {n}"]).format(
                    lk=lk, n=self.num(n))
                last_subject = None
                return cap(s) + "."
            else:
                last_subject = None
                return r.choice(SCENE)
            last_subject = None         # "it" is used only right after a real operation sentence
            return cap(s) + "."

        # --- intros: each counter is named once with a real operation; maybe an audit between
        for i, c in enumerate(cs):
            if i == 1 and r.random() < 0.25:
                sent.append(r.choice(["Then came the audit.", "The audit followed.",
                                      "At that point the auditors arrived."]))
                audit_split = 1
                last_subject = None
            intro_order.append(c)
            out = op_sentence(c, first=True)
            if isinstance(out, tuple):
                pending_plan = out[2]
                sent.append(out[1])
            elif out:
                sent.append(out)
        # --- follow-ups
        for _ in range(r.randint(2, 5)):
            x = r.random()
            live = [c for c in intro_order if c in self.state]
            if pending_plan and r.random() < 0.6:
                c, kind, n, confirmed = pending_plan
                pending_plan = None
                if confirmed and c in self.state:
                    sent.append(r.choice(["The planned change to {c} went through that afternoon.",
                                          "The plan for {c} was carried out before the count closed.",
                                          "What was planned for {c} was done the same day."]).format(c=c))
                    if kind == "set":
                        self.apply(c, "set", n, len(sent) - 1)
                        last_set.pop(c, None)   # corrections refer only to plainly stated figures
                    else:
                        self.apply(c, "add", n if kind == "add" else -n, len(sent) - 1)
                        last_set.pop(c, None)
                else:
                    sent.append(r.choice(["The plan for {c} was dropped before anything changed.",
                                          "Nothing came of the plan for {c}.",
                                          "The idea for {c} was abandoned the same hour."]).format(c=c))
                last_subject = None
                continue
            cands = [c for c in last_set if c in self.state and self.state[c] == last_set[c]]
            if cands and x < 0.12:
                c = r.choice(cands)
                old = last_set[c]
                new = old + r.choice([-1, 1]) * r.randint(1, 60)
                sent.append(r.choice([
                    "On review, the figure given for {c} above was a typo: it should have read {new}, not {old}.",
                    "Correction: {c} was recorded above as {old}, but the true figure was {new}.",
                    "The earlier figure for {c} was a typo; it was {new}, not {old}."]).format(
                    c=c, new=self.num(new, 0.2), old=self.num(old, 0.2)))
                self.apply(c, "correct", new, len(sent) - 1)
                last_set[c] = new
                last_subject = None
                continue
            if x < 0.45 or not live:
                sent.append(distractor(r.choice(intro_order)))
                continue
            c = r.choice(live)
            out = op_sentence(c, first=False)
            if isinstance(out, tuple):
                if pending_plan is None:
                    pending_plan = out[2]
                    sent.append(out[1])
            elif out:
                sent.append(out)
        if pending_plan:
            c, kind, n, confirmed = pending_plan
            sent.append(f"The plan for {c} was dropped before anything changed.")
        return " ".join(sent)


def build(out: Path, name: str, target_tokens: int, seed: int, batch_tokens: int, n_get: int,
          n_counters: int, mode: str, cpt: float, count_exact, n_batches: int | None = None) -> dict:
    rng = random.Random(f"prose-{seed}-{target_tokens}-{batch_tokens}-{n_counters}")
    g = Gen(rng, n_counters)
    count = count_exact or (lambda t: int(len(t) / cpt))
    batches, refs, tokens = [], [], 0
    while True:
        g.ops = []
        paras, t = [], 0
        while t < batch_tokens:
            p = g.paragraph()
            paras.append(p)
            t += count(p) + 1
        text = "\n\n".join(paras)
        tt = count(text)
        batches.append(text)
        refs.append({"state": dict(g.state), "ops": g.ops})
        tokens += tt
        if n_batches is not None:
            if len(batches) >= n_batches:
                break
        elif tokens + tt / 2 >= target_tokens:
            break
    gone = sorted(n for n in g.ever if n not in g.state)
    alive = sorted(g.state)
    n_gone = min(len(gone), max(1, n_get // 8)) if gone else 0
    queried = rng.sample(gone, n_gone) + rng.sample(alive, min(n_get - n_gone, len(alive)))
    rng.shuffle(queried)
    exp = {n: g.state.get(n) for n in queried}
    total = len(batches) + 1
    items = [{"kind": "UPDATE", "total": total, "text": b} for b in batches]
    items.append({"kind": "QUERY", "total": total,
                  "text": "The auditors ask for the current value of each counter below (null if it has "
                          "been removed). Answer in /app/answers.json:\n"
                          + "\n".join(f"QUERY {n}" for n in queried),
                  "last": "This was the last item. Write /app/answers.json now."})
    spec = {"kind": "ledger", "mode": mode, "expected": exp,
            "history": {n: g.history[n] for n in queried}, "all_names": sorted(g.ever),
            "n_items": total}
    bt = tokens // len(batches)
    instr = INSTRUCTION.format(
        total=total, n_batches=len(batches), batch_tokens=bt, n_get=len(queried),
        stream_tokens=tokens, n_counters=len(g.ever), example=g.names[0],
        storage_rule=STORAGE_MEMORY.replace("values, keys, SET lines", "counter names, values, report text")
        if mode == "memory" else STORAGE_NOTES)
    d = out / name
    write_task(d, items=items, spec=spec, answers_oracle=exp, instruction=instr, mode=mode,
               end_text="STREAM END: no more items. Answer the final query in /app/answers.json, then submit.",
               metadata={"seed": seed, "target_tokens": target_tokens, "stream_tokens": tokens,
                         "token_counter": "tokenizer" if count_exact else f"chars/{cpt}",
                         "batch_tokens": bt, "n_get": len(queried), "n_counters": len(g.ever),
                         "n_deleted_queried": n_gone},
               description=f"prose ledger, {mode}, ~{tokens} tokens, seed {seed}", kind="prose")
    (d / "tests" / "reference.json").write_text(json.dumps({"after_batch": refs}))
    return {"name": name, "mode": mode, "n_batches": len(batches), "items": total,
            "stream_tokens": tokens, "counters": len(g.ever), "deleted_queried": n_gone}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out")
    ap.add_argument("--tokens", type=int, nargs="+", default=[60000, 120000, 480000])
    ap.add_argument("--mode", choices=["memory", "notes"], default="memory")
    ap.add_argument("--seeds", type=int, nargs="+", default=[0])
    ap.add_argument("--batch-tokens", type=int, default=6400)
    ap.add_argument("--n-get", type=int, default=24)
    ap.add_argument("--n-counters", type=int, default=160)
    ap.add_argument("--chars-per-token", type=float, default=3.9)
    ap.add_argument("--exact-tokens", action="store_true",
                    help=f"count with the served model's tokenizer ({DEFAULT_TOKENIZER}) via `tokenizers`")
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    count_exact = None
    if a.exact_tokens:
        from tokenizers import Tokenizer
        tok = Tokenizer.from_file(DEFAULT_TOKENIZER)
        count_exact = lambda t: len(tok.encode(t).ids)  # noqa: E731
    made = []
    if a.smoke:
        made.append(build(out, f"prose-{a.mode}-smoke", 0, 0, 900, 3, 6, a.mode, a.chars_per_token,
                          count_exact, n_batches=2))
    else:
        for n in a.tokens:
            for s in a.seeds:
                made.append(build(out, f"prose-{a.mode}-t{n // 1000}k-s{s}", n, s, a.batch_tokens,
                                  a.n_get, a.n_counters, a.mode, a.chars_per_token, count_exact))
    for m in made:
        print(json.dumps(m))


if __name__ == "__main__":
    main()
