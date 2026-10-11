# Qwen3.8 Flash-Next UD-IQ3_XXS — quantized compressed version

**Reference-runtime baseline screening; not our runtime, not certified.**
Two B70s are the primary owner target and one B70 is a secondary target.
This separate Unsloth model has its own weights and CPU oracle; it does not
replace or share a performance record with the official FP8 model.

## October 11 two-card screen: faulted, incomplete

`window-20261011-boot13858eef` recorded **9 of 24 planned rows**, all in
repeat 1. Its fault watch caught an engine reset on `0000:43:00.0` at
02:34:46 UTC and stopped further launches. No repeat 2 or completed comparison
exists. The fault was on another card; that does not waive the host-wide stop
or establish a cause. This is retained diagnostic evidence, not a successful
baseline or certified speed. Recovery remains the coordinator's work.

| Observed rows only | Median | Samples |
| --- | ---: | ---: |
| Decode (writing), runtime aggregate | 25.905 tok/s | 8 |
| Prompt processing (reading), actual prompt lengths | 47.04 tok/s | 9 |
| Repeat 2 / byte equality | not measured | 0 |

The immediate-EOG code-review row has zero generated text tokens, no finite
decode rate and retained prompt timing. The eight other rows hit the 64-token
cap (63 timed decode evaluations). Medians are ordinary observed-row medians,
not the class-balanced 99-interval promotion metric. They exclude absent and
failed rates; they do not extrapolate the missing suite rows. Prompt speed is
not a 512-token prefill benchmark. TTFT and full-suite speed remain unmeasured.

[Generated per-prompt table](../../experiments/qwen38-flash-next-ud-iq3xxs-b70/data/window-20261011-boot13858eef-partial/summary.md)
contains both repeat columns, output counts, equality status and denominators.
[Snapshot manifest](../../experiments/qwen38-flash-next-ud-iq3xxs-b70/data/window-20261011-boot13858eef-partial/snapshot.json)
binds byte-preserved runs, command receipts, stdout/stderr, environment,
health receipt, model verification, gap override and fault/journal evidence.
The source run directory is retained untouched. Concurrent one-card exploration
shared this host; these partial measurements are not isolated-card comparisons.

## Exact identity and limits

- Unmodified llama.cpp `23b0202a189c44a54625aadcb37a946dd1d6278d`, SYCL F32
  arithmetic; [build receipt](../../experiments/qwen38-flash-next-ud-iq3xxs-b70/baseline-llamacpp/build-receipt.json).
- `unsloth/Qwen3.8-Flash-Next-GGUF`, revision
  `766911a6b7369840a91dbcd95f9f997acaab6cd6`, three UD-IQ3_XXS shards;
  [authenticated model packet](../../experiments/qwen38-flash-next-ud-iq3xxs-b70/packet1/README.md).
- `steve-b70s`, two B70 cards selected by `level_zero:0,1`, local devices
  `SYCL0,SYCL1`; layer splitting 1:1, all layers requested on GPU, explicit
  CPU input/PLE embeddings, fitting off, FP16 K/V, context 4096, batch 512,
  microbatch 128, flash attention off, two CPU threads, one request/process.
- Fixed twelve realistic prompts, greedy seed 20260609, 64-token cap,
  no runtime warmup, prompt/KV/response reuse or speculative decoding.
  The retained window used a 60-second coordinator gap override.
- CPU dequantization sample fixtures pass, but full-model CPU parity,
  deterministic fresh-process repeats and successful final health postflight
  are not established by this interrupted screen. `realistic_final_gate=false`.

The one-card [exploratory probe](../../experiments/qwen38-flash-next-ud-iq3xxs-b70/explore/README.md)
reported 21.64 decode tok/s and 49.8 prompt tok/s. Its split was not captured
and its output differs from the two-card probe; it is not a matched benchmark
or a lossless qualification. The new verbose one-card screen is preregistered
but has not been executed by this CPU-only preparation.

[Selectable plans, admission and commands](../../experiments/qwen38-flash-next-ud-iq3xxs-b70/baseline-llamacpp/run-identity.md)
retain the original two-card identity and add fitter-selected one-card placement.
Use the [summariser](../../experiments/qwen38-flash-next-ud-iq3xxs-b70/baseline-llamacpp/summarise.py)
on each future fresh output directory; never combine independent or partial
windows into a completed 24-row run. No public package, headline or deployment
is promoted here.

## Reference-runtime baseline, complete screens (2026-10-11, boot 13858eef)

Pinned upstream llama.cpp SYCL build (not our runtime; measurement baseline
only). 12 fixed prompts x 2 fresh-process repeats, greedy, 64 tokens, 4K
context, single user, 60 s gaps, concurrent on disjoint cards:

| Plan | Cards | Decode tok/s median (n) | Prompt tok/s median | Repeat byte-equal |
| --- | --- | ---: | ---: | --- |
| two-card, layer split | 0,1 | **28.49** (22) | 54.9 | 12/12 |
| one-card, fitter (CPU overrides) | 2 | **15.88** (22) | 47.6 | 12/12 |

Two prompts ended immediately (0 generated tokens) in both plans and are
recorded as such. The one-card number was taken while the two-card screen and
several CPU builds shared the host; an uncontended exploratory run measured
21.6 tok/s. Full tables: [reference-baseline-20261011.md](reference-baseline-20261011.md).
These are uncertified reference figures for our own runtime to beat.

Uncontended repeat of the one-card plan (card 2 alone, 03:23-03:55 UTC): decode
median **15.96 tok/s**, 12/12 byte-equal
([table](reference-baseline-onecard-uncontended-20261011.md)). Identical to the
contended run, so the earlier exploratory 21.6 tok/s came from giving the CPU
side 8 threads instead of the plan's 2: the one-card reference is bound by the
CPU threads working the layers the fitter leaves on the host. A one-card plan
variant with more CPU threads is a reasonable future reference row; it is not
our runtime's concern.
