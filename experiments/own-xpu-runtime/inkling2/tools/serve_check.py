#!/usr/bin/env python3
"""serve_check.py <serving ink_run> <card> <fresh ink_run> <out dir>: a served session against fresh runs.

The serving engine (INK_SERVE=1, with whatever INK_SPLIT / INK_DRAFT / INK_SPEC the environment gives it) gets:
  1. the 3,127-token prompt (prompts/long), 48 tokens;
  2. that conversation, its answer and a follow-up user turn, 48 tokens (read from the held state);
  3. a new conversation (prompts/haiku), 32 tokens (starts over);
  4. W: the haiku conversation saved to <out>/haiku.inkc;
  5. conversation 2 again with another follow-up (starts over: the long prompt is read again), 32 tokens;
  6. the haiku conversation, its answer and a follow-up, 32 tokens (INK_SERVE_CACHES=<out>: from the saved file).
Every answer must equal a fresh greedy run of its whole conversation by <fresh ink_run> (one engine, no guessing) on
the same card. Prints PASS / FAIL per request."""
import os, subprocess, sys

W = "/home/steve/inkling-work"
M = os.environ.get("INK_MODEL", "/mnt/fast-ai/llm-models/Inkling-2-Mini-GGUF/Inkling-2-Mini-UD-IQ4_XS.gguf")
OC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "on-card.sh")


def toks(path):
    return [int(x) for x in open(path).read().split()]


def turn(words):  # a user turn: <|message_user|><|content_text|> ... <|end_message|> (ids of a few plain words)
    return [200000, 200004] + words + [200010]


def main():
    sbin, card, fbin, out = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
    os.makedirs(out, exist_ok=True)
    env = dict(os.environ, INK_SERVE="1", INK_SERVE_CACHES=out)
    long_p, haiku = toks(f"{W}/prompts/long.tokens"), toks(f"{W}/prompts/haiku.tokens")
    f1 = turn([8017, 2891, 480, 306, 220, 18, 37190, 13])   # a few ordinary word ids
    f2 = turn([3206, 1617, 290, 4928, 306, 1001, 6496, 13])
    p = subprocess.Popen([OC, card, sbin, M, card, "/dev/null", "0", "8192"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=open(f"{out}/serve.err", "w"), env=env, text=True, bufsize=1)

    def read_until(prefix, rid=None):
        got = []
        while True:
            l = p.stdout.readline()
            if not l:
                raise SystemExit("server ended: see serve.err")
            l = l.strip()
            if l.startswith("@@T ") and (rid is None or l.split()[1] == rid):
                got += [int(x) for x in l.split()[2:]]
            if l.startswith("@@E"):
                raise SystemExit("server refused: " + l)
            if l.startswith(prefix) and (rid is None or l.split()[1] == rid):
                return got, l

    read_until("@@READY")
    convs, answers = [], []

    def g(rid, ids, n):
        p.stdin.write(f"G {rid} {n} 0 {len(ids)} {' '.join(map(str, ids))}\n")
        a, d = read_until("@@D", rid)
        convs.append(list(ids)); answers.append(a)
        print(f"  {rid}: {len(ids)} tokens, {d}", flush=True)
        return a

    a1 = g("r1", long_p, 48)
    c2 = long_p + a1 + f1
    a2 = g("r2", c2, 48)
    a3 = g("r3", haiku, 32)
    p.stdin.write(f"W w1 {out}/haiku.inkc\n")
    print("  " + read_until("@@W", "w1")[1], flush=True)
    g("r5", c2 + a2 + f2, 32)
    g("r6", haiku + a3 + f1, 32)
    p.stdin.write("Q\n"); p.stdin.close(); p.wait()
    rc = 0
    for i, (c, a) in enumerate(zip(convs, answers)):
        tf = f"{out}/fresh{i}.tokens"
        open(tf, "w").write(" ".join(map(str, c)) + "\n")
        r = subprocess.run([OC, card, fbin, M, card, tf, str(len(a))], capture_output=True, text=True,
                           env={k: v for k, v in os.environ.items() if not k.startswith(("INK_SPLIT", "INK_DRAFT", "INK_SPEC"))})
        fresh = [int(x) for x in r.stdout.replace("ids:", " ").split()]
        ok = fresh[:len(a)] == a and len(a) > 0
        rc |= not ok
        print(f"{'PASS' if ok else 'FAIL'} request {i + 1}: {len(a)} tokens after {len(c)}" + ("" if ok else f" (served {a[:8]}..., fresh {fresh[:8]}...)"),
              flush=True)
    sys.exit(rc)


if __name__ == "__main__":
    main()
