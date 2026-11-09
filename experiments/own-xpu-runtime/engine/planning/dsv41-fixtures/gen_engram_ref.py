# Reference dump for the engram hash-chain + gather fixture.
# Semantics from official inference/engram.py (DeepSeek-V4.1-Flash-1017, MIT).
# Real layout parameters from config.json; synthetic token_map (tokenizer not
# needed for hash-chain semantics — compressed ids are just integers).
import json
import numpy as np
import torch
from sympy import isprime

OUT = "/tmp/engram_ref"

cfg = json.load(open("/home/steve/b70-optimization-lab/experiments/own-xpu-runtime/data/dsv41-reference/config.json"))
layer_ids = tuple(cfg["engram_layer_ids"])              # (1, 14)
max_n = cfg["engram_max_ngram_size"]                    # 4
n_heads = cfg["engram_n_heads"]                         # 8
vocab = cfg["engram_compressed_vocab_size"]             # 99092
env_vocab = cfg["engram_vocab_size"]                    # 16000000

def find_next_prime(start, seen):
    c = start + 1
    while not isprime(c) or c in seen:
        c += 1
    return c

seen = set()
primes = []
for _ in layer_ids:
    per_ngram = []
    for _ in range(max_n - 1):
        sizes, current = [], env_vocab - 1
        for _ in range(n_heads):
            current = find_next_prime(current, seen)
            seen.add(current)
            sizes.append(current)
        per_ngram.append(sizes)
    primes.append(per_ngram)
primes = np.array(primes, dtype=np.int64)               # [L, max_n-1, heads]
flat = primes.reshape(len(layer_ids), -1)               # [L, 24]
offsets = np.concatenate([np.zeros((len(layer_ids),1),dtype=np.int64), np.cumsum(flat,axis=1)[:,:-1]], axis=1)

# multipliers: np.random.default_rng(10007*layer), int64 in [0,bound)*2+1
max_long = np.iinfo(np.int64).max
bound = max(1, (max_long // vocab) // 2)
mults = []
for lid in layer_ids:
    g = np.random.default_rng(10007 * lid)
    mults.append(g.integers(0, bound, size=(max_n,), dtype=np.int64) * 2 + 1)
mults = np.stack(mults)                                 # [L, 4]

# synthetic token_map (fixture scope: hash chain needs integer ids only)
rng = np.random.default_rng(0xE641)
raw_vocab = cfg["vocab_size"]                           # 129280
token_map = rng.integers(0, vocab, size=raw_vocab).astype(np.int64)
pad_id = int(token_map[cfg["engram_pad_id"]])

# synthetic token stream with DEAD spans (image tokens) at fixed positions
L = 512
ids = rng.integers(0, raw_vocab, size=L).astype(np.int64)
mask = np.ones(L, dtype=bool)
mask[100:104] = False; mask[300:301] = False            # dead spans
DEAD = -1
comp = token_map[ids]
comp_masked = np.where(mask, comp, DEAD)

# hash chain (semantics from NgramHashState.forward)
hashes = np.zeros((L, len(layer_ids), (max_n-1)*n_heads), dtype=np.int64)
for li in range(len(layer_ids)):
    toks = np.full((L, max_n), pad_id, dtype=np.int64)
    for shift in range(max_n):
        src_idx = np.maximum(np.arange(L) - shift, 0)
        src = comp_masked[src_idx]
        blocked = (np.arange(L) < shift) | (src == DEAD)
        toks[:, shift] = np.where(blocked, pad_id, src)
    prods = toks * mults[li]                            # [L, 4] int64
    rolling = prods[:, 0]
    for i in range(1, max_n):
        rolling = np.bitwise_xor(rolling, prods[:, i])
        hashes[:, li, (i-1)*n_heads:i*n_heads] = (rolling[:, None] % primes[li, i-1])
hashes += offsets[None, :, :]

primes.tofile(f"{OUT}_primes.bin")
offsets.tofile(f"{OUT}_offsets.bin")
mults.tofile(f"{OUT}_mults.bin")
token_map.tofile(f"{OUT}_token_map.bin")
ids.tofile(f"{OUT}_ids.bin")
mask.astype(np.uint8).tofile(f"{OUT}_mask.bin")
hashes.tofile(f"{OUT}_hashes.bin")
np.array([pad_id], dtype=np.int64).tofile(f"{OUT}_pad.bin")
print("wrote", OUT, "layers", layer_ids, "primes[0][0][0]", primes[0,0,0], "pad", pad_id)
