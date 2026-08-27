# Qwen3.8 Flash-Next FP8 TP4 2K context preregistration

Date: 2026-08-27

## Purpose

Classify the additive 2K active-context cell without changing or replacing
the retained 512-cap control or 1,536-cap 1K result. This is a context-specific
research arm, not an optimization trial and not a promotion attempt.

## Frozen server identity

The launcher is
`tools/launch-tp4-ep4-eager-mtp0-3072.sh`. It changes only the configured
maximum to 3,072 tokens and the derived campaign/run-directory identity. The
following remain identical to the completed 1K arm:

- model `Qwen/Qwen3.8-Flash-Next-FP8` revision
  `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`;
- vLLM overlay `658965050f259999e635b52a850004a3771cd644`;
- XPU kernels `2f829747503c77d4814834dffd0840fb1dd9f75a`;
- sealed production runtime stage
  `/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70`;
- TP4/EP4, eager, MTP0, graph disabled, text-only;
- 12.25-GiB selective host placement and the exact parameter selectors;
- 192-MiB fixed KV allocation, `BLHNC`, KV dtype auto, block size 64;
- one sequence, 64 maximum batched tokens, prefix caching disabled;
- all communication, scheduler, compilation, and diagnostic settings.

The prior server reported capacity for 3,949 cache tokens with this fixed KV
allocation. The planned exact request is 2,048 prompt plus 256 output tokens,
which is below both the 3,072 configured limit and the prior reported cache
capacity. The new server must independently report at least 2,304 cache tokens
before any qualification request is sent.

## Sealed request program

After health and identity gates:

1. Save `/v1/models` and require reported maximum length 3,072.
2. Require one exact 12.22-GiB selective-placement receipt from each rank and
   cache capacity of at least 2,304 tokens.
3. Run the short/needle suite once with 16 repeats, thinking disabled, and
   `--long-context-tokens 2048`. Require all recorded cached-token values to be
   zero, one repeat hash, and an exact needle response. The known 5/7 short
   result may reproduce; any new short failure is a regression.
4. Run three unique exact-p2048/o256/c1 requests, no warmups, with salts
   `context-r1`, `context-r2`, and `context-r3`. Offline tokenizer calibration
   fixes `--prompt-tokens 2099`, which produces exactly 2,048 API prompt tokens
   for all three salts.
5. Stop the server normally and retain the full log, request outputs, identity,
   hashes, and shutdown classification.

The 12-prompt realistic suite is not repeated in this arm: it already passed
on the identical production source/runtime and is not a context-depth test.
The 2K needle, repeat battery, and exact-depth samples are the incremental
evidence required for this cell.

## Frozen interpretation

- Any identity mismatch, missing rank receipt, insufficient cache capacity,
  unhealthy server, nonzero cached-token observation, repeat divergence,
  needle failure, or new short-suite failure stops performance interpretation.
- A valid 2K arm remains `lab-screened` and research-only because the inherited
  substantive short-quality miss still blocks deployment promotion.
- The prior 512 and 1K measurements remain authoritative for their cells and
  cannot be lowered, overwritten, or replaced by this result.
- Exact-2K rates are comparable to the exact-1K synthetic-prompt rates, not to
  the ordinary p146 control or the 99-interval realistic-suite metric.

## Sealed inputs

- `scripts/qwen38-text-quality-suite.py` SHA-256
  `67e65fc342393e5ae6903a332c929b3a2693e1f943c8a819b8447284fe835f6d`;
- `scripts/bench-openai-concurrency.py` SHA-256
  `0703d8f0564cab625183a02f010d238c8456d2e9e6aac04f4b8e11f81c8d6ae0`.
