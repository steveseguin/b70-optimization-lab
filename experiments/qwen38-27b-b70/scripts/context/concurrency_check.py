#!/usr/bin/env python3
"""concurrency_check.py: does a reply change, or turn to garbage, when another request runs beside it?

Campaign 21 (2026-10-16) found that on the research server with --seqs 2 a main reply written while a background notes
call ran beside it came back as 2,048 tokens of "!!!!". This sends a few deterministic chat requests (temperature 0,
thinking off) alone, then in overlapping pairs (the second one starting while the first is generating, so one
request's prompt is read while the other decodes, and both decode together), and compares every reply with its
solo reply. B and D share one long prompt up to the question (both served from the prefix cache), as a notes call
and the agent's call do.

  python3 concurrency_check.py --base-url http://127.0.0.1:18196/v1 [--rounds 3] [--json out.json]

Exit status 0 when every overlapped reply equals its solo reply; 1 when one differs; 2 when one is garbage.
Standard library only.
"""
import argparse
import json
import random
import re
import sys
import threading
import time
import urllib.request

TEAMS = ("north yard", "river crew", "night shift", "east depot", "survey team", "dock four", "tool room", "line two")
THINGS = ("pallets", "cable drums", "pump seals", "valve kits", "crates", "spare belts", "filter packs", "drill bits")


def records(seed: int, n: int) -> str:
    rng = random.Random(seed)
    return "\n".join(f"{i + 1}. {rng.choice(TEAMS)} moved {rng.randint(2, 900)} {rng.choice(THINGS)} to bay "
                     f"{rng.randint(1, 60)} at {rng.randint(0, 23):02d}:{rng.randint(0, 59):02d}." for i in range(n))


def prompt(seed: int, n: int, ask: str) -> list[dict]:
    return [{"role": "system", "content": "You are a careful logistics clerk. Answer from the records only."},
            {"role": "user", "content": f"Records:\n{records(seed, n)}\n\n{ask}"}]


def post(url: str, body: dict, timeout: float) -> dict:
    req = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def garbage(text: str) -> bool:
    """A run of one repeated character (the "!!!!" seen in campaign 21), or no letters at all."""
    return bool(re.search(r"(.)\1{40,}", text)) or not re.search(r"[A-Za-z]{3}", text or "")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-url", default="http://127.0.0.1:18196/v1")
    ap.add_argument("--model", default="")
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--max-tokens", type=int, default=400)
    ap.add_argument("--timeout", type=float, default=600)
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    model = a.model or post_get(a.base_url + "/models")
    url = a.base_url + "/chat/completions"
    # A: a short prompt with a long reply; B: a long prompt (its reading overlaps A's writing) with a medium reply
    cases = {
        "A": prompt(1, 60, "List every move by the night shift, one line each, in record order, then give their total."),
        "B": prompt(2, 700, "Which team moved the most items in all? Show the per-team totals first."),
        "C": prompt(3, 200, "Write a short shift report: the three largest moves and anything moved to bay 7."),
        # D shares B's whole record list (B's cached prompt) and differs only in the question: the shape of a
        # ctxkeeper notes call beside the agent's own call (campaign 23's smoke test: garbage there, none in A-C)
        "D": prompt(2, 700, "List the five largest single moves with their record numbers."),
    }

    def ask(name: str, out: dict, key: str) -> None:
        body = {"model": model, "messages": cases[name], "max_tokens": a.max_tokens, "temperature": 0,
                "chat_template_kwargs": {"enable_thinking": False}}
        t0 = time.monotonic()
        try:
            r = post(url, body, a.timeout)
            c = r["choices"][0]
            out[key] = {"text": c["message"].get("content") or "", "finish": c.get("finish_reason"),
                        "written": (r.get("usage") or {}).get("completion_tokens"), "s": round(time.monotonic() - t0, 2)}
        except Exception as exc:                                    # noqa: BLE001 - reported, not raised
            out[key] = {"text": "", "finish": f"error {type(exc).__name__}: {exc}", "written": 0, "s": 0}

    solo: dict = {}
    for name in cases:
        ask(name, solo, name)
        print(f"solo {name}: {solo[name]['written']} tokens, {solo[name]['finish']}, {solo[name]['s']} s"
              + ("  GARBAGE" if garbage(solo[name]["text"]) else ""), flush=True)
    rows, worst = [], 0
    pairs = [("A", "B", 1.0), ("B", "A", 0.3), ("A", "C", 1.0), ("C", "B", 0.5), ("B", "D", 0.5), ("D", "B", 1.0)]
    for rnd in range(a.rounds):
        for first, second, delay in pairs:
            got: dict = {}
            t1 = threading.Thread(target=ask, args=(first, got, "first"))
            t2 = threading.Thread(target=ask, args=(second, got, "second"))
            t1.start(); time.sleep(delay); t2.start(); t1.join(); t2.join()
            for key, name in (("first", first), ("second", second)):
                r = got[key]
                bad = garbage(r["text"])
                same = r["text"] == solo[name]["text"]
                worst = max(worst, 2 if bad else 0 if same else 1)
                rows.append({"round": rnd, "pair": f"{first}+{second}", "request": name, "same_as_solo": same,
                             "garbage": bad, "finish": r["finish"], "written": r["written"], "s": r["s"],
                             "head": r["text"][:120]})
                print(f"round {rnd} {first}+{second} ({delay} s apart): {name} "
                      + ("GARBAGE" if bad else "same as solo" if same else "DIFFERENT")
                      + f", {r['written']} tokens, {r['finish']}, {r['s']} s", flush=True)
    n_bad = sum(r["garbage"] for r in rows)
    n_diff = sum(not r["same_as_solo"] for r in rows)
    print(f"\n{len(rows)} overlapped replies: {n_bad} garbage, {n_diff} different from solo")
    if a.json:
        json.dump({"solo": solo, "rows": rows}, open(a.json, "w"), indent=1)
    return worst


def post_get(url: str) -> str:
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read())["data"][0]["id"]


if __name__ == "__main__":
    sys.exit(main())
