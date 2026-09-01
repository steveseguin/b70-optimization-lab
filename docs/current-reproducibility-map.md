# Reproducibility Map

This is a durable catalog of runnable recipes and promoted evidence. It is not
the authority for the currently loaded service or active research lane; use
[`CURRENT.md`](../CURRENT.md) for that live state. Historical service claims
below describe recorded lane context and may not describe what is running now.

This page connects the active Gemma 4 service, the deployable MiniMax baseline,
the session-cache experiments, the TurboQuant patch, and the long-context
research path. It is meant for a fresh human or agent who needs to reproduce or
review the current work without reading every historical note first.

Hardware scope: the local Intel lab is four Arc Pro B70 32 GB GPUs
(`128 GB` aggregate VRAM). Results here are useful because they are produced on
real community-accessible XPU hardware, but the same limit also constrains
larger model coverage. Additional high-VRAM Intel hardware would let this map
include larger GLM/DeepSeek-class lanes and more concurrent service/optimization
comparisons without sacrificing the current endpoint. The lab has spare EPYC
9015 PCIe 5.0 slot capacity, so the missing piece for broader Intel coverage is
higher-memory XPU hardware rather than host expansion.

## Promoted Closed Recipes

### Muse-Glimmer-30B Q8/WOQ Century Result

- [result packet](../results/muse-glimmer-30b-q8-woq-b70/README.md)
- [standalone reproduction](../repro/muse-glimmer-30b-q8-woq-b70-100tps-20260813/README.md)
- [source patch and history bundle](../patches/muse-glimmer-30b-b70/README.md)
- [structured result](../data/muse-q8-woq-argmax-century-20260813.json)
- [LocalMaxxing approved run](https://www.localmaxxing.com/en/runs/cmss8515c00n0ms01n3begqgg)

Identity: four B70s, TP4/concurrency one, Muse UD-Q8_K_XL target, pretrained
BF16 DFlash, fixed-N16 direct oneDNN WOQ, distributed ARGMAX. Two canonical
full-256 arithmetic means were `100.088` and `100.649 tok/s`; the frozen
15-prompt conventional first-100 median was `161.900 tok/s`, p10 `108.574`,
with every prompt cache-zero. This is a closed Q8/WOQ target-verified result,
not BF16/lossless or universally token-exact. LocalMaxxing approved the
conventional interval median as `cmss8515c00n0ms01n3begqgg`. Raw evidence is
mirrored into the repro, so review does not depend on `/mnt` paths.

## Research-Status Reproduction Foundations

### Qwen3.8 Flash-Next FP8 TP4/MTP3

- [dated experimental snapshot](../repro/qwen38-flash-next-fp8-tp4-mtp3-b70/EXPERIMENTAL-SNAPSHOT-20260831.md)
- [fail-closed reproduction foundation](../repro/qwen38-flash-next-fp8-tp4-mtp3-b70/README.md)
- [full result packet](../results/qwen38-flash-next-fp8-b70/README.md)
- [public family page](../models/qwen-flash-next.html)

Identity: official 125B-A6B FP8 artifact on four B70s, TP4/EP4, eager and
graph off, with selective host placement. The fastest retained short Grade-C
screen is MTP4 at `20.727176 tok/s` after first text; the preferred exact-4K
MTP3 screen is `15.501565 tok/s`, with `187.899 s` TTFT and `1.246260` wall
tok/s. This entry is not a promoted or runnable recipe: the hash-addressed
dependency wheelhouse, portable four-card preflight, and clean artifact-only
replay remain open, and LocalMaxxing submission is withheld.

## Qwen3.6 Family Recipes

Use the [Qwen3.6 family research map](qwen36-research-map.md) as the canonical
navigation layer. The detailed historical sections below remain available for
audit, but they do not define one comparable benchmark class.

| Identity | Reproduction or result entry |
| --- | --- |
| 27B Q8_0 target-only, two-B70 TP2 | [handoff](../results/qwen36-27b-q8-tp2-asrock-b70/HANDOFF.md), [repro](../repro/qwen36-27b-q8-tp2-asrock-b70/README.md), [patch](../patches/qwen36-27b-q8-tp2-asrock-b70/README.md) |
| 27B Q8_0 one-B70 baseline/service research | [experiment packet](../experiments/qwen36-27b-q8-gguf-b70/README.md) |
| 27B AutoRound INT4 MTP | [historical 95.385 repro](../repro/qwen36-27b-autoround-int4-b70/README.md), [source bundle](../patches/qwen36-27b-autoround-int4-b70/record-20260711/README.md), [independent validation](../experiments/qwen36-27b-autoround-int4-b70/validation-20260815/README.md), [dependency closeout](../notes/2026-08-17-qwen36-int4-input-dependency-closeout.md), [final RMSNorm closeout](../notes/2026-08-17-qwen36-int4-batch-invariant-rmsnorm-closeout.md), [determinism/speed tradeoff](../notes/2026-08-18-qwen36-int4-determinism-speed-tradeoff.md), [determinism repro](../repro/qwen36-27b-autoround-int4-b70-determinism-20260818/README.md) |
| 27B Q4_0 DFlash | [closure](../notes/2026-07-13-qwen27-dflash-sycl-closure.md) |
| 27B intrinsic-MTP Q4 | [result packet](../results/qwen36-27b-mtp-gguf-q4-b70/README.md) |
| 35B Quark W8A8 INT8 | [result packet](../results/qwen36-35b-quark-int8-b70/README.md) |

The current Q8 TP2 record remains `35.699225 tok/s` conventional with 12/12
cold exact outputs and cache zero. Its 2026-08-14 post-record pass promoted no
replacement; use its handoff rather than interpreting individual experiment
notes as active configuration.

The AutoRound INT4 row is a separate model/runtime identity from Q8_0. Its
historical July result remains reproducible evidence under the original bar,
but the newer six-start contribution-style review does not promote it under
the current bar: four speculative arms centered at `98.766 tok/s` across 25
prompts, while all four differed from target-only on 25/25 prompts and fresh
same-pair restarts were not token-exact. Do not select the lone `101.078`
arm or combine this result with the Q8_0 lane.

The later dependency and RMSNorm bisections are also nonpromotable. Small
warmed canaries matched their then-sealed controls above `100 tok/s`, but the
final matched-source RMSNorm 25-prompt candidate was only 12/25 exact at
`93.445681 tok/s`. Use the closeouts above rather than treating either bounded
canary as a reproduction recipe.

## Historical Production Recipes

This section is historical. `CURRENT.md` is the operational authority and
requires a fresh process/listener check. The temporary LAN endpoint recipe
described here was the Gemma 4 26B Q8 coding-agent service:

- model: `gemma4-26b-a4b-q8`
- local target model:
  `/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf`
- hardware: 4x Intel Arc Pro B70 32GB
- engine: llama.cpp/SYCL replicas plus no-auth OpenAI frontdoor
- endpoint: OpenAI-compatible API on `0.0.0.0:8000`
- served context: `65536` tokens per active request
- max active generations: `8`
- prompt cache: enabled with strict sticky routing available
- modalities: text
- auth: none

Restore or stop it from
`docs/gemma4-26b-q8-service-runbook.md`.

The usual model-slot production profile to restore after this temporary service
is the Gemma 4 c8 profile:

- model: `Intel/gemma-4-12B-it-int4-AutoRound`
- local model path used in the lab: `/mnt/fast-ai/llm-models/gemma4-12b-it-int4-autoround-intel`
- hardware: 4x Intel Arc Pro B70 32GB
- engine: vLLM/XPU TP4
- endpoint: OpenAI-compatible API on `0.0.0.0:8000`
- served context: `32768`
- max active generations: `8`
- prefix caching: enabled
- modalities: text and image
- auth: none

Restore production Gemma 4 c8:

```bash
cd /home/steve/llm-optimizations
printf '%s\n' "/'" | sudo -S -p '' \
  scripts/switch-vllm-model-slot.sh switch gemma4-12b-it-int4-autoround-c8
```

Current Gemma 4 recipe and results:

- `../experiments/gemma4-12b-int4-autoround-vllm/README.md`
- `../experiments/gemma4-12b-int4-autoround-vllm/results-20260607-c10-c12-32k-boundary.json`
- `model-slot-switching.md`

Latest full-32K concurrency conclusion:

- Keep c8 as production for website-sized requests that need the 32K window.
- c10 is research-only: short prompts improved in aggregate, but near-32K
  throughput did not improve and TTFT worsened.
- c12 is rejected after Level Zero out-of-resources/device-lost under burst
  load.
- Prefix caching is useful for fixed system/project prefixes plus unique user
  content. In the half-shared synthetic test, c8 near-32K TTFT improved from
  about `22.20 s` to `12.45 s`.

## Qwen3.6 27B Q8_0 One-B70 Baseline

The target-only Unsloth Q8_0 GGUF now has a validated one-card baseline and a
32K F16-KV capacity/quality gate. The correctness-qualified default disables
the archived runtime's DNN selector while retaining the broader SYCL
optimization path. It measured `15.550257 tok/s` median on the 12-prompt
128-token exact suite, fully offloaded `65/65` layers, used `28,372 MiB` at
32K, and passed exact retrieval at 4,369 / 17,274 / 31,846 prompt tokens.

Start with:

- `../experiments/qwen36-27b-q8-gguf-b70/STRATEGY.md`;
- `../experiments/qwen36-27b-q8-gguf-b70/README.md`;
- `../experiments/qwen36-27b-q8-gguf-b70/data/baseline-summary-20260808.json`;
- `../experiments/qwen36-27b-q8-gguf-b70/notes/2026-08-08-one-b70-baseline-and-dnn-exactness.md`;
- `../experiments/qwen36-27b-q8-gguf-b70/notes/2026-08-08-four-replica-functional-smoke.md`;
- `../experiments/qwen36-27b-q8-gguf-b70/notes/2026-08-10-canonical-q8-c2-crossover-no-effect.md`;
- `../experiments/qwen36-27b-q8-gguf-b70/notes/2026-08-10-near32k-ubatch-screen.md`;
- `../experiments/qwen36-27b-q8-gguf-b70/notes/2026-08-10-vdr2-vdr4-short-crossover.md`;
- `../experiments/qwen36-27b-q8-gguf-b70/notes/2026-08-10-formal-c2-near32k-vdr2-functional-pass-performance-fail.md`;
- `../experiments/qwen36-27b-q8-gguf-b70/notes/2026-08-10-embedded-mtp-short-diagnostic-advance.md`;
- `../experiments/qwen36-27b-q8-gguf-b70/notes/2026-08-10-embedded-mtp-realistic-suite-matched-control-pass.md`;
- `../experiments/qwen36-27b-q8-gguf-b70/notes/2026-08-10-embedded-mtp-crossband-four-service-recovery-closeout.md`;
- `../experiments/qwen36-27b-q8-gguf-b70/notes/2026-08-08-four-gpu-optimization-and-c2-plan.md`.

The official isolated short full-512 c1 packet now passes and has an exact
same-card repeat: about `156.9 tok/s` PP, `27.7 s` TTFT, and `15.07 tok/s`
through token 512. It is a correctness-qualified baseline, not a new
LocalMaxxing record. Keep DNN disabled: the DNN-on control retained speed but
failed temperature-zero replay exactness. The validated reference remains 32K
F16 KV. The durable strategy maintains a Pareto frontier across prompt
processing, decode, context, concurrency, quality, and stability, using
adaptive research cycles rather than a fixed experiment sequence.

F16 c2/32K now has a measured one-card fit at `30,570 MiB` loaded with
`1,814 MiB` free, full `65/65` offload, and true M=2 occupancy. The synchronized
forced streams contain the complete correct answer prefixes, while later
sequential natural-stop probes pass; a synchronized natural-stop pair is not
yet measured. Its forced-512 cross-mode gate fails only beyond those answer
prefixes: prompt reversal moved the alternate continuation with slot 1. A
replicated four-card compact matrix then made duplicate-B exact in both slots
while swapped B+A matched the historical A/slot-1 stream prefix on two cards
through generated token 128, including the 33-token divergent suffix after the
95-token common
prefix. This establishes replicated workload-sensitive, slot-1-associated
forced-tail behavior. A c2 performance score is therefore not promoted. Two
later sealed waves completed the fixed A/B matrix: A+A and
B+B were exact in both slots, while both heterogeneous directions reproduced
the first slot-1 split immediately after the separately measured boundary. The
forward B tail was repeatable on each fixed lane but differed between GPU 1 and
GPU 3 after the shared token-71 split; physical card remains confounded with
launch ordinal, readiness age, port, and request epoch. The canonical
single-column MMVQ plus recurrent-output DMMV control subsequently completed a
sealed two-wave same-card crossover and classified `NO_EFFECT`: all four ON and
all four OFF lanes reproduced B71/A96 without pre-boundary regression. GPU 0's
later forward tail differed across selector states, so this is not complete
ON/OFF output equality. The forced-512 packet is diagnostic-only and closes
that source lane without a natural-stop or performance claim. The optional stretch ladder
treats Q8 KV as a separate quality
identity and tests c1 at 64K, 100K, and 128K; MTP and vision are also separate
identities. See
`../experiments/qwen36-27b-q8-gguf-b70/notes/2026-08-08-context-concurrency-mtp-vision-plan.md`.

The four-process 4K topology and later full-512 four-band functional wave are
validated, but their concurrent timings remain diagnostic. The compact c2
matrix and canonical-Q8 crossover are also sealed diagnostic evidence. The
current speed lead is a balanced four-card same-card near-32K screen of
`-ub 128 -> 1024`: mean PP improved `155.2815 -> 622.1037 tok/s`
(`4.0063x`), TTFT improved `205.0883 -> 51.1965 s`, and natural 94-token
decode stayed flat at about `12.78 tok/s`. All eight cache-zero runs were
retrieval-exact, fully offloaded, clean, and output-identical. They remain
`legacy-validation`, `performance_promotable=false`. The subsequent official
isolated GPU-0 near-32K full-512 packet passes with `PASS_ORACLE_EXACT`, exact
intrinsic/result/post-canary gates, full offload, and clean teardown. At
`-ub 1024`, median PP is `629.2050 tok/s`, TTFT `50.6598 s`, conventional
tokens 1--100 decode `12.6475 tok/s`, and conventional tokens 1--512 decode
`12.6433 tok/s`. Its official isolated short full-512 guard also passes exact
oracle, intrinsic/result/post-canary, offload, and cleanup gates, with
`605.8453 tok/s` PP, `7.1909 s` TTFT, and `15.0835 tok/s` full-window decode.
Bank only the scoped short and near-32K PP/TTFT rows; both decode targets remain
unmet.

The middle `-ub 1024` packet is `FAIL_ORACLE_EXACT`: row 1 is exact, while row
2 has a 92-token common prefix and first differs at generated token 93
(candidate `90`, oracle `71093`). Its requested JSON remains semantically
correct and stream/replay exactness passes, but its performance is diagnostic
only and no completion marker was emitted. A subsequent same-GPU `-ub 128`
control passed and both rows exactly matched the old GPU-1 oracle, attributing
the divergence to the ubatch treatment rather than card or epoch. Therefore
`-ub 1024` is not a broad default; no further ubatch integration gate is
pending.

The subsequent balanced two-wave, same-card VDR2/VDR4 short full-512 screen
established the current decode direction. VDR2 improved D100 by
`1.09849x--1.10087x` and D511 by `1.09846x--1.10081x` on every B70, while
same-card PP and TTFT ratios stayed within `0.99551--1.00296` and
`0.99676--1.00473`. All eight lanes passed exact oracle,
intrinsic/result/post-canary, cache-zero, full-offload, runtime-binding, and
cleanup gates. The concurrent screen remains `parallel-functional-screen`,
`performance_promotable=false`; it is not an official score. The follow-up
official isolated GPU-0 VDR2 packet is `PASS`, `evidence_valid=true`, and
`performance_promotable=true`. Both rows are full-512 oracle/intrinsic/result/
post-canary exact with cache zero, `65/65` offload, and clean teardown. Against
the official isolated VDR4 short baseline, VDR2 measured D100
`16.5871550224 / 15.0812900263 = 1.09985x`, conventional D511
`16.5889072472 / 15.0835290852 = 1.09980x`, and legacy D512
`16.6211250758 / 15.1128678281 = 1.09980x`; PP and TTFT remained neutral.
The official isolated cross-band guards also pass. Middle retains the required
`-ub 128` and measures D100 `15.1381732549 / 13.8696711812 = 1.09146x`
and D511 `15.0772808986 / 13.8194229005 = 1.09102x`; near-32K retains
`-ub 1024` and measures D100 `13.6894526174 / 12.6475080195 = 1.08238x`
and D511 `13.6861593539 / 12.6432505506 = 1.08249x`. PP and TTFT remain
neutral in both bands. Both packets are official/promotable, full-512 exact,
cache-zero, fully offloaded, post-canary exact, and clean. Bank VDR2 at short
`-ub 1024`, middle `-ub 128`, and near-32K `-ub 1024`, with an
`8.2%--10.0%` decode improvement. D511 remains below `18 tok/s` throughout;
this advanced to a balanced VDR1 screen against banked VDR2. See
`../experiments/qwen36-27b-q8-gguf-b70/data/goal1-c1-c2-scorecard-20260809.json`
and
`../experiments/qwen36-27b-q8-gguf-b70/notes/2026-08-10-vdr2-vdr4-short-crossover.md`.

That balanced two-wave, same-card VDR1/VDR2 short screen is now a durable
exact negative. All eight lanes passed oracle/intrinsic/result/post-canary,
cache-zero, full-offload, runtime-binding, artifact-manifest, and cleanup
gates. VDR2 arm means were D100 `16.546098`, D511 `16.537322`, and legacy D512
`16.569407 tok/s`; VDR1 means were `14.361036`, `14.320120`, and
`14.347969 tok/s`. Median same-card VDR1/VDR2 ratios were `0.868858` D100
(`-13.1142%`), `0.866553` D511 (`-13.3447%`), and `0.866555` legacy D512;
zero of four cards favored VDR1 on any decode view. PP `1.000334x` and TTFT
`0.999569x` were neutral. The screen remains
`parallel-functional-screen`, `performance_promotable=false`; reject and
close VDR1 and retain VDR2. The scorecard and VDR chronology above bind the
complete two-wave packet.

The subsequent all-VDR2 four-service short screen completes the service-scaling
goal. A direct `2026-08-10T06:23:27Z` snapshot observed all four listeners and
task-0 decode concurrently, with server-log mtimes within `2.8 s`. All four
lanes passed full-512 exactness, canary, cache-zero, full-offload,
runtime-binding, artifact, and cleanup gates. Aggregate D100 was
`66.193839 tok/s` (`99.7667%` of ideal four-times isolated), D511
`66.197483 tok/s` (`99.7617%`), legacy D512 `66.326092 tok/s` (`99.7617%`),
and PP `2414.184 tok/s` (`99.5843%`). This is essentially linear scaling for
four independent services, not same-server concurrency. It remains
`parallel-functional-screen`, `performance_promotable=false`.

The later sealed formal GPU-0 VDR2 near-32K c2 packet is valid functional and
negative performance evidence. Both simultaneous 512-token streams exactly
match the fresh sequential phase; selected natural-stop retrieval, local and
external canaries, cache-zero, `65/65` offload, true M=2 occupancy, and cleanup
pass. Aggregate PP is `598.149228 tok/s`, but aggregate D511 is only
`10.144217 tok/s`; per-request D511 is `5.185072 / 10.391849 tok/s` and
fairness is `0.498956`. The primary `30` aggregate / `13` each and stretch `35`
aggregate / `16` each targets fail. Bank the functional PASS and honest
performance FAIL as the ordinary-c2 comparator; do not claim the per-card or
eight-slot serving objective or rerun the unchanged recipe.

The separate integrated publisher-MTP identity has now cleared a scoped fixed
cold realistic-suite gate. Its pinned 29,047,084,160-byte artifact is revision
`5cb35eb3dcbf52dbce5f87dbc64df6aaffadcace`, SHA-256
`9408dcb356cc061a05c139e5647cbde0698ff980c6a69f7fc214e9989f86cfa8`.
The preceding two-prompt confirmation remains
`official-isolated-diagnostic`, `performance_promotable=false`, and is retained
in its focused note rather than being relabeled.

The first realistic-suite run root
`embedded-mtp-vdr2-realistic-gpu0-20260810T100440.907192568Z` stopped safely
when the client assumed the wrong partial verbose `id_slot` sentinel. Its
48-entry manifest `3f2749a3...` verifies, and commit `612f6660d` fixed the
parser. The complete measurement root
`embedded-mtp-vdr2-realistic-gpu0-20260810T101337.129519194Z` also retains its
original `FAIL` and 132-entry manifest `8b0e18c...`: the then-current gate used
an identity-mismatched 4K/128 legacy oracle, which matched only 6/12 32K/512
control prefixes. It does not show context-caused quality loss; prior evidence
favors ubatch sensitivity and exact causality remains unresolved.

An immutable offline supplement at
`offline-supplemental/embedded-mtp-realistic-stale-oracle-final-20260810T101337.KjteSJ`
sealed manifest `d44cef31...`, comparison `41d75481...`, completion
`3eaf8d2c...`, and identity `d966b5d2...` as
`PASS_REALISTIC_MTP_WIN` under `matched_fresh_control_v1`. Candidate and control
full token arrays and content are exact on all 12 prompts. Median D99 is
`36.048707` versus `17.107772 tok/s` (`2.107154x`), matched full-window rate is
`34.545186` versus `17.017022 tok/s` (`2.030037x`), and native rate is
`34.612807` versus `17.050342 tok/s` (`2.030036x`). TTFT is `1.028123x`, the
minimum per-prompt D99 ratio is `1.757122x`, and counters bind 3,709 accepted /
6,448 draft tokens over 2,152 verifications (`0.575217` acceptance,
`1.723513` accepted/verification). Eleven prompts reached 512 tokens;
`customer-email` stopped normally at 248. The scoped one-B70 short result is
realistic-policy valid because every row includes the required generated-token
1/100 timing endpoints for the primary window; ordinary EOS after that window
does not require padding to
512. The hash-bound Q8_0 queue passes local preflight and authenticated server
dry-run. LocalMaxxing approved the final record as
`cmsn6b0bm0074o001uw5f9kod` at `36.04870684253697 tok/s`.

The next two crossover attempts remain important negative evidence. Root
`embedded-mtp-vdr2-crossband-crossover-20260810T120559.307858138Z` failed
before measurement with a BDF `0000:43:00.0` CCS/BCS reset/`-ENOENT`, an
orphaned lifecycle, GPU-3 IGC teardown termination, and a stale 114-entry root
seal. After lifecycle hardening, root
`embedded-mtp-vdr2-crossband-crossover-20260810T122232.328585286Z` failed
closed when child `ZE_AFFINITY_MASK` filtering reindexed devices while
telemetry still requested the global XPU-SMI ordinal; its 92-entry root
manifest `726f4b38...` verifies, but the same window is contaminated by a real
BDF-43 GuC timeout/reset storm. Neither root contains a measurement.

Passive-first recovery used an all-four B70 unbind and `xe` module reload,
without PCI FLR or reboot. The frozen
`recovery/xe-reload-20260810T0833.fxkD91` packet passes four-device BDF/UUID
mapping and idle gates, peer access, four per-card compute smokes, four-rank
XCCL all-reduce, an exact isolated VDR2 generation canary, clean journal, and
final cleanup. Its root manifest/summary/completion hashes are
`a898b658... / 666aa472... / c2810643...`; no B70/xe fault followed reload.

The recovered two-wave same-card crossover at
`embedded-mtp-vdr2-crossband-crossover-20260810T125036.354085966Z` passes as
`PASS_CROSSBAND_MTP_RETENTION_WIN`. Middle keeps `-ub 128` and measures
D99/D511 ratios `2.784953x / 2.962436x`; near-32K keeps `-ub 1024` and measures
`2.899193x / 3.036799x`. All eight arms pass two full-512 scored rows plus
replay, same-card control/MTP token/content equality, cache-zero, full-offload,
counter, overlap, and cleanup gates. Manifest/comparison/completion hashes are
`40e8892a... / 53d739a2... / 1e791ec0...`. This remains a nonpromotable,
non-LocalMaxxing `parallel-functional-screen`.

The subsequent three-wave four-service realistic gate at
`embedded-mtp-four-service-realistic-20260810T131718.247962407Z` also passes.
Each B70 hosts one independent `-c 32768 -np 1` integrated-MTP service. All 12
rows pass the sealed retained-position exactness policy and are cache-zero;
four-way overlaps are `8.747546 / 15.359000 / 15.232755 s`. Aggregate D99 is
`139.098563 tok/s` (`1.003634x` of the prompt-balanced isolated reference),
full-window rate is `136.884848 tok/s` (`0.998850x`), and normalized fairness
is `0.970874 / 0.976385`. Manifest/gate/completion hashes are
`e9329ff9... / c91df0d9... / bc2aa4e2...`. This packet is also nonpromotable
and non-LocalMaxxing; it proves four one-slot services, not c2, eight slots, or
production.

Full integrated-MTP c2/32K remains a fit `NO-GO`: measured one-slot residency
is `29,911 MiB`, while the second target/draft KV and recurrent allocations
project about `32,683 MiB` before useful headroom. Do not launch the unchanged
shape or use CPU offload to obscure the miss. The next bounded work is
turnover/durability, isolated reproduction where needed, and production
routing/lifecycle generalization. Keep the sealed ordinary VDR2 c2 functional
PASS/performance FAIL as the honest comparator.

## Historical Qwen3.6 27B Optimization Lane

Qwen3.6 27B INT4 AutoRound was a prior optimization target, separate from the
production LAN endpoint:

- current fastest variant: `webhie/Qwen3.6-27B-int4-AutoRound`
- webhie revision: `f5750c90b3776db658594df5fe8051098226dd8e`
- prior Intel reference: `Intel/Qwen3.6-27B-int4-AutoRound`
- Intel revision: `abc86de19eb1ebbf6a7df4582341325c22ddcb7d`
- hardware: one Intel Arc Pro B70 32 GB for the TP1 reference and two B70s for
  the current TP2 record
- engine: local vLLM/XPU from `/home/steve/src/vllm`
- current strict fresh-response historical best: TP2 median
  `95.384868 tok/s` for generated tokens 1-100 after TTFT under the July 2026
  metric. Pinned public oneCCL/libccl fixes the installed runtime's
  deterministic packed-verifier all-reduce corruption, a compiled all-gather
  custom op enables exact draft graph capture, graph-safe FlashAttention
  permits one full four-row target graph, and exact ReplaySSM pending-metadata
  plus direct-core-output transaction fusions complete the record path. Exact
  cases, repeat128, baseline parity, the 1K needle, and `cached_tokens=0` on
  every strict prompt passed. Both assignments in a swapped four-GPU
  crossover favored the candidate (`95.332 vs 87.901`, then
  `94.523 vs 93.685 tok/s`).
- current result packet:
  `../results/qwen36-27b-autoround-int4-b70/tp2-fp16-fullgraph-transaction-20260711.json`
- exact standalone repro, including private source bundles and original run
  directories:
  `../repro/qwen36-27b-autoround-int4-b70/README.md`
- current TP2 LocalMaxxing: `cmrh35ct50092mj01h7jgydqj`; prior full-graph
  row `cmrgue7kl007pmj01yrkcyqmv`; prior FP16 approval
  `cmrgojixq005rmj0141e9fjj2`
- graph-safe FA build/oracle/repro:
  `../experiments/qwen27_graphsafe_flash_attention/README.md`
- prior TP1 LocalMaxxing: ReplaySSM draft-INT4 row approved as
  `cmr9atqb800msqr01u760xh0t`, with queue/response at
  `../experiments/qwen36-27b-autoround-int4-b70/localmaxxing/qwen36-27b-webhie-int4-int8lmhead-bf16scale-draftint4-replayssm-current-confirm-20260706.queue.json` and
  `../data/localmaxxing-responses/qwen36-27b-webhie-int4-int8lmhead-bf16scale-draftint4-replayssm-current-confirm-20260706.submit.log`;
  previous BF16-scale row `cmr5iu3gk00bfq901nidgcana`; prior webhie INT8 row
  `cmr576apv0079q901i6dvsh0l`; prior Intel INT8 row `cmr4zkcxb003yq9018408i1pn`
- prior TP1 result packet:
  `../results/qwen36-27b-autoround-int4-b70/webhie-int8lmhead-bf16scale-draftint4-replayssm-current-confirm-20260706.json`
- TP1 current-source attribution/reconfirmation packet:
  `../results/qwen36-27b-autoround-int4-b70/tp1-draftgraph-attribution-reconfirm-20260711.json`.
  The valid historical high remains `68.236 tok/s`; July 11 isolated rows
  reproduced `65.359`, `66.716`, and `65.420 tok/s`, with complete quality on
  the first. A swapped four-GPU graph/eager draft crossover was flat at
  `-0.05%`, closing the TP2 draft-graph transfer as a TP1 speed idea.
- previous BF16-scale packet:
  `../results/qwen36-27b-autoround-int4-b70/webhie-int8-lmhead-bf16scale-20260703.json`
- prior webhie INT8 packet:
  `../results/qwen36-27b-autoround-int4-b70/webhie-int8-lmhead-20260703.json`
- prior Intel INT8 packet:
  `../results/qwen36-27b-autoround-int4-b70/int8-lmhead-20260703.json`
- BF16-LM-head baseline best: `53.522 tok/s`, LocalMaxxing
  `cmr4gokx90061nv01lhoe3ft8`
- handoff:
  `../results/qwen36-27b-autoround-int4-b70/HANDOFF.md`
- repro:
  `../repro/qwen36-27b-autoround-int4-b70/README.md`
- service / prompt-processing ladder:
  `../experiments/qwen36-27b-autoround-int4-b70/notes/2026-07-04-long-context-ladder-baseline.md`.
  This is separate from the short-decode headline. The current 32K-capability
  anchor uses `MAX_MODEL_LEN=32768`, exact cold JSON retrieval, `cached_tokens=0`,
  and reaches `17706` actual prompt tokens with TTFT median `22.443s`,
  approximate prefill median `224.67 tok/s`, and after-TTFT short-output median
  `60.19 tok/s`. For production-visible OpenAI `content`, set
  `QWEN36_27B_REASONING_PARSER=`; the no-parser 32K content check passed the
  same exact retrieval gate with all rows streaming visible content deltas.

## Laguna S 2.1 INT4 Qualified Published Result

The current four-B70 Laguna row is approved at **`125.461973164 tok/s`** under
conventional 99-inter-token-interval accounting; the same timestamps produce
`126.729265822 tok/s` under the historical compatibility formula. The fixed
suite used BF16 KV, exact width 12, DFlash depth 11, audited 146/145 target and
14/13 draft graphs, decode GRF128 with transposed BF16 scales, exact Q/K
RMSNorm+RoPE, and exact M12 shared elementwise fusions. All 13 prompts were
token-and-text exact against the canonical q1 teacher and cache-zero, with
selector evidence on all four ranks. LocalMaxxing approved the record as
`cms9wuuf300cqpm01t5i285tq`.

Use:

- [record resume](../experiments/laguna-s-2.1-xpu-b70/RESUME.md);
- [qualified result packet](../results/laguna-s-2.1-int4-b70/README.md);
- [current record evidence](../experiments/laguna-s-2.1-xpu-b70/notes/2026-07-31-shared-elementwise-m12-record.md);
- [current structured packet](../data/laguna-shared-elementwise-m12-record-20260731.json);
- [current standalone repro](../repro/laguna-s-2.1-int4-b70-125tps-20260731/README.md);
- [older standalone repro](../repro/laguna-s-2.1-int4-b70-102tps-20260726/README.md);
- [source/runtime reconstruction and reproducibility tiers](../repro/laguna-s-2.1-int4-b70-102tps-20260726/BUILD.md);
- [accounting correction](../experiments/laguna-s-2.1-xpu-b70/notes/2026-07-26-throughput-window-accounting-correction.md);
- [record note](../experiments/laguna-s-2.1-xpu-b70/notes/2026-07-26-width12-dflash-fp8-w8a16-record.md);
- [structured packet](../data/laguna-s-2.1-width12-dflash-fp8-record-20260726.json);
- [source snapshots](../patches/laguna-s-2.1-xpu-b70/README.md);
- [campaign transfer ledger](../experiments/laguna-s-2.1-xpu-b70/notes/2026-07-26-campaign-transfer-ledger.md);
- [KV-cache precision decision](../experiments/laguna-s-2.1-xpu-b70/notes/2026-07-26-kv-cache-precision-decision.md).

The record uses BF16 KV to preserve its BF16 canonical-teacher contract.
Poolside's quantized checkpoint officially specifies calibrated FP8 KV, which
has a paused, separately labeled experiment under
[`experiments/laguna-s-2.1-fp8-kv-xpu-b70/`](../experiments/laguna-s-2.1-fp8-kv-xpu-b70/).
It has its own source patches, checkpoint/runtime scale audit, FP8 q1 teacher,
and promotion gates; it is not a silent record-lane substitution.

The repro tracks the sealed raw benchmark, log, environment, cleanup, and idle
evidence; portable release-only model hashes; the complete observed runtime;
and every direct or transitively loaded native library. Exact lab replay and a
source-equivalent clean rebuild are separate claims: a rebuild with different
binary hashes is a new environment and must pass all semantic, topology,
teardown, and performance gates.

## DeepSeek V4 Flash K160 Closed Frontier

The four-B70 DeepSeek V4 Flash experimental uniform-K160 lane is paused. Its
best verified one-active-generation result is `80.820052 tok/s` with
target-verified DSpark7; three independent strict medians were `80.820052`,
`76.900178`, and `78.287226 tok/s`. All 36 realistic rows were cache-zero and
24/24 ordered exact canaries passed. LocalMaxxing approved
`cmrquta9905w3lg013m5vxoqx`.

Use the [closed result packet](../results/deepseek-v4-flash-k160-b70/README.md)
and [standalone pinned repro](../repro/deepseek-v4-flash-k160-b70-80tps-20260718/README.md).
The recipe includes exact source bundles because the measured vLLM, XPU
kernel, and oneCCL commits are local experimental history rather than upstream
commits. The K160 artifact is hash-pruned and its calibration/ranking is not
reproducible, so this record applies only to that explicitly labeled artifact.

## MiniMax Deployable Baseline

The MiniMax 32K FP16-family KV c1 endpoint remains the deployable baseline
recipe and optimization reference:

- model: `Lasimeri/MiniMax-M2.7-int4-AutoRound`
- local model path used in the lab: `/mnt/fast-ai/llm-models/minimax-m2.7-int4-autoround`
- hardware: 4x Intel Arc Pro B70 32GB
- engine: vLLM/XPU TP4
- endpoint: OpenAI-compatible API on `0.0.0.0:8000`
- served context: `32768`
- max active generations: `1`
- default KV: `auto` / FP16-family

Fresh install guide:

`../repro/minimax-m27-b70-110tps-ubuntu24-20260523/README.md`

Human deployment guide:

`b70-minimax-ubuntu24-deployment.md`

Main server script:

`../repro/minimax-m27-b70-110tps-ubuntu24-20260523/scripts/06-serve-openai-compatible.sh`

Operational profile switcher:

`../experiments/minimax_xpu_kv_offload/scripts/switch_session_cache_profile.sh`

Restore c1:

```bash
cd /home/steve/llm-optimizations
experiments/minimax_xpu_kv_offload/scripts/switch_session_cache_profile.sh c1
```

Check status:

```bash
experiments/minimax_xpu_kv_offload/scripts/session_cache_status.sh
```

## Gemma 4 26B Realistic-Suite Observation

The current Gemma 4 26B A4B Q8 single-B70 realistic-suite observation is
documented in the result packet:

`../results/gemma4-26b-a4b-q8-b70/reproduce.md`

Current handoff and production backend recipe:

- `../results/gemma4-26b-a4b-q8-b70/HANDOFF.md`
- `../results/gemma4-26b-a4b-q8-b70/production-service.md`
- `gemma4-26b-q8-service-runbook.md` for restoring the temporary
  OpenAI-compatible coding-agent endpoint on one or four B70 GPUs
- backend launcher:
  `../scripts/serve-gemma4-26b-q8-production.sh`
- health/smoke:
  `../scripts/gemma4-26b-prod-health.py`

This is a localhost llama.cpp backend recipe, not the current public `:8000`
systemd frontdoor profile. The tracked systemd unit
`../deploy/systemd/gemma4-26b-q8-llamacpp.service` starts the backend on
`127.0.0.1:19350`; wire the frontdoor to that backend only after smoke passes.

Standalone current repro:

`../repro/gemma4-26b-a4b-q8-b70-125tps-20260701/README.md`

Use it when the goal is to reproduce the current fixed-suite cold-response
frontier rather than the older synthetic filled-long diagnostics. The older
standalone
`../repro/gemma4-26b-a4b-q8-b70-95tps-20260624/README.md` folder remains as a
superseded `95.264 tok/s` reproduction artifact.

Record identity:

- model: `unsloth/gemma-4-26B-A4B-it-GGUF`, `UD-Q8_K_XL` target
- draft: local `Q4_0` Gemma MTP draft only
- hardware: headless Supermicro AMD Threadripper PRO 5955WX platform, 128 GB
  DDR4, one Intel Arc Pro B70 32 GB used for the measured replica
- result: best strict result `124.97714084813418 tok/s` median
  generated-token throughput for tokens 1-100 after TTFT across the fixed
  realistic cold prompt suite, `cached_tokens=0` on every prompt,
  `realistic_final_gate.passed=true`.
  Evidence:
  `../data/gemma4-q8-gpu0-finalpostnorm-reproexact-full512-20260701T084728Z/summary.json`.
  Config: llama.cpp `c926ad098`, reordered-Q8 VDR2, `FLASH_ATTN=on`,
  `CTX_SIZE=32768`, `GGML_SYCL_ENABLE_VMM=1`, `n_max=3`, `n_min=2`,
  `p_min=0.0475`, `UBATCH_SIZE=1024`,
  `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`,
  `LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`,
  `LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2=1`,
  `LLAMA_GEMMA4_FUSED_FINAL_POST_NORM_RESIDUAL=1`,
  `--ctx-checkpoints 0`, no n-gram/history acceleration.
  This is the current submitted VDR2 selected-down fused weighted-sum plus
  FA-on 32K/VMM plus final post-norm residual fusion row, approved under the
  realistic-suite policy as `cmr1u77na01k2ld01kalwzs1e`. Same-family support
  includes the prior `123.67689864739785 tok/s` row
  (`cmr01nnet000mld01x2tt6qds`), the prior `121.41411987308553 tok/s` row
  (`cmqztiqdn02vnoe01egox6q3f`) and
  `../data/gemma4-q8-gpu2-baseline-recordconfirm-full512-20260629T225215Z/summary.json`
  at `119.94842631460949 tok/s`. Earlier selected-down rows
  `cmqyrpox4021dqk01co5o4fcw` and `cmqyo0jyt08ippk01vhiobdnm`, prior
  `98.34046474459183`, `95.82453787677183`, VDR2 `90-91`, and VDR4
  `87.61145306230438` submissions are superseded.
  The old `176.216232 tok/s` synthetic filled-long row remains diagnostic only
  and is not representative real-world throughput.
- primary artifacts:
  `../data/gemma4-q8-gpu0-finalpostnorm-reproexact-full512-20260701T084728Z/summary.json`,
  `../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260701-finalpostnorm-reproduction-check.md`,
  `../data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-realistic-finalpostnorm-faon-vmm-ctx32768-full512-124tok-20260701.submit.log`,
  `../data/gemma4-q8-gpu0-finalpostnorm-on-full512-20260630T024027Z-finalpost-full512/summary.json`,
  `../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-final-postnorm-fusion-screen.md`,
  `../data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-realistic-finalpostnorm-faon-vmm-ctx32768-full512-123tok-20260630.submit.log`,
  `../data/gemma4-q8-gpu1-selecteddown-bf16retest-control-full512-20260629T051323Z/summary.json`,
  `../results/gemma4-26b-a4b-q8-b70/20260629-vdr2-selected-down-record.md`,
  `../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260629-record-repeat-full512-variance.md`,
  `../data/gemma4-q8-gpu1-strict-vdr2-f16p021-bulksampled-confirm-B-n3-nmin2-p00475-ub1024-full512-20260628T052158Z/summary.json`,
  `../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260628T0245-crack100-runtime-sweeps.md`,
  `../data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-realistic-vdr2-mtp-n3-nmin2-p00475-ub1024-f16p021-bulksampled-full512-20260628.submit.log`,
  `../data/gemma4-q8-gpu1-strict-vdr2-f16p021-smallncols-full512-exactconfirm-n3-nmin2-p00475-ub1024-20260628T010121Z/summary.json`,
  `../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260628T0047-strict-f16p021-smallncols-record.md`,
  `../data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-realistic-vdr2-mtp-n3-nmin2-p00475-ub1024-f16p021-smallncols-full512-20260628.submit.log`,
  `../data/gemma4-q8-gpu1-strict-vdr2-recordconfirm-n3-nmin2-p00475-ub1024-20260627T221722Z/summary.json`,
  `../data/gemma4-q8-gpu2-strict-vdr2-n3-p00475-repeat-ub1024-v21-20260627T201757Z/summary.json`,
  `../data/gemma4-q8-gpu2-strict-vdr2-n3-p00475-ub1024-v19-20260627T191931Z/summary.json`,
  `../data/gemma4-q8-gpu0-strict-vdr2-repeat-n3-p005-ub1024-v19-20260627T191931Z/summary.json`,
  `../data/gemma4-q8-gpu0-strict-vdr2-n3-p005-ub1024-v18-20260627T191648Z/summary.json`,
  `../data/gemma4-q8-gpu1-strict-vdr2-th6-n3-p005-ub1024-v18-20260627T191648Z/summary.json`,
  `../data/gemma4-q8-gpu2-strict-vdr2-dth16-n3-p005-ub1024-v18-20260627T191648Z/summary.json`,
  `../data/localmaxxing-gemma4-26b-a4b-q8-b70-llamacpp-realistic-vdr2-mtp-n3-nmin2-p00475-ub1024-v19-20260627.queue.json`,
  `../data/localmaxxing-responses/gemma4-26b-a4b-q8-b70-llamacpp-realistic-vdr2-mtp-n3-nmin2-p00475-ub1024-v19-20260627.submit.log`,
  and
  `../repro/gemma4-26b-a4b-q8-b70/realistic-suite-v1.json`
- long-context service artifacts:
  `../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-sycl-fattn-dv512-gqa8-prefill-win.md`,
  `../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-long-context-prefill-service-gate.md`,
  `../repro/gemma4-26b-a4b-q8-b70/long-context-suite-v1.json`,
  `../scripts/bench-openai-long-context-suite.py`,
  `../repro/gemma4-26b-a4b-q8-b70/run-vdr2-long-context-service-gate.sh`, and
  `../repro/gemma4-26b-a4b-q8-b70/run-vdr2-short-decode-guard.sh`. The current
  validated service/prefill patch is
  `../patches/gemma4-26b-a4b-q8-b70/20260630-sycl-fattn-dv512-gqa8-ncols2.patch`
  with `GGML_SYCL_FATTN_DV512_GQA_NCOLS2=8`. Use UB2048 as the balanced
  long-service setting, UB2304 for pure prefill, and keep UB1024 as the
  short-record reproduction setting. The optional KQ register/broadcast service
  flag `GGML_SYCL_FATTN_DV512_GQA8_KQ_REG_BCAST=1` is preserved in
  `../patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-kq-reg-bcast-source.patch`
  and the DKQ576 extension
  `../patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260702-kq-reg-bcast-dkq576-source.patch`;
  it is documented as a small service/prefill win in
  `../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260702-global-fattn-kq-reg-bcast-dkq576-service-win.md`
  and is not a LocalMaxxing headline decode result. The KV-max mask pre-scan threshold
  diagnostic is preserved at
  `../patches/gemma4-26b-a4b-q8-b70/20260630-sycl-fattn-kv-max-scan-threshold.patch`
  and documented as a negative in
  `../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-sycl-fattn-kv-max-scan-threshold-negative.md`;
  do not disable the scan for this lane. The forced-`ncols1` diagnostic is
  preserved at
  `../patches/gemma4-26b-a4b-q8-b70/20260630-sycl-fattn-dv512-gqa8-ncols1-negative.patch`
  and documented as a negative in
  `../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-sycl-fattn-dv512-gqa8-ncols1-negative.md`;
  keep the GQA8 selector's implicit `ncols1=2` path. The `nbatch_fa=128`
  retune for the selected GQA8 FP16 tile is preserved at
  `../patches/gemma4-26b-a4b-q8-b70/20260630-sycl-fattn-dv512-gqa8-nbatchfa128-negative.patch`
  and documented as a negative/noise result in
  `../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-sycl-fattn-dv512-gqa8-nbatchfa128-negative.md`;
  keep the current `nbatch_fa=64` tile config. Phase-specific prompt/decode
  ubatch is preserved as a service candidate at
  `../patches/gemma4-26b-a4b-q8-b70/20260630-llama-phase-prefill-ubatch-memory-sized-experiment.patch`
  and documented in
  `../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260630-phase-prefill-ubatch-service.md`;
  the reproducible service wrapper is
  `../repro/gemma4-26b-a4b-q8-b70/run-vdr2-gqa8-phase-prefill-service.sh`.
  Use it for service/prefill validation only; short-decode headline submissions
  still use the fixed short record recipe and gate.
- source patch snapshot:
  `../patches/gemma4-26b-a4b-q8-b70/20260626T2225-llamacpp-gemma4-current-record-stack.patch`
  with note
  `../patches/gemma4-26b-a4b-q8-b70/20260626T2225-llamacpp-gemma4-current-record-stack.md`

The full optimization ledger remains in
`../results/gemma4-26b-a4b-q8-b70/README.md`.

## Baseline Build Inputs

The fresh Ubuntu 24 repro builds from source and applies two compressed patch
artifacts from the older strict-speed repro:

- `../repro/minimax-m27-b70-89tps-20260520/patches/vllm-active-promoted-minimax-89tps-20260520.patch.gz.b64`
- `../repro/minimax-m27-b70-89tps-20260520/patches/llm-scaler-active-promoted-minimax-89tps-20260520.patch.gz.b64`

The build script decodes and applies those patches automatically:

`../repro/minimax-m27-b70-110tps-ubuntu24-20260523/scripts/03-build-stack.sh`

Pinned source commits are listed in:

`../repro/minimax-m27-b70-110tps-ubuntu24-20260523/README.md`

Live-source audit snapshots from the originating machine are also tracked:

- `../patches/vllm-live-src-snapshot-20260525.patch`
- `../patches/llm-scaler-live-src-snapshot-20260525.patch`

These snapshots capture the dirty local `/home/steve/src/vllm` and
`/home/steve/src/llm-scaler` trees after the session-cache and TurboQuant
research. Treat them as review/audit artifacts, not as clean upstream-ready
patches. The clean fresh-install repro still uses the two compressed promoted
patch bundles listed above.

## Baseline Results

The fresh deployable baseline records:

- strict p512/n1536 comparable lane: `83.172` output tok/s, `110.896` total tok/s
- OpenAI endpoint warm decode: about `83.8-84.1` output tok/s
- prompt/prefill endpoint check: about `1.7k-1.8k` prompt tok/s
- served context: `32768`
- near-full context smoke: prompt `32408`, output `64`, no OOM

Tracked summaries:

- `../repro/minimax-m27-b70-110tps-ubuntu24-20260523/results/summary-20260523.json`
- `../repro/minimax-m27-b70-110tps-ubuntu24-20260523/results/context-window-32768-20260523.json`
- `../data/localmaxxing-minimax-m27-autoround-openai-32k-context-20260523.payload.json`
- `../data/localmaxxing-minimax-m27-autoround-openai-32k-endpoint-metrics-20260524.payload.json`

Detailed notes:

- `../notes/2026-05-23-b70-display-disable-32768-context.md`
- `../notes/2026-05-23-current-host-pcie4-prefill-check.md`

## Session-Cache / RAM-Backed Juggling

This is the main experimental path for keeping multiple long conversations
warm. It is not one huge active context.

Mental model:

- OpenAI-compatible requests are stateless.
- The client keeps and resends the full conversation history.
- vLLM hashes exact repeated token prefixes.
- CPU KV offload can park/reload those prefix KV blocks through system RAM.
- If old transcript text, system prompts, or chat templates change, prefix
  reuse can be lost after that point.

Entry points:

- `../experiments/minimax_xpu_kv_offload/REPRODUCE.md`
- `../experiments/minimax_xpu_kv_offload/ARTIFACTS.md`
- `../experiments/minimax_xpu_kv_offload/README.md`
- `../experiments/minimax_xpu_kv_offload/notes-20260525-session-cache-operations.md`

Scripts:

- `../scripts/install-minimax-vllm-service.sh`
- `../scripts/openai-lan-frontdoor.py`
- `../scripts/minimax-prod-health.py`
- `../scripts/minimax-prod-benchmark.py`
- `../deploy/systemd/minimax-vllm.service`
- `../deploy/systemd/minimax-openai-frontdoor.service`
- `../experiments/minimax_xpu_kv_offload/scripts/serve_session_cache.sh`
- `../experiments/minimax_xpu_kv_offload/scripts/switch_session_cache_profile.sh`
- `../experiments/minimax_xpu_kv_offload/scripts/session_cache_status.sh`
- `../experiments/minimax_xpu_kv_offload/scripts/session_cache_canary.py`

Current operational recommendation:

- c1 is production. Run it with `minimax-vllm.service` as a localhost backend
  on `127.0.0.1:18080` and `minimax-openai-frontdoor.service` as the no-auth
  LAN OpenAI-compatible endpoint on `0.0.0.0:8000`.
- Latest production-service near-32K LocalMaxxing result:
  `cmpm35jsa0003rt01zghtmwip` for prompt `32264`, output `64`,
  `63.91` output tok/s after TTFT, `1382.57` approximate prefill tok/s,
  `23.336 s` TTFT.
- c2 is the current known-good RAM-backed session-cache profile for two parked
  `32768`-token window sessions.
- c4 is the next target, but live service switching hit blockers.
- c8 is useful for smaller parked sessions but does not increase total decode
  throughput.

Near-full c2 validation:

- two concurrent strict-word sessions
- `32474` prompt tokens per session, `64948` combined prompt tokens
- expected first words matched the GPU-only baseline
- second-pass reload TTFT: `0.668-1.232 s`
- CPU-to-GPU KV reload: about `14-15 GB/s`

Known-good c2 operations smoke:

- two concurrent fact-word sessions
- `22540` prompt tokens per session
- exact output hashes matched across passes
- second-pass reload TTFT: `0.320-0.570 s`
- CPU-to-GPU KV reload: about `16.2 GB/s`

The operations smoke is intentionally smaller and cleaner. It does not define
the desired c2 context ceiling; c2 should be presented as a 32K-window profile.

Result file from the originating host:

`/mnt/fast-ai/bench-results/minimax-m27-b70-serve/session-cache-c2-ops-fact-900lines-20260525T223527Z.json`

The raw `/mnt/fast-ai` file is not in GitHub; the result is summarized in:

`../experiments/minimax_xpu_kv_offload/notes-20260525-session-cache-operations.md`

Concurrency/sustained decode notes:

- `../experiments/minimax_xpu_kv_offload/notes-20260525-c2-session-cache-ladder.md`
- `../experiments/minimax_xpu_kv_offload/notes-20260525-c4-c8-session-cache-ladder.md`
- `../experiments/minimax_xpu_kv_offload/notes-20260525-sustained-concurrency-decode.md`

Headline sustained warm results:

- c4 at four `9234`-token prompts, `128` requested output tokens: about
  `109.76 tok/s` total warmed wall output
- c8 at eight `9234`-token prompts, `128` requested output tokens: about
  `110.34 tok/s` total warmed wall output
- c8 spreads roughly the same decode budget across more sessions; it does not
  double total throughput

Live c4 caveat:

- c4 started and reported `34304` GPU KV tokens
- a later operational smoke stalled on second-pass reload with waiting/deferred
  requests
- a rerun hit Level Zero `UR_RESULT_ERROR_DEVICE_LOST` while copying vLLM
  block-table state to GPU
- keep c4 experimental until this path is debugged

## TurboQuant

TurboQuant is a compressed-KV research lane. It can raise the live KV ceiling,
but it is not the production mode.

Patch artifact:

`../patches/vllm-turboquant-xpu-workspace-fallback-20260525.patch`

Repro script:

`../scripts/repro-minimax-turboquant-xpu-workspace-bug.sh`

Detailed notes:

- `../experiments/minimax_xpu_kv_offload/notes-20260525-c2-quality-and-turboquant.md`
- `../experiments/minimax_xpu_kv_offload/notes-20260525-turboquant-active-context-boundary.md`

Current status:

- the patch works around locked-workspace crashes in
  `turboquant_attn.py:_decode_attention` and `_continuation_prefill`
- `turboquant_k8v4` at 32K reported `80128` GPU KV tokens and `2.45x` max
  concurrency for a 32K request
- strict-word canaries passed at about `8K` and `32.5K` prompt tokens
- sustained decode around a `24874` token prompt was only about `16.5 tok/s`
  after TTFT
- `turboquant_4bit_nc` with `max_model_len=196608` reported `98304` GPU KV
  tokens but still could not serve a true 196K active request

Important boundary:

TurboQuant plus CPU KV offload still requires the active request's working KV
blocks to fit in live GPU memory. It helps capacity, but it is not active-context
overflow.

## Full 196K Active Context Path

The credible exact-quality path is CPU-paged attention, not simply increasing
`--kv-offloading-size`.

Design notes and probes:

- `../experiments/minimax_xpu_kv_offload/notes-20260525-cpu-paged-attention-design.md`
- `../experiments/minimax_xpu_kv_offload/notes-20260525-dense-staged-cpu-attention.md`
- `../experiments/minimax_xpu_kv_offload/notes-20260525-stagea-gpu-split-attention.md`
- `../experiments/minimax_xpu_kv_offload/probes/split_attention_merge_probe.py`
- `../experiments/minimax_xpu_kv_offload/probes/xpu_flash_attn_split_probe.py`
- `../experiments/minimax_xpu_kv_offload/probes/xpu_cpu_dense_staged_attention_probe.py`

Experimental patches:

- `../experiments/minimax_xpu_kv_offload/patches/kv-offload-admission-check-xpu-experiment-20260524.patch`
- `../experiments/minimax_xpu_kv_offload/patches/xpu-cpu-kv-worker-prototype-20260525.patch`
- `../experiments/minimax_xpu_kv_offload/patches/vllm-xpu-gpu-split-attn-stagea-failed-20260525.patch`

Current design direction:

1. Keep recent/current KV in normal GPU KV blocks.
2. Keep older logical KV blocks in CPU offload storage.
3. Stage old CPU-resident KV chunks into GPU scratch.
4. Run attention over each chunk.
5. Merge partial attention outputs using log-sum-exp/LSE state.
6. Merge old-context attention with normal attention over the live GPU suffix.

This is still a research path, not a serving recipe.

## What GitHub Does Not Include

GitHub has:

- setup scripts
- build scripts
- patch artifacts
- benchmark payloads
- LocalMaxxing responses
- summarized results
- notes and runbooks

GitHub does not include:

- model weights
- Hugging Face tokens or other secrets
- the full raw `/mnt/fast-ai/bench-results` tree
- compiled vLLM/llm-scaler build outputs
- Torch/AOT compile caches

When a note references a raw `/mnt/fast-ai` log or JSON, use the summarized
values in GitHub unless you are on the originating machine.
