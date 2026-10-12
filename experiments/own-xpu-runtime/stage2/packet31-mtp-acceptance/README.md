# Packet 31: CPU draft acceptance

This measures guesses against the IQ3 target’s own greedy tokens. The target is the Unsloth quantized compressed version, with arithmetic `iq3-p17-detmath-v2`. Drafts never changed the target’s input or state. No GPU or device API was used.

The FP8 draft is a CPU reference of the official MTP architecture and quantization semantics. It uses the stored FP8 codes and BF16 block scales, dynamic FP8 activations, and explicit BF16 boundaries. **It is not certified bit-identical to the served XPU draft kernels.** CPU dots, transcendental functions, attention reductions and compiled XPU quantization can differ. See the independent [wiring review](wiring-review.md).

## Acceptance

Each cell gives hits out of 64 and the percentage. The pooled column has 256 guesses. These are four development prompts, including the incident prompt used to develop the runtime. They are not a benchmark suite.

| Guess source | Incident | Code review | Customer email | Benchmark analysis | Pooled | Pooled 95% Wilson |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| FP8 MTP · IQ3 bindings | 54/64 (84.4%) | 43/64 (67.2%) | 52/64 (81.2%) | 49/64 (76.6%) | 198/256 (77.3%) | 71.8%–82.0% |
| Int8 MTP · IQ3 bindings | 54/64 (84.4%) | 43/64 (67.2%) | 52/64 (81.2%) | 49/64 (76.6%) | 198/256 (77.3%) | 71.8%–82.0% |
| FP8 MTP · official bindings | 54/64 (84.4%) | 43/64 (67.2%) | 52/64 (81.2%) | 48/64 (75.0%) | 197/256 (77.0%) | 71.4%–81.7% |
| Shortlist 4,096 | 22/64 (34.4%) | 24/64 (37.5%) | 32/64 (50.0%) | 29/64 (45.3%) | 107/256 (41.8%) | 35.9%–47.9% |
| Shortlist 16,384 | 31/64 (48.4%) | 33/64 (51.6%) | 40/64 (62.5%) | 32/64 (50.0%) | 136/256 (53.1%) | 47.0%–59.1% |
| Shortlist 65,536 | 42/64 (65.6%) | 41/64 (64.1%) | 48/64 (75.0%) | 40/64 (62.5%) | 171/256 (66.8%) | 60.8%–72.3% |
| Recent unigram successor | 1/64 (1.6%) | 4/64 (6.2%) | 4/64 (6.2%) | 7/64 (10.9%) | 16/256 (6.2%) | 3.9%–9.9% |
| Recent bigram successor | 4/64 (6.2%) | 5/64 (7.8%) | 4/64 (6.2%) | 9/64 (14.1%) | 22/256 (8.6%) | 5.7%–12.7% |
| Repeat current token | 1/64 (1.6%) | 0/64 (0.0%) | 0/64 (0.0%) | 0/64 (0.0%) | 1/256 (0.4%) | 0.1%–2.2% |
| FP8 MTP top 2 | 59/64 (92.2%) | 53/64 (82.8%) | 58/64 (90.6%) | 56/64 (87.5%) | 226/256 (88.3%) | 83.8%–91.7% |
| FP8 MTP top 4 | 63/64 (98.4%) | 58/64 (90.6%) | 62/64 (96.9%) | 62/64 (96.9%) | 245/256 (95.7%) | 92.5%–97.6% |

Wilson intervals describe binomial counts. Tokens within a prompt are correlated, so these intervals do not measure uncertainty across real-world tasks. Top-2/top-4 are membership rates, not the acceptance of a single guess.

## Misses and controls

| Source | Longest miss run (incident / code / email / analysis) | Copy-current hits | Next-next hits | Agreement with FP8 IQ3 draft |
| --- | --- | ---: | ---: | ---: |
| FP8 MTP · IQ3 bindings | 2 / 5 / 2 / 2 | 1/256 | 3/256 | 100.0% |
| Int8 MTP · IQ3 bindings | 2 / 5 / 2 / 2 | 1/256 | 3/256 | 99.2% |
| FP8 MTP · official bindings | 2 / 5 / 2 / 2 | 1/256 | 4/256 | 98.0% |

The per-position tokens, top-four logits, top-two margin, hit/miss flags and every source’s per-prompt decile counts are in [acceptance.json](acceptance.json). Longest miss runs reset between prompts. Both offset controls cover all 256 positions, using one extra target prediction at the end.

## Wiring and target gate

For target input x[p] and output x[p+1], the draft uses `MTP(H[p-1], embedding(x[p]))`, with draft cache/RoPE position **p-1**. It starts with `(H[0], x[1])`. Every shifted prompt row is processed before generation. Each variant has independent, complete BF16 QSA K/V and indexer caches.

H is the materialized layer-47 output before the target’s final mixer: four contiguous streams of 2,560 BF16 values. MTP applies a global 10,240-element hidden Gemma norm, its shared per-stream hidden projection, and the normalized/projected token embedding as a broadcast residual. The draft has its own QSA, indexer, 512-expert router, top-ten experts, shared expert, HC mixers and final mixer; it has no PLE. Official norm parameters use `1+w`. No extra norm is inserted before the shared head.

FP8 input groups of 128 are dynamically quantized before gate/up and again before down. Stored `weight_scale_inv` values multiply the FP8 codes. Router probabilities multiply the down accumulator before BF16 rounding; the weighted outputs sum in slot order. QSA and shared-expert sigmoid outputs round to BF16 before multiplication. The primary embedding/head use the IQ3 target’s bytes; its head uses the runtime’s packed-weight reduction. Official BF16 embedding/head bindings are a separate control.

The incident run matches **all 64 sealed v2 tokens** and **all eight retained layer-47 fixtures byte for byte**. Every prompt and all 64 generated input positions have a stream hash and greedy prediction. [Target gates](target-gates.json), [target evidence](target-evidence.json), and [timings](target-timing.json) retain the checks.

A fresh CPU draft process also reproduced all 64 incident positions: all 1,344 compared fields were equal, including guesses, margins and top-four logits. [Repeat gate](draft-repeat-gate.json).

## Cheaper sources

The int8 variant requantizes routed expert weights with one FP32 max-absolute/127 scale per 16 weights, nearest-even signed codes in [-127,127], and BF16 activations/dense components. The rule applies to all 512 experts; tensors are materialized only when routed. It is draft-only. This has the existing expanded format’s code/scale geometry, but it is a new quantizer and needs a new device type/loader. The routed bank has 2,516,582,400 weights: about 2.517 GB as stored FP8 plus block scales, or 3.146 GB as int8 codes plus group16 FP32 scales, before dense parts and the head. These are storage calculations, not allocation measurements.

The shortlist first pass scores every row from 64 evenly spaced head columns. It selects K rows without target logits, target tokens or future context, then uses the normal IQ3 head score inside that list. Equal final logits keep the first-pass rank order. Full reference logits were reused offline to measure acceptance; no shortlist execution speed was measured. The first-pass table is about 63.6 MB in FP32. Because candidates change each position, all head rows still need backing storage; this is fewer evaluated rows, not a fixed smaller resident vocabulary. Token-only guesses use the most recent completed successor in the context; bigrams fall back to unigrams, and missing unigrams repeat the current token.

## CPU cost

These timings describe this low-priority CPU capture, not device throughput. Target captures include the full head even at prompt positions, and run alongside one CPU draft thread. Draft timings include weight reads; the int8 layer also includes on-demand requantization. None is a resident-device latency estimate.

| Prompt | All-position mean seconds | Prompt mean seconds | Generated-input mean seconds |
| --- | ---: | ---: | ---: |
| incident-retrospective | 10.653 | 7.929 | 14.357 |
| code-review | 13.279 | 14.315 | 11.824 |
| customer-email | 11.083 | 8.866 | 13.749 |
| benchmark-analysis | 11.406 | 9.927 | 12.909 |

| Draft source | CPU layer seconds/position | CPU head seconds/scored position |
| --- | ---: | ---: |
| FP8 MTP · IQ3 bindings | 0.408 | 2.338 |
| Int8 MTP · IQ3 bindings | 0.606 | 2.316 |
| FP8 MTP · official bindings | 0.400 | 1.147 |

## Arithmetic timing model — not measured speed

The requested model is `p × (T/2 + m) + (1−p) × T` milliseconds per token. Sequential throughput is `1000/T`. It assumes equal card halves and ignores transfer, rollback, cache and scheduling costs. It also omits draft cost on misses exactly as in the supplied equation. None of these numbers is a measured device speed.

The table uses pooled acceptance; [timing-model.json](timing-model.json) also gives every per-prompt probability. Each cell lists tok/s for draft cost **3 / 2 / 1 ms**.

| Single-guess source | p | T=42 ms (23.81 sequential) | T=36 ms (27.78 sequential) | T=32 ms (31.25 sequential) |
| --- | ---: | ---: | ---: | ---: |
| FP8 MTP · IQ3 bindings | 77.3% | 35.61 / 36.62 / 37.69 | 40.99 / 42.33 / 43.76 | 45.57 / 47.23 / 49.02 |
| Int8 MTP · IQ3 bindings | 77.3% | 35.61 / 36.62 / 37.69 | 40.99 / 42.33 / 43.76 | 45.57 / 47.23 / 49.02 |
| FP8 MTP · official bindings | 77.0% | 35.53 / 36.52 / 37.58 | 40.89 / 42.22 / 43.63 | 45.46 / 47.11 / 48.88 |
| Shortlist 4,096 | 41.8% | 29.01 / 29.36 / 29.73 | 33.64 / 34.12 / 34.61 | 37.64 / 38.24 / 38.86 |
| Shortlist 16,384 | 53.1% | 30.83 / 31.34 / 31.87 | 35.67 / 36.36 / 37.08 | 39.85 / 40.71 / 41.61 |
| Shortlist 65,536 | 66.8% | 33.36 / 34.12 / 34.92 | 38.49 / 39.51 / 40.58 | 42.89 / 44.15 / 45.49 |
| Recent unigram successor | 6.2% | 24.46 / 24.50 / 24.54 | 28.52 / 28.57 / 28.62 | 32.06 / 32.13 / 32.19 |
| Recent bigram successor | 8.6% | 24.72 / 24.77 / 24.83 | 28.81 / 28.88 / 28.95 | 32.38 / 32.47 / 32.56 |
| Repeat current token | 0.4% | 23.85 / 23.85 / 23.85 | 27.82 / 27.83 / 27.83 | 31.30 / 31.30 / 31.31 |

## Device implementation limits

Acceptance does not validate overlap or speed. A device implementation still needs draft operator parity, complete prompt-cache population, a safe way to discard the guessed target step’s GDN/QSA/PLE/token-history state, and unchanged target verification on every emitted token. It must measure draft latency, transfers and simultaneous memory use. The int8 format and shortlist selection need device implementations. Shared embedding/head duplication or placement also needs a memory plan.

Four short development prompts cannot establish long-context indexer behavior, varied-task acceptance, device determinism or production readiness. The official-lane 60–100% window range is context only: these prompts, target weights, hidden states and CPU arithmetic are different, so it is not a matched comparison.

## Reproduction and retained files

Run from the repository root. All temporary data stays under this packet’s ignored build directory. `prepare_target.py` copies and instruments the frozen v2 oracle into build, compiles host-only code, and prepares the four exact prompt inputs. `run_target.py` runs sequential captures with five threads; `run_draft.py` uses one thread. `analyze.py` fails unless the sealed incident gate and full four-prompt coverage pass. `finalize.py` renders this report. See [reproduce.sh](reproduce.sh).

[build-receipt.json](build-receipt.json) binds scripts, compiler/binary identities, official tensor byte ranges and shared-IQ3 binding reads. Source files from vLLM are research/wiring references only; no vLLM runtime is imported or executed. Our existing packet2 CPU reference supplies reusable mathematical operators. Large capture dumps, binaries and scratch logs are deleted after hashing; the scripts regenerate them. [cleanup.json](cleanup.json) records that removal. Other packets and shared status files remain untouched. [Measurement closeout](CLOSEOUT.md).
