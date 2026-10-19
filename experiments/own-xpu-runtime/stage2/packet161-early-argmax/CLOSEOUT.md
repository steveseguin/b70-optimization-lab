# Packet161 exact early-argmax feasibility — closeout

<!-- campaign-closeout -->

## Question and identity

Can rigorous upper bounds avoid enough unchanged head work to support at least
3% over two-card bundle8's 58.798108759 tok/s? This CPU study uses real Unsloth
UD-IQ3_XXS `output.weight` Q6_K rows, width 2,560, the full 248,320-row target
and fixed 80,128-row draft prefix. The arithmetic contract remains
`iq3-p49-split32-v1`. No runtime changed or GPU job launched.

## Outcome

**No build admitted.** Donating the final winning logit before reading any row,
and the entire historical full-target-head saving to the critical rank, gives
only **+2.240%** in the most favorable mean-cost sensitivity. Bounds, ordering
and extra launches are free in that figure. A metadata-bandwidth sensitivity
reduces the best surviving scheme to **+1.637%**. Neither number is a measured
speedup or a current target-head timing.

The requested coverage is **partly incomplete**: target coverage is 200 distinct
positions across all 12 suite prompts and 120 generated positions from five
fixed packet114 document excerpts retained by packet132. Draft coverage is 65
distinct native KD incident positions; no exact independent draft or other
eleven-prompt draft read fraction was obtained. Missing evidence is not a
measured negative. No READY marker, build brief or proposal exists.

## What worked

[Per-position fractions](evidence/fractions.csv) and [summary](evidence/analysis.json):

| Fixed bound | Suite target, 200 | Independent target, 120 | Native incident draft, 65 |
| --- | ---: | ---: | ---: |
| Row norm | 99.999919% | 100% | 100% |
| 256-weight block norms | 99.999879% | 100% | 100% |
| Quantization-group16 norms | 99.999120% | 100% | 100% |
| Partial dots, 256-weight blocks | 83.1934% | 85.7299% | 82.8852% |
| Partial dots with group16 bounds | 78.6276% | 84.5303% | 80.6393% |

These are mean full-row-equivalent weight reads, with the correct final maximum
supplied for free: optimistic lower bounds for these fixed schemes, not an
implemented running-max scan. Almost every row is still touched; partial dots
save the last blocks of losing rows. Counts, medians and ranges are retained.
The best individual suite position reads 51.19% under the last scheme; that is
not representative and is not used as an all-position gain. Both unequal
target partitions are reported separately in the CSV.

The [proof](PLAN.md) includes FP32 product/accumulator/tree error, gradual
underflow, outward FP64 error, BF16 rounding, strict ties and a full-scan
fallback contract for exceptional inputs. The CPU head uses the original
32-lane order. Target HC reconstruction passes all **1,600 stored top-five
logits** exactly; native draft inputs pass 65 saved prefix-winner checks. These
validate reconstruction usefully, but are not an independent all-hidden-byte
comparison or a device qualification.

[Pricing](evidence/pricing.json) reproduces all 1,188 original intervals and
the class-balanced record before applying the labeled sensitivities:

| Scheme / target corpus | Draft saving before overhead | Target saving before overhead | Free-overhead gain | Metadata sensitivity gain |
| --- | ---: | ---: | ---: | ---: |
| Partial256 / suite | 0.076220 ms | 0.235911 ms | 1.793% | 1.637% |
| Partial256 / independent | 0.076220 ms | 0.200307 ms | 1.555% | 1.400% |
| Group16 partial / suite | 0.086222 ms | 0.300001 ms | 2.240% | −0.006% |
| Group16 partial / independent | 0.086222 ms | 0.217145 ms | 1.705% | −0.517% |

Draft costs use 0.4453476 ms from packet122/158's historical diagnostic. Target
costs use packet87's older full-head 1.403683854 ms; packet105b/136 do not retain
an isolated current half-head GPU time. Do not invent it or divide by two:
the target split is 202,240 / 46,080 rows. Its saving is generously donated
entirely to B in packet160's replay. The same 65-position incident draft mean
is used in both corpus sensitivities; independent rows do not measure
independent draft behavior. Suite target per-prompt sample means are applied
to the replay, not falsely joined as per-position observations. Metadata uses
one FP32 norm per group plus one row-index word, priced at 537 GB/s as a
sensitivity, not a hard latency floor. Online bound arithmetic, synchronization
and irregular memory access remain unpriced costs. No supported net 3%
mechanism follows from this evidence.

## What failed or remains uncertain

The one-card chain was active at entry 03:47 UTC. The session was frozen during
its measurement and resumed with the unit inactive at 04:16. Weight-read
admission was recorded after that transition. The existing CPU-only native
draft executable was then tested with the real independent doc0 capture argv
to see whether missing draft data could be recomputed without a build.

Its first invocation refused before reading weights because the existing loader
requires idle I/O priority. The corrected, fresh-named invocation used
`ionice -c3` for that child only and a **3.7 GB hard address-space cap**, leaving
room for the supervisor under the 4 GB total budget. It reached `std::bad_alloc`
after 32.40 seconds, peak child RSS 3,601,132 KiB. Its MockDevice teardown
completed with zero live bytes and safe exit. The cap was not increased and no
allocation retry was made. Both receipts remain under `evidence/draft-probe*`.
This is a CPU preparation refusal, not a GPU fault.

Schemes and data were committed as `d71d22866` before GGUF access. A concurrent
remote push rejected the immediate push; the shared-workspace coordinator
merged main while this session was frozen. A subsequent push confirmed
everything up to date. Unrelated dirty orchestration files were preserved.

## Evidence and patches

[Plan/proof/prior closures](PLAN.md), [positions and hashes](evidence/positions.json),
[head inputs](evidence/hidden.bf16.gz), [preparation](evidence/preparation.json),
[CPU tests](evidence/cpu-tests.log), [analysis](evidence/analysis.json),
[replay](evidence/pricing.json), [native probe](evidence/draft-probe-idle-result.json),
[retention](RETENTION.md), [negative index](DO-NOT-REPEAT.md).

Analysis peaked at 814,588 KiB RSS and took 28.67 seconds. No compiler, model
server, GPU work, service change, sudo, host setting change or live queue edit
was used. The native probe used a pre-existing CPU-only binary. Only packet161
and its dated note changed. Reproduction commands are in PLAN; `price.py`
replays without opening weights. Python mains use nice19, the assigned CPUs,
`-B`, closed stdin, memory caps and the 27 GB CPU storage floor.

## When to revisit

A materially tighter inexpensive certificate or algebraic head structure that
reduces actual critical work, with exact native draft states across both
corpora, current isolated head timing and an overhead-inclusive ≥3% supported
bound. Do not retry these norm schemes, tune on the suite, change the prefix,
use a partial winner as a corrected target, or pretend missing draft data passed.
Future admission still needs both lanes, unchanged exactness, real-argv CPU
preparation, real-parent analyzer checks, stream/format/exactness-only in-run
proof checks, no wall-clock data-proof deadline, 25 GB device floor, 27 GB CPU
stop, fresh names and READY last. The optimization lane remains open.
