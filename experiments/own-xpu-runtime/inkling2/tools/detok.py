#!/usr/bin/env python3
"""detok.py <model.gguf> <ids...|file>: token ids -> text, from the GGUF's own vocabulary (GPT-2 byte-level BPE).
Special tokens (<|...|>) are printed as they are. For reading outputs only; the server tokenizes with llama.cpp."""
import struct, sys

def read_tokens(path):
    with open(path, 'rb') as f:
        b = f.read(64 << 20)
    p = 4
    def rd(fmt):
        nonlocal p
        v = struct.unpack_from(fmt, b, p); p += struct.calcsize(fmt); return v[0]
    def rs():
        nonlocal p
        n = rd('<Q'); s = b[p:p + n].decode('utf-8', 'replace'); p += n; return s
    sizes = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 4, 7: 1, 10: 8, 11: 8, 12: 8}
    def skip(t):
        nonlocal p
        if t == 8: rs()
        elif t == 9:
            at = rd('<I'); n = rd('<Q')
            for _ in range(n): skip(at)
        else: p += sizes[t]
    rd('<I'); rd('<Q'); nkv = rd('<Q')
    for _ in range(nkv):
        k = rs(); t = rd('<I')
        if k == 'tokenizer.ggml.tokens' and t == 9:
            at = rd('<I'); n = rd('<Q')
            return [rs() for _ in range(n)]
        skip(t)
    raise SystemExit('no tokenizer.ggml.tokens')

def byte_decoder():
    bs = list(range(ord('!'), ord('~') + 1)) + list(range(ord('¡'), ord('¬') + 1)) + list(range(ord('®'), ord('ÿ') + 1))
    cs = bs[:]
    n = 0
    for c in range(256):
        if c not in bs:
            bs.append(c); cs.append(256 + n); n += 1
    return {chr(c): b for b, c in zip(bs, cs)}

def main():
    toks = read_tokens(sys.argv[1])
    args = sys.argv[2:]
    if len(args) == 1 and not args[0].lstrip('-').isdigit():
        args = open(args[0]).read().replace('ids:', ' ').split()
    dec = byte_decoder()
    out = bytearray()
    for a in args:
        t = toks[int(a)]
        if t.startswith('<|') and t.endswith('|>'):
            out += t.encode()
        else:
            out += bytes(dec.get(ch, ord('?')) for ch in t)
    sys.stdout.write(out.decode('utf-8', 'replace') + '\n')

if __name__ == '__main__':
    main()
