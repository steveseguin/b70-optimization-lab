# Qwen3.8 Flash-Next UD-IQ3_XXS — quantized compressed version

**October 24 precision qualification:** The CPU oracle uses the custom BF16 recurrent-state contract. Even first-128-token agreement does not establish equivalence to reference FP32 recurrence or no additional quality loss. Historical timings and internal parity remain measured; reference fidelity is unqualified. The exact two-card P195/P165 source proof is retained in the [audit](../../experiments/own-xpu-runtime/gsq-rco-iq3s/candidate-appraisals/published-unsloth-recurrent-state.md); it is not a proof of every one-card binary.

## October 23 optimization closeout

The one-card capped record is now **37.595605 tok/s**: twelve prompts, 128 output
tokens each, all 1,536 token IDs exact. The independent audit and approved result
are in the [completed packet196 record](../../experiments/own-xpu-runtime/stage2/packet196-onecard-diet-chain/RESULT.md).
This is a separate identity from the full-512 profiles below.

The separate [streaming pilot](../../experiments/own-xpu-runtime/stage2/packet201-streaming-serving/RESULT.md)
completed sixteen turns and 1,484 tokens in one loaded owner, with seven SSE and
nine JSON responses, exact prior outputs and retained checkpoint state, and safe
exit. It establishes bounded serving correctness, not a new speed record.

[Updated recipes and read-only verification](../../repro/qwen38-flash-next-iq3xxs-ownrt-tp1-b70/LATEST.md)
keep record, source-build and serving identities explicit. Later prefill and
expert-sharing work is retained as CPU/compile-only research and is not promoted
into these measured recipes. Further optimization is closed at the owner's request.

## One-card rebuild and checkpoint results, October 22

One lane-A window (runner unit `lanequeue-A34`, 2026-10-22 02:13–02:55 UTC,
whole host, kernel fault count 2 before and 2 after) ran four one-card rows.
All four passed.

**Rebuilt binary (packet178).** A portable rebuild from the one-card
package's published source archive and build manifest produced a new binary
whose hash differs from the sealed packet165 binary. Two fresh loads of this
rebuild measured writing at **31.827 / 31.813 tok/s** and reading a 512-token
prompt at **32.823 / 32.888 tok/s**. All 13 responses, the twelve suite
prompts plus the reading request, are identical token for token across both
loads and to the sealed packet165c rows (31.782 / 31.510 tok/s). The first
128 output tokens remain the only oracle-checked span. The one-card package
still pins and measures the sealed binary. The two-card rebuild has not been
tested on device.

**Checkpoint restart-and-continue (packet179, experimental).** The checkpoint
engine is a packet165 relink with new save/restore entry code; every kernel
object is unchanged. Its own full-suite load measured 31.850 tok/s, with the
same 13 responses as the sealed rows and the rebuild. The gate saved one generation after 256 generated tokens
of an 87-token prompt: 1.10 s and 68,756,516 bytes in 128 state blobs. Two
separate new processes each restored it, in 0.458 s and 0.437 s, and generated
128 more tokens. The merged 384 tokens equal the uninterrupted reference
exactly, both restores match, and the first 128 tokens match the oracle.
Recomputing the same prompt and 256 tokens from scratch took 36.75 s. This is
a same-generation save/restart/resume only. Adding a new turn after a
restore, and saving again after a restore, are not implemented. The
checkpoint manifest keeps the label `experimental`. The blob bytes are not in
Git; the tracked manifest records each blob's size and SHA-256. None of these
rows is a strict headline or submission-eligible.

- [Exact derived values, token comparisons and source hashes](ownrt-measurements-20261022.json).
- [CPU-only extraction with independent token, oracle and checkpoint checks](extract-ownrt-window-20261022.py).
- [Packet178 rebuild evidence](../../experiments/own-xpu-runtime/stage2/packet178-onecard-portable/one-card/evidence/build.json), [packet179 checkpoint gate](../../experiments/own-xpu-runtime/stage2/packet179-session-swap/one-card/evidence/device-p179-checkpoint-A-b/bracket-summary.json), [checkpoint contract](../../experiments/own-xpu-runtime/SESSION-SWAP-DESIGN.md) and [window note](../../notes/2026-10-21-own-runtime-window-pin-guard-refusal.md).

```bash
python3 -B results/qwen38-flash-next-ud-iq3xxs-b70/extract-ownrt-window-20261022.py
```

## Current measured own-runtime profiles, October 19

These are separate from the official FP8 model. The full-512 workload has now
been measured on two fresh loads per topology; the older package's statement
that all 512-token prefill is unmeasured is superseded for these identities.

| Profile | Writing, first 99 intervals | Reading, 512 input / native TTFT | Context allocation / users |
| --- | ---: | ---: | --- |
| Two cards, bundle 8 / packet136 through packet165 | 58.632 / 58.557 tok/s | 75.973 / 75.884 tok/s | 4,096 / 1 |
| One card, target-only packet58aj through packet165c | 31.782 / 31.510 tok/s | 32.752 / 32.595 tok/s | 4,096 / 1 |

Each slash separates two observed fresh loads, not an error interval. Twelve
varied prompts ran once per load with a 512-token response cap, plus a distinct
512-input-token document. Outputs match across both loads. The CPU oracle
covers only the first 128 output tokens of the twelve suite prompts. The
reading request has no independent oracle, and full-output quality approval
remains false. These are measured lab observations, **not strict public
headlines or submission-eligible results**.

Reading is 512 / native request TTFT after a different prompt warms the runtime,
with full request-state reset and zero cached tokens. It includes first-token
work; one-card timing additionally includes reset while two-card timing starts
after reset. It is not isolated device prefill or HTTP TTFT. Only one suite
prompt finished naturally in each run; full-natural-completion medians in the
raw receipts therefore have sample count 1 and are not twelve-prompt medians.

The separately approved capped records are two-card **63.611824 tok/s**
(packet195 diet chain: packet190's k3x line + the bit-identical instruction diet of
the IQ2_S expert gate/up kernel, October 23, `cmvkniuvp003gng017f0s68rn`; supersedes packet190
62.345282, packet187 60.659520 and packet136 58.798109) and one-card **37.595605
tok/s** (packet196 diet/max23: exact expert gate/up instruction diet,
23,049,601,024-byte expert cache, spin wait and kernel foreground I/O;
October 23, `cmvl5k4p9004nng01z5xtanw5`; supersedes cache23 36.602512,
packet182c 35.926720 and packet58as 34.573038). They use the older 128-token cap. Those record
packets do not have the full-512/prefill measurements above; packet58aj does. See the [submission ledger](../localmaxxing-submissions.md).

Actual prompt-length scaling and concurrency remain unmeasured on these exact
identities. The native controller processes one request at a time. Historical
256/4K/32K capacity allocations below are not a prompt-length speed curve and
cannot supply these missing measurements.

- [Exact derived measurements with source hashes](ownrt-measurements-20261019.json).
- [CPU-only extraction and independent timestamp/oracle-prefix/repeat checks](extract-ownrt-measurements.py).
- [Two-card current candidate replay](../../repro/qwen38-flash-next-iq3xxs-ownrt-tp2-b70/README.md).
- [One-card current candidate replay](../../repro/qwen38-flash-next-iq3xxs-ownrt-tp1-b70/README.md).
- [Original October 13 result page](packet44-results.md) and [packet44 replay](../../repro/qwen38-flash-next-iq3xxs-ownrt-tp2-b70/packet44-replay.md).

CPU evidence checks can be repeated without model loading or GPU access:

```bash
python3 -B results/qwen38-flash-next-ud-iq3xxs-b70/extract-ownrt-measurements.py
```


## Historical own-runtime record: packet 44, October 13

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
