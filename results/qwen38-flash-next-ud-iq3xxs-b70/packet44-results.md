# Qwen3.8 Flash-Next UD-IQ3_XXS — quantized compressed version

## Own Xe runtime record: packet 44, October 13

**Two B70 cards, two rank processes (TP2), native controller, full BF16 KV,
official MTP draft head with target verification.** This quantized compressed
model uses Unsloth revision `766911a6b7369840a91dbcd95f9f997acaab6cd6` and the
lab's arithmetic-v2 CPU oracle. It is a separate lane from official FP8.

LocalMaxxing approved **37.85626413203107 tok/s**, submission
`cmv6pugme0020oa01fjrho6nx`: median within each of six prompt classes, then
median across those class medians, using **99 intervals between generated-token
timestamps 1 and 100**. The ordinary all-prompt median is 37.77, not the same
aggregation. Each of twelve prompts ran once with a 128-token cap, after an
excluded distinct warmup, with full state reset and no prompt/KV/response reuse.

| Allocation capacity | Cap / requests | Decode median (63 intervals, tokens 1–64) | All-prompt submission median (99 intervals) | Exact requests |
| ---: | --- | ---: | ---: | --- |
| 256, packet 38 predecessor | 64 / 24 | 38.25 tok/s | unavailable | 24/24 |
| 4,096, packet 44 | 128 / 12 | 37.59 tok/s | 37.77 tok/s | 12/12 |
| 32,768, packet 44, other card pair | 128 / 12 | 37.71 tok/s | 37.70 tok/s | 12/12 |

At both packet44 capacities, all **1,536 token IDs and 4,608 retained layer
fixtures** match CPU oracles byte for byte, with zero tolerance. Fixture checks
cover generated steps 1–8, not every intermediate state. Draft-only 8-bit
requantization changes guesses, which the unchanged target verifies; it does
not change accepted tokens. Sequential target-only decode at 4,096 is 25.00
tok/s on its separate 128-token suite. The 64-token suites repeat 24/24 exactly.

At 4,096 the per-prompt decode range is 34.45–40.71 tok/s; at 32,768 it is
34.27–40.46. **Prefill at 512 input tokens: not measured.** Median TTFT is
1,422.011 ms and median wall speed 26.634 tok/s for the 4,096 suite, whose median
input is 68 tokens. Capacities reserve storage; these short-input measurements
are not a prompt-length performance curve. Separate WL checks retain exact
32-token outputs from 598- and 2,271-token prompts, with no intermediate
midprompt comparison. No official-FP8 or llama.cpp output equivalence is claimed.

The approved result is preserved as recorded. A 128-token cap does not pass
the repository's 512-token natural-completion final gate; two fresh complete
128-token suite launches are also not established. The linked historical
attestation is `lab.promotion-attestation.v1`, not the newer hash-bound
`neural.download.promotion-attestation.v1` contract. No new external submission
or strict headline promotion is made by this publication. Clean-host rebuild,
portable admission and binary release verification remain pending.

- [256-position predecessor chain](../../experiments/own-xpu-runtime/stage2/packet38-integrated/receipts-cards01-20261012-chain/README.md)
- [4,096 receipt chain](../../experiments/own-xpu-runtime/stage2/packet44-context/receipts-cards01-20261013-c4096/README.md)
- [32,768 receipt chain](../../experiments/own-xpu-runtime/stage2/packet44-context/receipts-cards23-20261013-c32768/README.md)
- [Class-balanced result and prompt/output hashes](../../experiments/qwen38-flash-next-ud-iq3xxs-b70/data/20261013-own-rt-iq3-tp2-c4096-realistic-suite-v1-result.json)
- [Historical attestation](../../experiments/qwen38-flash-next-ud-iq3xxs-b70/data/20261013-own-rt-iq3-tp2-c4096-promotion-attestation.json)
- [Payload queue](../../experiments/qwen38-flash-next-ud-iq3xxs-b70/data/20261013-own-rt-iq3-tp2-c4096-localmaxxing-payload-queue.json) and [submission ledger](../localmaxxing-submissions.md)
- [Lab replay recipe and CPU verification](../../repro/qwen38-flash-next-iq3xxs-ownrt-tp2-b70/README.md), [publication chain](../../repro/qwen38-flash-next-iq3xxs-ownrt-tp2-b70/publication-manifest.json)

## Preserved reference-runtime screening record

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
median **15.94 tok/s**, 12/12 byte-equal
([table](reference-baseline-onecard-uncontended-20261011.md)). Identical to the
contended run, so the earlier exploratory 21.6 tok/s came from giving the CPU
side 8 threads instead of the plan's 2: the one-card reference is bound by the
CPU threads working the layers the fitter leaves on the host. A one-card plan
variant with more CPU threads is a reasonable future reference row; it is not
our runtime's concern.
