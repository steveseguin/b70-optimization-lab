#!/usr/bin/env python3
"""make_needle_long.py <tokhelper> <model.gguf> <needle.tokens> <target tokens> <out.tokens> <notes files... | @list>

A longer needle prompt from a shorter one: the other lab notes go in before the question (the two hidden notes stay
where they were, so they end up further back). Notes files that mention the hidden notes' values are left out. Each
file is tokenized on its own (llama.cpp's tokenizer, tokhelper as the server runs it) and goes in whole, between
blank lines, until the prompt has <target tokens>. The question is the text from its last line on."""
import subprocess, sys

QUESTION = b"Two notes for the reader were hidden in the document above."
BANNED = (b"7351", b"Juniper", b"QX-4829", b"vault code", b"Vault code", b"meeting room")


def main():
    th, gguf, src, target, out = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5]
    files = sys.argv[6:]
    if len(files) == 1 and files[0].startswith("@"):  # @list: one path per line
        files = [l.strip() for l in open(files[0][1:]) if l.strip()]
    p = subprocess.Popen([th, gguf], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    p.stdin.write(b"V\n"); p.stdin.flush()
    n = int(p.stdout.readline().split()[1])
    pieces = [bytes.fromhex(p.stdout.readline().strip().decode()) for _ in range(n)]

    def enc(b):
        p.stdin.write(b"T " + b.hex().encode() + b"\n"); p.stdin.flush()
        r = p.stdout.readline().split()
        if not r or r[0] != b"I":
            raise RuntimeError("tokenizer failed")
        return [int(x) for x in r[1:]]

    tok = [int(x) for x in open(src).read().split()]
    # the question's first token: walk back from the end until the text holds the question's start
    q = None
    tail = b""
    for i in range(len(tok) - 1, max(0, len(tok) - 400), -1):
        tail = (pieces[tok[i]] if tok[i] < len(pieces) else b"") + tail
        if QUESTION in tail:
            # the first token from which the text still starts at or before the question's newlines
            j = i
            while j < len(tok) and QUESTION in b"".join(pieces[t] for t in tok[j + 1:]):
                j += 1
            q = j
            break
    if q is None:
        raise SystemExit("question not found")
    head, qt = tok[:q], tok[q:]
    sys.stderr.write(f"body {len(head)} tokens, question {len(qt)} tokens: {b''.join(pieces[t] for t in qt)[:80]!r}\n")
    extra, used = [], []
    room = target - len(tok)
    for f in files:
        b = open(f, "rb").read()
        if any(x in b for x in BANNED) or not b.strip():
            continue
        t = enc(b"\n\n" + b.strip() + b"\n")
        if len(extra) + len(t) > room:
            continue
        extra += t
        used.append(f)
        if room - len(extra) < 2000:
            break
    allt = head + extra + qt
    with open(out, "w") as o:
        o.write(" ".join(map(str, allt)) + "\n")
    sys.stderr.write(f"{len(allt)} tokens ({len(extra)} added from {len(used)} files) -> {out}\n")
    p.stdin.close(); p.wait()


if __name__ == "__main__":
    main()
