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
   `--long-context-tokens 2157`. Offline calibration gives 2,036 raw prompt
   tokens; the previously observed 12-token chat wrapper should make server
   usage exactly 2,048 tokens. Server usage is authoritative. Require exactly
   2,048 prompt tokens, all recorded cached-token values zero, one repeat hash,
   and an exact needle response. The known 5/7 short result may reproduce; any
   new short failure is a regression.
4. Run the formal exact-depth harness once at depth 2,048 with configured
   capacity 3,072. It uses the Flash-Next-specific sealed flat-token fixture,
   requests 128 output tokens, and must pass every harness check: exactly
   2,048 prompt tokens in server usage, zero cached tokens, no prompt
   truncation or context shift, exactly 128 returned token IDs, a length stop,
   and a valid conventional 100-event/99-interval timing window.
5. Run three legacy-comparative exact-p2048/o256/c1 requests, no warmups, with
   salts `context-r1`, `context-r2`, and `context-r3`. Offline tokenizer
   calibration fixes `--prompt-tokens 2099`, which produces exactly 2,048 API
   prompt tokens for all three salts. These samples retain the 1K arm's
   historical after-first-text accounting; the formal exact-depth receipt is
   the cache-zero and 99-interval authority for the 2K cell.
6. Stop the server normally and retain the full log, request outputs, identity,
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
- The three legacy exact-2K rates are comparable to the exact-1K
  synthetic-prompt rates, not to the ordinary p146 control or the 99-interval
  realistic-suite metric. The formal 2K row uses its separately labeled
  100-event/99-interval accounting and must not be substituted into that
  legacy series without the accounting label.

## Sealed inputs

- `scripts/qwen38-text-quality-suite.py` SHA-256
  `67e65fc342393e5ae6903a332c929b3a2693e1f943c8a819b8447284fe835f6d`;
- `data/qwen27-exact-depth/qwen38-flash-next-bcd9f01-exact-depth-v1.json`
  SHA-256
  `c44fccbaf600cc506d8ed0cc7357161057b86abc44469b611be71db97558061d`;
  selected depth-2,048 prompt-token-array SHA-256
  `a173e60e5047c0f080e0ea45680eecbb533d30946cfc2ae0e028c684bf18d1ba`;
- `scripts/build-qwen27-exact-depth-fixtures.py` SHA-256
  `54771cfdf1f84ba6844ddf6a4d8141a0d403750e84af1bba57e13f8c88d81e52`;
- `scripts/bench-openai-token-depth-suite.py` SHA-256
  `8f162c1ab9fde7e0daffed2c4f0d6ff061ad6076c5de716e36f3d883ab4a1067`;
  the plan-only formal request payload for model
  `qwen38-flash-next-fp8-tp4`, depth 2,048, capacity 3,072, vLLM response
  adapter, seed 1, and 128 output tokens has SHA-256
  `3aa1bba4d0ade3c07e7cad10bb5ee01245dc194d28dc17359311ece3b4ab6f36`;
- `scripts/bench-openai-concurrency.py` SHA-256
  `0703d8f0564cab625183a02f010d238c8456d2e9e6aac04f4b8e11f81c8d6ae0`.
