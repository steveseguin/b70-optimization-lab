# Qwen3.8 Flash-Next FP8 A73 proposal: exact-4K rows on the deterministic graph line

Date: 2026-09-03 (drafted overnight; not frozen; needs the user's sign-off on
the authority policy before a packet is generated)

## Why

A66 was logit-exact at depth 2048 in eager mode and A70/A71 agree byte for
byte at 2K on the graph line, but the served capacity of every deterministic
arm is 2304 tokens. The certified-lossless context of this line is therefore
still below 4K. The 4352-token PLE-only base exists (A9-A25 lineage) and the
exact-depth fixture carries a 4096-token case, so a 4K arm is a packet
change, not new tooling.

## What changes against A72

- Base: the PLE-only 4352 launcher lineage (`MAX_MODEL_LEN=4352`,
  `KV_CACHE_MEMORY_BYTES=201326592`) instead of the 2304 one; the 2304
  literals in the launcher rules, supervisor identity check (`max_model_len`,
  `kv_cache_memory_bytes`), and client (`--max-model-len`, `.max_model_len`,
  identity receipt line, summary) all move to 4352/201326592.
- Client depth rows: `--depth 4096 --context-capacity 4352`, usage
  `(4096, 128, 4224)`, two rows.
- Head `2169dbfe...` (V2 runner receipt), `VLLM_XPU_MKLDNN_DETERMINISTIC=1`,
  public oneCCL twoshots, tuned M1 W13-N32 map, full decode graph: unchanged.

## The open policy question

The native-line 4K authority (`1d833e5f...`, 2026-08-28) came from a server
class now known to be logit-jittery. The deterministic line will produce a
stable 4K output that may or may not match it (at 2K it did not, at a
near-tie token). Options: (a) first run with the 4K pin removed and record
the deterministic output as a candidate authority, then a fresh-server
repeat with that pin (the A70/A71 pattern); (b) pin the native authority and
accept a failed-closed first attempt as the record. Option (a) preserves the
protected record and gives a promotable pair in two attempts; it is what
this note proposes. The same question already stands for the 2K candidate
`afffd2110812...`.

## Cost

Two server loads (about 35 minutes each) plus the client; the 4K rows take
about five minutes each.
