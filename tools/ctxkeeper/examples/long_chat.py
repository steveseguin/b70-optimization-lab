#!/usr/bin/env python3
"""long_chat.py: a conversation several times longer than the model's live window, to see what survives.

It says three things at the start (a codename, a starting budget and a standing rule), then sends reports until the
history is several times the window, changing the budget a few times on the way, and at the end asks about all of
it. Like any ordinary client it sends its whole history every time; through ctxkeeper the proxy decides what the
model sees, and the answers show whether what was said long ago is still known.

  python3 long_chat.py --base-url http://127.0.0.1:18200/v1                    # through ctxkeeper
  python3 long_chat.py --base-url http://127.0.0.1:18200/v1 --tokens 150000 \\
      --extra-body '{"chat_template_kwargs": {"enable_thinking": false}}'       # Qwen on vLLM, quick replies

Standard library only. Prints each answer and a score; exit status 0 when every check passes.
"""
import argparse
import json
import random
import re
import sys
import time
import urllib.request

WORDS = ("amber", "falcon", "cedar", "harbor", "violet", "comet", "granite", "willow", "summit", "orchid", "ember",
         "lagoon", "quartz", "meadow", "cobalt", "juniper", "tundra", "saffron", "beacon", "canyon")
TEAMS = ("north yard", "river crew", "night shift", "east depot", "the survey team", "dock four", "the tool room",
         "line two", "the paint shop", "west gate")
THINGS = ("pallets", "cable drums", "pump seals", "valve kits", "crates of fittings", "spare belts", "filter packs",
          "sensor boards", "steel plates", "drill bits")
RULE_WORD = "ROGER"


def post(url: str, body: dict, timeout: float) -> dict:
    req = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def report(rng: random.Random, chars: int) -> str:
    """A filler report full of names and numbers (none of them about the budget)."""
    out: list[str] = []
    while sum(len(s) + 1 for s in out) < chars:
        out.append(f"{rng.choice(TEAMS).capitalize()} moved {rng.randint(3, 900)} {rng.choice(THINGS)} to bay "
                   f"{rng.randint(1, 60)} and logged {rng.randint(1, 80)} hours; {rng.randint(0, 40)} items were "
                   f"set aside for checking and {rng.randint(0, 12)} were sent back.")
    return " ".join(out)


def digits(text: str) -> str:
    return re.sub(r"(?<=\d)[,\s](?=\d{3})", "", text)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-url", default="http://127.0.0.1:18200/v1", help="ctxkeeper (or any server) with /v1")
    ap.add_argument("--model", help="model name (default: the first one /v1/models lists)")
    ap.add_argument("--tokens", type=int, default=100000, help="about how long the conversation grows (tokens)")
    ap.add_argument("--report-tokens", type=int, default=2000, help="about how long each report is (tokens)")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--max-tokens", type=int, default=2048, help="max_tokens of each request")
    ap.add_argument("--extra-body", default="{}", help="JSON merged into every request (e.g. chat_template_kwargs)")
    ap.add_argument("--timeout", type=float, default=900)
    a = ap.parse_args()
    base = a.base_url.rstrip("/")
    extra = json.loads(a.extra_body)
    model = a.model
    if not model:
        with urllib.request.urlopen(base + "/models", timeout=60) as r:
            model = json.loads(r.read())["data"][0]["id"]

    rng = random.Random(a.seed)
    codename = f"{rng.choice(WORDS)} {rng.choice(WORDS)}".upper()
    budgets = [rng.randint(1000, 9000)]
    reports = max(3, a.tokens // a.report_tokens)
    changes = {int(reports * f) for f in (0.3, 0.6, 0.85)}
    messages = [
        {"role": "system", "content": "You are a careful assistant helping with a long review session."},
        {"role": "user", "content": (
            "We are starting a long review session. Keep these for the whole session:\n"
            f"1. The project codename is {codename}.\n"
            f"2. The project budget starts at {budgets[0]:,} credits. It may change later; I will say so.\n"
            f"3. Standing rule: every answer of yours that states the project budget must end with the word {RULE_WORD}.\n"
            "Reply with just: ready")},
    ]
    t0 = time.time()

    def ask(text: str) -> str:
        messages.append({"role": "user", "content": text})
        body = {"model": model, "messages": messages, "max_tokens": a.max_tokens, "temperature": 0, **extra}
        reply = post(base + "/chat/completions", body, a.timeout)["choices"][0]["message"]
        content = reply.get("content") or ""
        messages.append({"role": "assistant", "content": content})
        return content

    first = post(base + "/chat/completions", {"model": model, "messages": messages, "max_tokens": a.max_tokens,
                                              "temperature": 0, **extra}, a.timeout)["choices"][0]["message"]
    messages.append({"role": "assistant", "content": first.get("content") or ""})
    for i in range(1, reports + 1):
        text = report(rng, a.report_tokens * 4)
        if i in changes:
            budgets.append(rng.randint(1000, 9000))
            text = f"BUDGET UPDATE: the project budget is now {budgets[-1]:,} credits.\n\n" + text
        ask(f"Report {i} of {reports}. Read it and reply with just: noted\n\n{text}")
        size = sum(len(m["content"]) for m in messages) // 4
        print(f"report {i}/{reports}: history about {size:,} tokens, {time.time() - t0:.0f} s", flush=True)

    checks = []
    answer = ask("Question: what is the project codename? Answer in a few words.")
    checks.append(("codename said at the start", codename.lower() in answer.lower(), answer))
    answer = ask("Question: what is the project budget now, in credits?")
    checks.append(("current budget", str(budgets[-1]) in digits(answer), answer))
    checks.append(("standing rule kept (ends with " + RULE_WORD + ")",
                   answer.strip().rstrip(".!").upper().endswith(RULE_WORD), answer))
    answer = ask("Question: what was the project budget at the very start of this session, in credits?")
    checks.append(("starting budget", str(budgets[0]) in digits(answer), answer))

    print()
    for name, ok, said in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {' '.join(said.split())[:200]}")
    passed = sum(ok for _, ok, _ in checks)
    print(f"\n{passed}/{len(checks)} checks passed; history about "
          f"{sum(len(m['content']) for m in messages) // 4:,} tokens in {time.time() - t0:.0f} s")
    root = base[:-3] if base.endswith("/v1") else base
    try:
        with urllib.request.urlopen(root + "/ctxkeeper/status", timeout=10) as r:
            for key, s in json.loads(r.read()).items():
                print(f"ctxkeeper: {s.get('cuts')} cuts, {s.get('cut')} messages archived, {s.get('recalls')} "
                      f"recalls, {s.get('rules_put_back', 0)} rules put back")
    except Exception:
        pass
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
