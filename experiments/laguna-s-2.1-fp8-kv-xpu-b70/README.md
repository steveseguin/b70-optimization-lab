# Laguna S 2.1 INT4 — calibrated FP8 KV on Intel B70

This is the active Laguna optimization lane as of 2026-07-27. The prior BF16
KV record is sealed and remains reproducible under
`repro/laguna-s-2.1-int4-b70-102tps-20260726`; this directory does not modify
that source, launcher, oracle, or result.

## Contract

- target: `poolside/Laguna-S-2.1-INT4` at
  `4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb`;
- draft: `poolside/Laguna-S-2.1-DFlash-INT4` at
  `5e07c246915c86dc6920fead03d019989224f2ba`;
- target activations remain BF16;
- target KV is explicit E4M3 FP8 with the checkpoint's 96 calibrated scalar
  K/V scales (48 layers);
- the six DFlash cache layers also use FP8, but the draft checkpoint has no
  calibrated KV scheme, so their K/V scales are explicitly audited as 1.0;
- no runtime scale calculation (`--calculate-kv-scales`) is allowed;
- TP4 + EP4, concurrency 1, prefix caching off, async scheduling off;
- width 12 / DFlash depth 11 is inherited from the sealed final BF16 stack;
- exactness is evaluated against a new target-only FP8 teacher, never against
  the BF16 teacher.

Poolside documents FP8 KV as the checkpoint-native format. The explicit
`--kv-cache-dtype fp8` launch is intentional: it makes the experimental
identity fail closed while retaining the model's loaded calibrated scales.

## Promotion gates

Before any throughput result is promoted:

1. all four target ranks must emit the calibrated-scale audit PASS with digest
   `3e6df440976ab2ed5229e1a39179cbc99d573c615386f223eeabc9de5ea9ddc0`;
2. all four draft ranks must identify six unit-scale, uncalibrated cache layers;
3. the engine and metrics must resolve FP8 KV and Flash Attention, with no
   fallback;
4. candidate token IDs and decoded-text hashes must match a fresh target-only
   FP8 teacher for all 13 fixed prompts;
5. every prompt must be cold (`cached_tokens=0`);
6. the candidate must retain the audited 146-graph / 145-break topology on all
   four ranks;
7. a second fresh start must reproduce the FP8 output and throughput;
8. coding, structured-output, tool-use, repetition, and longer-context quality
   checks remain separate from bitwise within-FP8 exactness.

The old width-8/depth-7 matched test found FP8 4.132% slower at short context
while doubling KV capacity. Therefore capacity is already established, but a
decode-rate gain is not assumed.

## Initial optimization order

1. establish final-stack FP8 target-only and width-12/depth-11 baselines;
2. profile FP8 cache update and exact q1/M12 paged attention separately;
3. investigate scaled E4M3 insertion at the Q/K norm + RoPE boundary;
4. tune the real B70 FP8 paged-attention shapes and block policy;
5. re-sweep DFlash depth only after the target/cache path is stable.

Negative results and failures belong in `notes/`; source deltas belong in
`patches/`; structured outputs belong in `data/` or the referenced NVMe run
directory.
