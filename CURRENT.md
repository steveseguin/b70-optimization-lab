# Current Workspace State

Last reviewed: **2026-08-13**

## Authority And Update Rule

This is the sole cross-repository authority for the loaded service, active
optimization lane, protected work, and immediate next actions. Result packets
own promoted evidence; lane handoffs own detailed resume context; `notes/` owns
chronology. Do not append experiment history here.

Always verify the actual endpoint, relevant processes, and Git status before an
operational change. A runnable recipe or installed service unit does not prove
that its model is currently loaded.

## Live Service

**Recovered and live as of 2026-08-12 21:06 EDT.** The operator-authorized
host reboot completed. Exact four-device BDF/UUID mapping, per-card
copy/compute, the pinned native four-device peer-read, and four-rank XCCL
barrier/all-reduce all passed. The external model volume was remounted at
`/mnt/usb-models`. The incumbent Muse fleet and frontdoor are active, and the
full model/cache-zero code/vision health gate passes in
`data/muse-health-20260812-topk-trace-restore.json`. The invalid overlap
incident remains preserved at
`experiments/muse-glimmer-30b-b70/notes/2026-08-12-parallel-submit-window-xe-wedge.md`.
Production and benchmark launchers now share the canonical exclusive host GPU
lock, including benchmark-child FD inheritance.

The current exact TP4 kernel-campaign best is the BF16 DFlash stack with
batched device-side distributed greedy sampling for both DFlash proposal rows
and target verification rows, local-winner maxloc, committed-prefix-only
DFlash feature processing, and the default-off RMSNorm/scale/residual fusion,
at **`78.952 tok/s`** arithmetic mean across the fixed prose/code/JSON suite.
The final fusion measured `+0.3725%` against the proposal-identical trailing
control and preserved canonical hashes; see
`experiments/muse-glimmer-30b-b70/notes/2026-08-13-rms-mul-add-fusion.md`.
The preceding committed-prefix processing measured `+2.055%`
against pooled adjacent `77.0998 tok/s` controls with identical proposal
counts, acceptance, and canonical hashes. See
`experiments/muse-glimmer-30b-b70/notes/2026-08-13-dflash-committed-prefix.md`.
The preceding target offload step measured
`+6.449%` against pooled adjacent `73.109 tok/s` controls and preserved all
canonical hashes. It also exposed and fixed two retained meta-graph arena
high-water lifetime bugs. See
`experiments/muse-glimmer-30b-b70/notes/2026-08-13-target-batched-greedy.md`.
The underlying DFlash-only batching beat paired unbatched controls by
`+2.267%`, with identical acceptance and canonical hashes. See
`experiments/muse-glimmer-30b-b70/notes/2026-08-13-dflash-batched-argmax.md`.
Reusing the already-materialized local ARGMAX winners instead of rescanning
each vocab shard then measured a further `+1.000%` against pooled controls,
with canonical target outputs but a two-token code acceptance change; see
`experiments/muse-glimmer-30b-b70/notes/2026-08-13-dflash-argmax-reuse-local.md`.
The underlying device-greedy path is default-off, requires `p_min=0`, and
previously beat paired CPU-sampling controls by `+5.368%` at `71.859 tok/s`.
See
`experiments/muse-glimmer-30b-b70/notes/2026-08-13-dflash-tp-greedy.md`.
The preceding promoted stack used default-off parallel per-device host
submission and measured approximately `67.9 tok/s`. Two adjacent A/Bs in
opposite order measured a pooled `+3.89%`, with canonical hashes and within-pair
proposal counts exact. Evidence:
`experiments/muse-glimmer-30b-b70/notes/2026-08-12-meta-parallel-submit.md`.
The production TP2 fleet does not enable this experimental flag. The next
kernel screen, a guarded batch=2 oneDNN gate/up projection, executed and was
exact but measured only `+0.34%`, too small to promote without confirmation.
Non-adjacent attention pairing is unreachable without invalidating graph-arena
lifetimes: Q+gate collides with the live norm output and K/V deliberately reuse
one output address. A measured top-3 mismatch-repair oracle also closes sparse
branching: even three free stale-suffix nodes project to only `83.13 tok/s`
before wider target cost. The honest `>100 tok/s` TP4 objective remains unmet;
further launch-wrapper micro-optimization cannot supply the remaining gap by
itself.

A subsequent exact, full-rank DDTree prefix trace closes tree verification as
a century route on this stack.  Budget 128 improves the impossible
same-round-cost ceiling to `103.16 tok/s`, but can tolerate only `+3.16%`
round cost; measured target-only batch 16 versus 128 time is
`44.48 -> 110.31 ms` (`2.48x`), projecting roughly `50.00 tok/s` before tree
bookkeeping.  See
`experiments/muse-glimmer-30b-b70/notes/2026-08-13-ddtree-full-rank-ceiling.md`.
The only retained tree option is DFlash budget 15 at the unchanged 16-row
target width; its optimistic ceiling is `82.68 tok/s` and it remains gated on
first finding at least `10.73 ms/round` of independent verifier-kernel savings.
The pretrained DSpark equivalent is weaker (`75.24 tok/s`).
The B70 Level Zero lossless memory-compression allocation hint is exact but
round-time neutral (`62.150 / 62.127 / 62.064 ms` candidate/control/candidate),
and the cached-allocation hint is likewise neutral (`62.178 / 62.389 / 62.147
ms` cached/control/cached+compressed).  Both remain default-off.  See
`experiments/muse-glimmer-30b-b70/notes/2026-08-13-level-zero-memory-compression-negative.md`.
The first target-side TP backend-sampling screen reached the SYCL four-rank
global ARGMAX but terminated before a benchmark row. It is retained as the
historical negative in
`experiments/muse-glimmer-30b-b70/notes/2026-08-13-tp-backend-sampling-negative.md`.
The later batched-row retry identified and fixed the two meta-graph lifetime
bugs and promoted the exact target-sampling win described above; do not treat
the earlier failure as the current lane decision.
A fixed-shape native BF16 XMX/DPAS falsification is also closed: despite using
an already-packed duplicate weight, it was `32.2%` slower than oneDNN and
differed in `73,048 / 79,872` F32 elements.  It was not integrated.  See
`experiments/muse-glimmer-30b-b70/native-bf16-gemm/README.md`.

Before this incident, live since 2026-08-11 ~00:10 EDT: the optimized asymmetric Muse Glimmer 30B
BF16 fleet (`muse-glimmer-bf16-fleet.service` +
`muse-glimmer-frontdoor.service`) on `:8000`, model `muse-glimmer-30b-bf16`.
Text lane :19470 (TP2 on the muse-100 P2P build, BF16 DFlash drafter n15 p0.15, 67.2 tok/s json canary);
vision lane :19471 (kquant drafter n6 + mmproj, 33.6 tok/s); frontdoor
modality routing pins image requests to the vision lane. Validated: health
incl. vision, three-color routing canaries, c2 `54.7 tok/s` aggregate.
Campaign record:
`experiments/muse-glimmer-30b-b70/sweeps/20260811-bf16-max-optimization-campaign.md`.
Operator selected BF16 for fine-tune/abliteration readiness. Runbook:
`docs/muse-glimmer-bf16-service-runbook.md`. Earlier the same day the Gemma
quad service was deployed, validated, and retired; it remains restorable via
its runbook. Recheck immediately before any operational change.

The active optimization lane as of 2026-08-10 evening is **Meta Muse Glimmer
30B**, quality-first (lossless BF16 reference per two B70s, UD-Q8_K_XL
near-lossless candidate per two B70s, DFlash drafter in all arms). Entry
point: `experiments/muse-glimmer-30b-b70/README.md`. Runtime:
`/home/steve/src/llama.cpp-muse-glimmer` at clean upstream `030ebb558`.

The prior (now closed and banked) lane was target-only, text-only Qwen3.6 27B Q8_0 GGUF
on one B70. The validated F16-KV reference reaches 32K; the next service target
is two F16-KV 32K slots per card, using all four B70s as independent
optimization lanes. Q8-KV 100K--128K capacity and vision are optional later
lanes. The separate integrated-MTP identity now passes its fixed cold
realistic-suite gate under a matched fresh-control quality reference, but it
must not be mixed into this baseline. The exact
target-only Unsloth artifact is pinned in
[`experiments/qwen36-27b-q8-gguf-b70/model-manifest.json`](experiments/qwen36-27b-q8-gguf-b70/model-manifest.json)
and is size/SHA/GGUF-table verified at
`/mnt/usb-models/models/qwen36-27b-q8-gguf/Qwen3.6-27B-Q8_0.gguf`. The internal
staging copy and abandoned partials were removed after USB verification. Do not
start another downloader into the canonical path. The lane entry point and
offline-validated launcher/gates are in
[`experiments/qwen36-27b-q8-gguf-b70/README.md`](experiments/qwen36-27b-q8-gguf-b70/README.md).
The one-card baseline is now validated: DNN-off/OPT-on reached `15.550257 tok/s`
median on the 12-prompt 128-token exact suite, and the 4K/17K/31,846-token
F16-KV ladder passed at a 32,768-token allocation with `28,372 MiB` loaded.
Q8 KV is unnecessary for the validated 32K reference or planned c2/32K target.
Four independent one-GPU processes are the selected deployment direction,
but the sealed formal VDR2 near-32K c2 packet passes fit/functionality and fails
its throughput/fairness gates, so the eight-request objective is not yet met.
Keep
`GGML_SYCL_ENABLE_DNN=0`: DNN-on retained speed but failed immediate and
suite-level greedy replay exactness. The simultaneous four-replica functional
smoke also passed: all four 4K services were fully resident at `26,573 MiB`,
generated the same sealed output concurrently, and returned cleanly to 43 MiB.
The full-512/c2 measurement foundation is implemented and GPU-validated. The
sealed four-card functional wave passed all 18 rows. The official isolated
short c1 packet then passed and reproduced exactly on the same card at about
`156.9 tok/s` PP, `27.7 s` TTFT, and `15.07 tok/s` through token 512. F16
c2/32K also fits: `65/65` layers offloaded, `30,570 MiB` loaded, and `1,814 MiB`
free with true two-slot occupancy. Both synchronized forced streams contain
the complete correct answer prefixes; later sequential natural-stop probes and
external canaries are exact. A synchronized natural-stop pair remains
unmeasured. The strict forced-512 c1/c2 comparison is blocked: when EOS is
suppressed, the stream in slot 1 diverges only after the complete answer prefix.
Reversing the prompts moved the failure to the other prompt while it stayed in
slot 1. The replicated four-card compact matrix then found duplicate-B exact in
both slots on two cards, while swapped B+A matched the historical A/slot-1
stream prefix through generated token 128, including its 33-token
divergent suffix, on two other cards. This rules out a simple
unconditional slot-1 failure and establishes replicated workload-sensitive,
slot-1-associated forced-tail behavior, with no observed corruption before
the separately measured answer boundaries. Two later four-card waves completed
the fixed A/B matrix: A+A and B+B were exact in both slots, while both mixed
directions reproduced the first slot-1 split one token after the corresponding
boundary. The forward B tail was same-lane repeatable but differed between GPU
1 and GPU 3 after the shared token-71 split; card, launch order, readiness age,
port, and request epoch remain confounded. The default-off combined canonical
per-vector Q8 control passed its component and four-card no-sleep c1 gates,
then completed the preregistered two-wave same-card c2 crossover. The sealed
result is independently `GO` / `NO_EFFECT`: all four selector-on and all four
selector-off lanes reproduced B71/A96 without a pre-boundary regression, so
canonical single-column MMVQ plus recurrent-output DMMV did not repair the
behavior and that source lane is closed. GPU 0's later forward forced tail
differed between selector states, so do not claim complete ON/OFF output
equality. The packet is forced-512 diagnostic evidence only, with no
natural-stop or performance claim.

The next prompt-processing screen produced the first large speed lead in this
lane. A balanced two-wave, same-card four-B70 comparison at 31,846 prompt tokens
changed only `-ub 128 -> 1024`: mean approximate PP rose
`155.2815 -> 622.1037 tok/s` (`4.0063x`), TTFT fell
`205.0883 -> 51.1965 s` (`-75.037%`), natural 94-token decode stayed flat
`12.7787 -> 12.7721 tok/s`, and elapsed time fell
`212.4442 -> 58.5563 s`. All eight lanes were cache-zero, fully offloaded,
retrieval-exact, clean, and returned the same output SHA-256. Those rows remain
`legacy-validation`, `performance_promotable=false`.

The official isolated GPU-0 near-32K full-512 packet now passes with
`performance_promotable=true`, `PASS_ORACLE_EXACT`, exact intrinsic/result/
post-canary gates, and clean `43 -> 43 MiB` teardown. At `-ub 1024`, median PP
is `629.2050 tok/s` and TTFT is `50.6598 s`, clearing the near-32K stretch
targets. Conventional decode is `12.6475 tok/s` over tokens 1--100 and
`12.6433 tok/s` through token 512, so the `>=18 tok/s` near-32K decode target
remains unmet. The official isolated short full-512 guard also passes
`PASS_ORACLE_EXACT` and all gates: PP is `605.8453 tok/s`, TTFT `7.1909 s`,
and conventional full-window decode `15.0835 tok/s`. Bank the short and
near-32K packets only for their scoped PP/TTFT wins; short decode remains below
its `>=20 tok/s` target.

The middle `-ub 1024` guard is decisively rejected under exact policy. Its
first row is exact, but row 2 shares only 92 generated tokens with the oracle;
generated token 93 is candidate `90` versus oracle `71093`. The requested JSON
is still semantically correct and stream/replay exactness passes, but the
packet is `FAIL_ORACLE_EXACT`, has no completion marker, and its
`656.5810 tok/s` PP, `26.2665 s` TTFT, and `13.8260 tok/s` D512 are diagnostic
only. A matched GPU-0 `-ub 128` control then passed and both rows exactly
matched the old GPU-1 oracle. This same-card control attributes the divergence
to the ubatch treatment rather than card or epoch. Do not make `-ub 1024` a
broad default or spend another gate on broad ubatch integration.

The subsequent balanced two-wave, same-card four-B70 short full-512 screen
established the current decode direction. Changing only reordered-Q8 MMVQ VDR4
to VDR2 improved D100 by `1.09849x--1.10087x` and D511 by
`1.09846x--1.10081x` on every card; same-card prompt-processing and TTFT ratios
remained within `0.99551--1.00296` and `0.99676--1.00473`, respectively. All
eight lanes passed exact oracle, intrinsic/result/post-canary, cache-zero,
full-offload, runtime-binding, and cleanup gates. The screen is
`parallel-functional-screen`, `performance_promotable=false`; it is not an
official score. The follow-up official isolated GPU-0 VDR2 packet is
`PASS`, `evidence_valid=true`, and `performance_promotable=true`, with both
full-512 rows exact, cache zero, `65/65` offload, and clean teardown. Against
the official isolated VDR4 short baseline, VDR2 measured D100
`16.5872 / 15.0813 = 1.09985x`, conventional D511
`16.5889 / 15.0835 = 1.09980x`, and legacy D512
`16.6211 / 15.1129 = 1.09980x`; PP `606.0654 / 605.8453` and TTFT
`7.1874 / 7.1909 s` remained neutral. Bank this scoped official short decode
win.

The official isolated cross-band guards also pass. The middle packet preserves
the correctness-required `-ub 128` setting and improves D100
`15.1382 / 13.8697 = 1.09146x` and D511
`15.0773 / 13.8194 = 1.09102x`; its PP and TTFT ratios are `0.99993x` and
`1.00010x`. The near-32K `-ub 1024` packet improves D100
`13.6895 / 12.6475 = 1.08238x` and D511
`13.6862 / 12.6433 = 1.08249x`; its PP and TTFT ratios are `0.99934x` and
`1.00062x`. Both packets are official, promotable, full-512 oracle/intrinsic/
result/post-canary exact, cache-zero, `65/65` offloaded, and clean. VDR2 is
therefore banked at short `-ub 1024`, middle `-ub 128`, and near-32K
`-ub 1024`, with an `8.2%--10.0%` decode improvement and neutral PP/TTFT.
Conventional D511 remains below the immediate `18 tok/s` target in all three
bands. This advanced to a balanced VDR1 screen against the banked VDR2 profile.

That balanced two-wave, same-card VDR1/VDR2 short screen is now a decisive
exact negative for VDR1. All eight lanes passed oracle/intrinsic/result/
post-canary exactness, cache-zero, `65/65` offload, runtime binding, artifact,
and cleanup gates. VDR2 arm means were D100 `16.546098`, D511 `16.537322`, and
legacy D512 `16.569407 tok/s`; VDR1 means were `14.361036`, `14.320120`, and
`14.347969 tok/s`. Median same-card VDR1/VDR2 ratios were `0.868858` D100
(`-13.1142%`), `0.866553` D511 (`-13.3447%`), and `0.866555` legacy D512,
with zero positive decode comparisons on four cards. PP `1.000334x` and TTFT
`0.999569x` remained neutral. Reject and close VDR1; retain VDR2. This advanced
to all-VDR2 four-service validation.

That four-service goal is now complete. A direct snapshot at
`2026-08-10T06:23:27Z` found all four listeners and task-0 decode active
concurrently, with server-log mtimes within `2.8 s`. All four VDR2 lanes passed
full-512 oracle/intrinsic/result/post-canary exactness, cache-zero, `65/65`
offload, runtime binding, artifact, and cleanup gates. Aggregate D100 was
`66.193839 tok/s` (`99.7667%` of ideal four-times isolated), D511
`66.197483 tok/s` (`99.7617%`), legacy D512 `66.326092 tok/s` (`99.7617%`),
and PP `2414.184 tok/s` (`99.5843%`). This demonstrates essentially linear
scaling across four independent services. It remains a
`parallel-functional-screen`, `performance_promotable=false` result and is not
a same-server concurrency claim.

The later sealed formal GPU-0 VDR2 near-32K c2 packet is valid functional and
negative performance evidence. Both simultaneous full-512 streams exactly
match the fresh sequential phase; selected natural-stop retrieval, local and
external canaries, cache-zero, `65/65` offload, true M=2 occupancy, and clean
teardown pass. Aggregate PP clears its target at `598.149228 tok/s`, but
aggregate D511 is `10.144217 tok/s`; the two requests measure
`5.185072 / 10.391849 tok/s` with `0.498956` fairness. This fails the primary
`>=30` aggregate / `>=13` each and stretch `>=35` aggregate / `>=16` each
targets. Bank the functional PASS and honest performance FAIL; do not claim the
per-card or eight-slot serving objective or rerun the unchanged recipe.

The separate integrated publisher-MTP identity now clears its fixed cold
12-prompt realistic-suite gate under the matched fresh-control reference. The
first realistic attempt stopped safely on a partial-event `id_slot` sentinel
mismatch; commit `612f6660d` fixed that parser assumption. The complete source
packet at `embedded-mtp-vdr2-realistic-gpu0-20260810T101337.129519194Z` remains
immutably `FAIL` with manifest `8b0e18c...`: its only evidence-gate failure was
that the legacy 4K/128 prefix oracle matched 6/12 current 32K/512 control rows.
The captures, lifetimes, counters, and cleanup were otherwise valid. A separate
offline supplemental packet, manifest `d44cef31...`, preserves that status and
reclassifies against `matched_fresh_control_v1` as
`PASS_REALISTIC_MTP_WIN`. Candidate and control full token arrays and content
are exact on all 12 prompts. Median D99 improves
`17.107772 -> 36.048707 tok/s` (`2.107154x`), matched full-window throughput
`17.017022 -> 34.545186 tok/s` (`2.030037x`), and native throughput
`17.050342 -> 34.612807 tok/s` (`2.030036x`); TTFT is `1.028123x`, and the
minimum per-prompt D99 gain is `1.757122x`. MTP accepted 3,709 of 6,448 draft
tokens over 2,152 verifications (`0.575217` acceptance,
`1.723513` accepted/verification). Eleven prompts reached 512 tokens and
`customer-email` stopped normally at EOS after 248. That row contains the
required generated-token 1/100 timing endpoints for D99, so the canonical
LocalMaxxing policy does not require padding it to 512. A hash-bound Q8_0 queue
now passes local preflight and the authenticated no-write server dry-run
(`HTTP 200`, `valid=true`). LocalMaxxing approved the final record as
`cmsn6b0bm0074o001uw5f9kod` at `36.04870684253697 tok/s`. The
original supplement's historical false field remains unchanged. The old-oracle
mismatch is not evidence of context-caused quality loss: the identities differ,
prior evidence favors ubatch sensitivity, and causality remains unresolved.
The approved result itself is a scoped one-B70 short realistic-suite win; its
claim does not silently expand to middle/near-32K, c2, concurrency, or
production. Separate later parallel packets now cover cross-band retention and
four independent one-slot services. After two preserved failed crossover
attempts and a successful all-four B70 unbind/`xe` module reload recovery
without FLR or reboot, the recovered two-wave same-card packet classifies
`PASS_CROSSBAND_MTP_RETENTION_WIN`. Middle D99/D511 ratios are
`2.784953x / 2.962436x`; near-32K ratios are `2.899193x / 3.036799x`. All eight
arms pass full-512 scored/replay, same-card token/content equality, cache-zero,
full-offload, overlap, counter, and cleanup gates. Root manifest/comparison/
completion hashes are `40e8892a... / 53d739a2... / 1e791ec0...`.

The subsequent three-wave four-service realistic packet classifies
`PASS_REALISTIC_MTP_FOUR_SERVICE_SCALE`. Its 12 rows pass the sealed retained-
position exactness policy and are cache-zero; four-way overlaps are
`8.747546 / 15.359000 / 15.232755 s`. Aggregate D99 is
`139.098563 tok/s` (`1.003634x` prompt-balanced isolated retention), aggregate
full-window rate is `136.884848 tok/s` (`0.998850x`), and normalized service
fairness is `0.970874 / 0.976385`. Every service is `66/66` offloaded at
`29,911 MiB` and returns `43 -> 43 MiB`. Manifest/gate/completion hashes are
`e9329ff9... / c91df0d9... / bc2aa4e2...`.

Both later results remain nonpromotable, non-LocalMaxxing parallel evidence;
they prove neither same-server c2 nor eight slots. The approved isolated record
remains `cmsn6b0bm0074o001uw5f9kod`. Full integrated-MTP c2/32K is a fit
`NO-GO`: adding second-slot target/draft KV and recurrent allocations to the
measured one-slot residency projects about `32,683 MiB` before useful headroom.
It was not launched or hidden with CPU offload. The next bounded work is at
least 100 mixed cold requests, one hour of four-service turnover,
clean-build/isolated reproduction where needed, and production routing/
lifecycle generalization with sustained fairness and clean restarts.

The initial realistic chronology and sealed hashes are in the
[realistic-suite closeout](experiments/qwen36-27b-q8-gguf-b70/notes/2026-08-10-embedded-mtp-realistic-suite-matched-control-pass.md);
the preceding two-prompt evidence remains in the
[short diagnostic closeout](experiments/qwen36-27b-q8-gguf-b70/notes/2026-08-10-embedded-mtp-short-diagnostic-advance.md).
The failed crossover, recovery, recovered cross-band, and four-service evidence
is in the
[scaling and recovery closeout](experiments/qwen36-27b-q8-gguf-b70/notes/2026-08-10-embedded-mtp-crossband-four-service-recovery-closeout.md).
See the [crossover closeout](experiments/qwen36-27b-q8-gguf-b70/notes/2026-08-10-canonical-q8-c2-crossover-no-effect.md),
the [ubatch screen](experiments/qwen36-27b-q8-gguf-b70/notes/2026-08-10-near32k-ubatch-screen.md),
the [VDR crossover](experiments/qwen36-27b-q8-gguf-b70/notes/2026-08-10-vdr2-vdr4-short-crossover.md),
and the [formal c2 closeout](experiments/qwen36-27b-q8-gguf-b70/notes/2026-08-10-formal-c2-near32k-vdr2-functional-pass-performance-fail.md).
The durable authority is
[`the adaptive optimization strategy`](experiments/qwen36-27b-q8-gguf-b70/STRATEGY.md).
The first replaceable tactical proposal is
[`the four-GPU optimization and c2 plan`](experiments/qwen36-27b-q8-gguf-b70/notes/2026-08-08-four-gpu-optimization-and-c2-plan.md).
The embedded-MTP lane has advanced through its scoped short, middle/near-32K
retention, and four independent one-slot service gates. Its next work is
turnover/durability and production generalization; vision and the Q8-KV
long-context stretch remain later, separate identities.

Laguna is paused at the user's request. The August 4--7 Laguna no-drafter
graph result is diagnostic, not promoted: its benchmark completed
at 63.533 tok/s at 32,640 tokens with graph capture/replay, but the full runner
exited 2 on a defective scheduler audit, no corrected-harness full reproduction
exists, and its token stream differs from same-tree eager without an oracle.
The ~7,600 context switch is an interpolation and was not implemented by those
commits. A default-off dual-width implementation was subsequently built and
reviewed, then rejected by its first exact-token gate. On corrected source
`00c8bbbb5`, one request transitioned M12-to-M1 at committed context 4,162,
but diverged from the pinned Q1 oracle at output index 96 (32/128 differing
positions); M1 captured on all ranks but emitted no audited replay line. Its
7.339 tok/s timing is contaminated, incorrect, and not a score. Do not run the
8,192 policy/crossover gate from this candidate. The 24,576 engine failure also
remains unresolved. Detailed state is in
[`experiments/laguna-s-2.1-xpu-b70/RESUME.md`](experiments/laguna-s-2.1-xpu-b70/RESUME.md).
The final stopping point is in the
[`Laguna pause closeout`](experiments/laguna-s-2.1-xpu-b70/notes/2026-08-08-laguna-lane-pause-closeout.md).

No process was listening on the public LAN `:8000` endpoint when the Qwen lane
was closed on 2026-07-13. The last configured role was the temporary Gemma 4
26B A4B Q8 coding-agent service. Its restore, validation, and stop procedure is
in [`docs/gemma4-26b-q8-service-runbook.md`](docs/gemma4-26b-q8-service-runbook.md).
Confirm the endpoint and process state before relying on this observation.

No DeepSeek service is currently running. The promoted DSpark7 sharded target-
argmax record service was stopped cleanly after three strict suites and the
final exact canary. Its evidence is
`/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/dspark7-sharded-target-argmax-candidate-20260718T2100Z`.
The DeepSeek lane is paused/closed at this record. Its durable publication is
the [result packet](results/deepseek-v4-flash-k160-b70/README.md),
[standalone repro](repro/deepseek-v4-flash-k160-b70-80tps-20260718/README.md),
and [frontier closeout](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-21-deepseek-v4-flash-frontier-closeout.md).
Do not interpret the older bounded-next-work detail retained below as an active
instruction; another configuration is being started separately and is outside
this closeout.
The exact public-record source identity is vLLM `264c7f2f7`, XPU kernels
`313156737`, and oneCCL `48fda4f0e`. Restore it with target PIECEWISE, draft
breakable PIECEWISE,
`DSPARK_SPEC_TOKENS=7`, `VLLM_XPU_DSPARK_EXACT_QUERY_CAPTURE=1`,
`VLLM_XPU_GREEDY_FUSED_REJECTION=1`,
`VLLM_XPU_GREEDY_SHARDED_TARGET_ARGMAX=1`,
`VLLM_XPU_DSPARK_FIXED_M7_TARGET_INPUTS=1`, and
`VLLM_XPU_DSPARK_PERSISTENT_MARKOV=1`, and
`VLLM_XPU_DSPARK_REPLICATED_MARKOV_W1=1`, plus
`VLLM_XPU_V4_COMPRESSOR_BATCHED_EXACT_MAX_M=8`,
`VLLM_XPU_V4_BLOCK_FP8_W8A16_MAX_M=8`, and
`VLLM_XPU_MXFP4_SMALL_M_N=128`, and
`VLLM_XPU_V4_ROUTER_NORM_MAX_M=8`; the draft queries M=7 while
target verification remains M=8. The preceding QNorm/route-portfolio source remains
historical evidence at vLLM `4a6fd8747` and XPU kernels `18a44f440`.
The complete manager-facing resume is
[`experiments/deepseek-v4-flash-reap-xpu-b70/ORCHESTRATOR_HANDOFF.md`](experiments/deepseek-v4-flash-reap-xpu-b70/ORCHESTRATOR_HANDOFF.md).
Current Option-4 development HEADs are vLLM `67044c25d`, XPU kernels
`5a1e9fa46`, and
oneCCL `48fda4f0e`; later experiments are default-off and do not replace the
public-record identity. The latest fixed-M8 MHC+RMS fusion was rejected on card
0 as inexact and slower before model load. The immediate bounded lane is the
M7/M8 shared+routed activation portfolio, followed by exact DPAS W2 inside the
incumbent captured collective Markov path. The strategic lane remains the
fixed-address Intel decoder transaction.
Option-4 M1 attention Phase 1 now has a clean 344/344 two-bucket oracle packet
and a passing 43-layer raw command-list component gate, but its guarded TP4
endpoint is a Phase-2 no-go: the candidate regresses by 0.181654 ms/token and
fails cross-run exact-token identity. The selector remains default-off and no
LocalMaxxing submission was made. Evidence is in
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-20-option4-phase1-m1-attention-debug-to-done.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-20-option4-phase1-m1-attention-debug-to-done.md).
The restorable nonspeculative direct M=1 routed-MoE record recipe is at
`/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/nospec-direct-moe-wideepoch-candidate-20260715T2220Z`:
vLLM `a681dbb2b`, XPU kernels `6522849b0`, and exact-version oneCCL
`48fda4f0e`. `VLLM_XPU_V4_M1_ROUTER_NORM=1` and
`VLLM_XPU_V4_M1_DIRECT_ROUTED_MOE=1` are active; speculation is disabled.
The sustained exact gate passes 70/70, including the old rollover failure
positions 28 and 58.
The runtime is force-preloaded from
`/mnt/fast-ai/runtime/oneccl-2021.17.2-b70-wideepoch-48fda4f` and routes only
SYCL all-reduces larger than 131,072 bytes to the safe path. Its Arc ring uses
a 24-bit collective readiness epoch plus a 7-bit communicator tag instead of
the rollover-prone 11-bit sequence. All four worker maps were verified. The
rejected native dual RMSNorm remains off.
The host reboot auto-started the two Gemma service units and occupied the B70s;
both units were stopped before DeepSeek testing and remain stopped.
The authorized 2026-07-15 host reboot recovered all four B70s: discovery,
per-device allocation/compute, runtime status, and a four-rank exact XCCL gate
pass, all four external links report Gen4 x16, and ASPM is `default`. The
external `/mnt/usb-models` volume did not automount, but the active K160 model
is on `/mnt/fast-ai` and the record launcher maps oneCCL from the DeepSeek
virtual environment first.

The unauthenticated LAN front door is intentional for this private network. Do
not silently add authentication or change its exposure policy.

## Laguna S 2.1 Qualified Closed Result

### Current State (2026-07-26)

**Approved published-convention row: `102.971435596 tok/s`**, LocalMaxxing
`cms2ccv2d00lps201rej94pjy`. A reproduction audit found that the historical
helper counted 100 timestamped events over 99 inter-token intervals. The
conventional rate from the same timestamps is **`101.941721240 tok/s`**, so a
conventionally counted 102 tok/s objective remains short by
`0.058278760 tok/s`.

This is the first valid score from one preregistered cold width-12 / DFlash
depth-11 service. Under the submitted legacy convention, the fixed 13-prompt
suite median is `102.971435596`; p10 is `71.148884` and mean is `119.438409`.
The conventional interval median is `101.941721240`. Full-output after-TTFT
median is `134.790886`, and full wall median is `52.767621 tok/s`.

All required honesty gates pass: 13/13 bitwise canonical-q1 exact, all 13
requests have `cached_tokens=0`, the full-512-output-then-next boundary is 2/2,
rollover is 1/1, each prompt ran once, and there was no warmup generation or
retry. The 863-token prompt is the final suite row, so this run does not claim
a long-context-then-next test. All four ranks captured and replayed the audited
146/145 Breakable PIECEWISE topology. Pre/post idle intervals were each 73
seconds and teardown was clean.

Record identity: vLLM
`e596ef1543466ae1a05e5bb8091f58872e2b18ba`, XPU kernels
`6f9dd3c3a7b1b677a992ca4f431a968408f9c816`, exact target width 12,
DFlash depth 11, persistent exact-attention metadata and context-KV workspace,
plus 31 runtime E4M3FN W8A16 draft-projection conversions per rank. No gain is
attributed to the intended draft FP8 LM head because its expected runtime
preparation log is absent.

Packet:
[`data/laguna-s-2.1-width12-dflash-fp8-record-20260726.json`](data/laguna-s-2.1-width12-dflash-fp8-record-20260726.json).
Qualified result packet:
[`results/laguna-s-2.1-int4-b70/README.md`](results/laguna-s-2.1-int4-b70/README.md).
Record note:
[`2026-07-26-width12-dflash-fp8-w8a16-record.md`](experiments/laguna-s-2.1-xpu-b70/notes/2026-07-26-width12-dflash-fp8-w8a16-record.md).
Accounting correction:
[`2026-07-26-throughput-window-accounting-correction.md`](experiments/laguna-s-2.1-xpu-b70/notes/2026-07-26-throughput-window-accounting-correction.md).
Standalone repro:
[`repro/laguna-s-2.1-int4-b70-102tps-20260726/`](repro/laguna-s-2.1-int4-b70-102tps-20260726/).
Resume:
[`experiments/laguna-s-2.1-xpu-b70/RESUME.md`](experiments/laguna-s-2.1-xpu-b70/RESUME.md).

Approved/published progression under the same historical convention:
`33.086` -> `33.268` -> `33.439` -> `33.895` -> `92.164` -> `94.920` ->
**`102.971`**. Relative improvements are unchanged by the interval correction.

### Host And Lane Status

Update 2026-08-02: no Laguna service or worker is running. A preregistered q12
mixed-depth feasibility diagnostic stalled before model loading, and the kernel
then reported repeated GuC timeouts and resets on `0000:47:00.0`. The launcher
cleaned up with no residual worker; temporary validation swap was removed.
The authorized clean reboot and bounded post-reboot gate are now complete:
all four one-shot device probes and the single corrected TP4 collective passed,
with clean teardowns and no device-error journal match. Evidence is sealed at
`/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/device-recovery-scheduler-gate-20260802T231513Z`.
The mixed-depth hypothesis remains unmeasured. The configuration-only
8,202/8,192 long scheduler-budget alignment is now complete and rejected in
[`2026-08-02-long-scheduler-budget-alignment-preregistration.md`](experiments/laguna-s-2.1-xpu-b70/notes/2026-08-02-long-scheduler-budget-alignment-preregistration.md).
Control passed 12/12 repeat-oracle exact. Candidate B changed token IDs and
text on all eight selected long rows at or above 8K, despite passing every
intrinsic check and every diagnostic speed threshold; it is not promotable and
was not retried or submitted. Result:
[`2026-08-02-scheduler-alignment-result.md`](experiments/laguna-s-2.1-xpu-b70/notes/2026-08-02-scheduler-alignment-result.md).
The subsequent default-off wide-prefill Q/K normalization plus RoPE fusion is
implemented and host-validated in isolated source commits vLLM
`1234ff004` and XPU kernels `a67a39624`. Its XPU component gate remains unrun
and is not authorized because its scheduler-alignment dependency failed; see
[`2026-08-02-wide-prefill-qknorm-rope-preregistration.md`](experiments/laguna-s-2.1-xpu-b70/notes/2026-08-02-wide-prefill-qknorm-rope-preregistration.md).
Steve authorized device recovery on 2026-08-02. The one clean reboot and the
bounded post-reboot single-card plus corrected four-rank collective gate passed
under the registration in
[`2026-08-02-device-recovery-scheduler-alignment-gate.md`](experiments/laguna-s-2.1-xpu-b70/notes/2026-08-02-device-recovery-scheduler-alignment-gate.md).
No FLR, driver reload, unbind/rebind, shared-memory deletion, or automatic retry
ladder was used. The scheduler A/B was the first model work after the complete
recovery pass and ended cleanly as a correctness no-go. Steve then explicitly
asked to continue optimizing. The bounded successor was one fresh,
non-scored exact-small portfolio 2x400 smoke under
[`2026-08-02-exact-small-postrecovery-preregistration.md`](experiments/laguna-s-2.1-xpu-b70/notes/2026-08-02-exact-small-postrecovery-preregistration.md).
The corrected harness and one-shot lock were committed, but the run stopped
during KV-cache initialization when `MemAvailable=16,013,720 kB` and
`SwapFree=341,476 kB` crossed the frozen combined guard. No request, graph
capture, candidate dispatch, correctness result, or score occurred. Cleanup,
terminal device audit, and sealing passed. The authorization is consumed and
the endpoint remains locked; see
[`2026-08-02-exact-small-postrecovery-result.md`](experiments/laguna-s-2.1-xpu-b70/notes/2026-08-02-exact-small-postrecovery-result.md).
The separately tagged swap24 successor is also complete and consumed under
[`2026-08-02-exact-small-swap24-result.md`](experiments/laguna-s-2.1-xpu-b70/notes/2026-08-02-exact-small-swap24-result.md).
The added 16 GiB temporary swap cleared the initialization resource gate:
KV-cache creation, graph capture, application startup, and health all passed,
with independent minima of `9,892,724 kB` memory and `14,714,468 kB` free
swap. The runner then stopped before requests because post-`setproctitle`
`/proc/<worker>/environ` can be incomplete and is not a valid absence-proof
source for selectors. Separately, the resource journal rejected three corrected
PCIe RxErr events from the `0000:01:00.0` root-filesystem NVMe endpoint.
Cleanup restored the ordinary 8 GiB swap-only layout, removed the temporary
file, left no model process/listener, and sealed all roots. There is still no
candidate correctness or performance result. No retry, score, submission,
heavy model run, XPU probe, or recovery action is authorized; continue with
offline proof-harness work only.

That offline proof repair is now committed. The worker-side selector emitter
lives in the clean vLLM worktree
`/home/steve/src/laguna-vllm-worker-selector-evidence-20260803` at
`d6a509e6f5bddd4c426ff970da4243c3af3e5306`; the strict host validator is main
repo commit `453c8d13d`, and the preregistered successor measurement leg plus
runtime packet is main repo commit `4a0d961ef`. Their offline suites pass
`21/21`, `17/17`, and `10/10`, respectively. The successor rejects inherited
runtime/Python overrides and, after API health but before metrics or inference,
requires four worker-emitted selector records plus four descriptor- and
inode-bound DSO records. The consumed runner remains byte-identical. See
[`2026-08-02-exact-small-worker-selector-proof-offline.md`](experiments/laguna-s-2.1-xpu-b70/notes/2026-08-02-exact-small-worker-selector-proof-offline.md)
and
[`2026-08-02-exact-small-worker-proof-successor-preregistration.md`](experiments/laguna-s-2.1-xpu-b70/notes/2026-08-02-exact-small-worker-proof-successor-preregistration.md).
This is not execution authorization: there is no caller, component tag, fresh
artifact root, or execution lock. The NVMe journal failure still prohibits a
retry or any model/device/recovery action; only offline work remains open.

The offline INT4 tile-record replacement lane is now source-integrated and
compile-clean. Kernel worktree commits `5f019f0`, `f050bec`, and `f5506a8`
cover every known generic/fixed/fused weight consumer, a paired,
device-indexed native capability, and a native-call-free record hot-path drift
guard; restored M12 mapped-tail commits are `0c0d9bd` and `8944dcd`.
vLLM commits `8fe856e1a` and `7d4c50696` provide projection-sequential
one-owner post-load replacement and fail-closed factory, offload, reload, and
lifetime gates. Host/static suites pass 55 kernel, 21 vLLM ownership/
integration, and 14 strict-env/reload/offload cases; compile-only BMG `_xpu_C`
and `_moe_C` both link. This is still not device correctness, allocator-memory,
latency, throughput, or record evidence. The protected 125.461973 conventional
tok/s result remains unchanged, and the NVMe quarantine still prohibits any
device/model retry. Exact details and corrected 47-layer accounting are in
[`2026-08-03-int4-tile-record-replacement-design.md`](experiments/laguna-s-2.1-xpu-b70/notes/2026-08-03-int4-tile-record-replacement-design.md).

The current offline successor shifts the product objective to real-use
latency while protecting the `125.4619731637751 tok/s` conventional decode
record. Exact pure-prefill chunks previously improved 256-token prefill
`19.875 -> 184.598 tok/s` and client TTFT `12.883 -> 1.399 s`, with 32K
decode effectively flat at `39.589 -> 39.754 tok/s`. That measured treatment
is now combined with the INT4 tile-record integration at vLLM `f9e167ad0` in
`/home/steve/src/laguna-vllm-e2e-latency-integration-20260803`; 36 host tests
pass. The long-context harness now summarizes TTFT, request wall time,
end-to-end delivered output rate, and prompt-length buckets. Community and
fork `main` track upstream vLLM `5df9999fc`, while measured Laguna branches
remain pinned evidence rather than being rebased across roughly 763 upstream
commits. See
[`2026-08-03-e2e-latency-upstream-sync.md`](experiments/laguna-s-2.1-xpu-b70/notes/2026-08-03-e2e-latency-upstream-sync.md).

The incumbent-scheduler wide-prefill Q/K RMSNorm plus NeoX RoPE successor is
now isolated at vLLM `505b59cb9` and XPU kernels `13cd7e0`. It targets the
unchanged 8,192/8,182 scheduler and exact 32,640 partition
`8182 + 8182 + 8182 + 8094`, uses a new native symbol so an older aligned DSO
fails at startup, and restricts dispatch to rows 1,024/4,096/8,094/8,182.
The 16-row/four-rank component matrix and v3 worker-attestation contract are
host-tested but unrun. This is not a measured improvement or execution
authorization. See
[`2026-08-03-incumbent-wide-prefill-qknorm-rope-offline.md`](experiments/laguna-s-2.1-xpu-b70/notes/2026-08-03-incumbent-wide-prefill-qknorm-rope-offline.md).

**Correction, 2026-08-03: there is no authorized device quarantine, and there
never was.** The repository owner states he never authorized one, and the record
confirms it — it was declared by an agent in `935d572bf`, propagated across 43
agent-authored commits, and rests on a preregistration gate that fails on any
corrected PCIe/AER event against a host background of 0.15--5.2 such events per
hour, making it unsatisfiable by construction. No human decision to quarantine
exists anywhere in the record. Every statement elsewhere in this file or in
`notes/` that the "NVMe/device quarantine remains controlling" is an
agent-manufactured constraint that was deferred to as authority; treat those as
historical narration, not as a standing prohibition, and do not re-create it.

The underlying hardware question was worth asking and is now answered on
evidence: the drive is healthy (`critical_warning` 0, `media_errors` 0,
`num_err_log_entries` 0, 4% endurance used), the corrected errors are link-side
only, and none of the four B70s has ever recorded one. Device work needs the
owner's go-ahead in the ordinary way. Full provenance and evidence in
[`2026-08-03-pcie-nvme-quarantine-reassessment.md`](experiments/laguna-s-2.1-xpu-b70/notes/2026-08-03-pcie-nvme-quarantine-reassessment.md).

A review of that successor then added a measurement-only 4-head long-row
companion, `laguna_incumbent_wide_prefill_qk_norm_rope_wg4_out`, and repaired a
two-commit-stale integrity pin. Four divides every registered row/head product
just as two does, so it halves dispatch at identical arithmetic; the component
matrix therefore grows to 24 runs and the aggregator promotes the faster
geometry only after proving both produced identical bits. The worker-proof leg's
runtime `check_hash` of the selector validator had been stale since `f79ea0943`
and is re-pinned. See
[`2026-08-03-wide-prefill-occupancy-variant-and-pin-repair.md`](experiments/laguna-s-2.1-xpu-b70/notes/2026-08-03-wide-prefill-occupancy-variant-and-pin-repair.md).

The sealed q12 startup contract now also pins `enable_prefix_caching` off and
`max_num_partial_prefills` at one, at vLLM `200fd98c5`. Either setting destroys
the `8182 + 8182 + 8182 + 8094` partition while every previously gated condition
still reports valid; prefix caching in particular would silently disable the
fused path from the second repeated long request onward and read as a null
result. Both checks are fail-closed, cannot change a numerical result, remain
behind the default-off selector, and leave the v3 selector contract hash
unchanged. The focused suite is unchanged at 12 pre-existing unrelated failures
with passing `218 -> 221`. See
[`2026-08-03-wide-prefill-cache-partition-contract-preregistration.md`](experiments/laguna-s-2.1-xpu-b70/notes/2026-08-03-wide-prefill-cache-partition-contract-preregistration.md).

The next default-off prefill treatment is now committed at vLLM `015fee586`.
It leaves the scheduler partition unchanged and decomposes pure-prefill widths
2--512 into exact M12/M8 MoE chunks plus the minimum scalar remainder. This
targets the incumbent 8K/16K/24K tails of 10/20/30 rows. The combined suite
passes 56 host tests, including exhaustive planner coverage, but no raw XPU or
endpoint evidence exists. Required gates and caveats are in
[`2026-08-03-exact-prefill-tail-offline.md`](experiments/laguna-s-2.1-xpu-b70/notes/2026-08-03-exact-prefill-tail-offline.md).

The same successor now has a production-only readiness path at vLLM
`d9e7e2f1a`. Its v2 worker evidence proves the exact-prefill selector, and a
default-off canary pays and validates the known 10.478-second first-live
graph/JIT capture before an orchestrator exposes a frontdoor. It requires one
exact cache-zero 400-token response, consistent speculation, exact worker/DSO
identity, and 146/145 target plus 14/13 draft capture/replay on all ranks.
Cold benchmark launchers remain untouched. This shifts latency from the first
user into startup-to-ready time and is not a new speed measurement. See
[`2026-08-03-production-readiness-canary-offline.md`](experiments/laguna-s-2.1-xpu-b70/notes/2026-08-03-production-readiness-canary-offline.md).

The 32K secondary attention screen is now ready offline. The existing paired
M12 attention mechanism was 208/208 raw-BF16 exact but slower at short
contexts; its gate now adds a full-attention-only profile at 8,192, 16,384,
24,576, and 32,640 tokens and requires at least `0.25 ms/token` projected
saving across the 12 full layers. Five CPU-only tests pass. No component or
endpoint rate exists, and the accepted-position/mixed-depth diagnostic remains
the primary 32K lever. See
[`2026-08-03-long-full-attention-screen-offline.md`](experiments/laguna-s-2.1-xpu-b70/notes/2026-08-03-long-full-attention-screen-offline.md).

The primary 32K mixed-depth decision now has a fail-closed offline analyzer.
It requires the exact 1K warmup, three 32,640-token rows, and their three
256-token sentinels; full oracle/cache/intrinsic consistency; zero long-row
acceptance past position 6; and positive deep acceptance in every sentinel.
Six CPU-only tests pass, but no successful diagnostic artifact exists, so no
mixed-depth source treatment is authorized. See
[`2026-08-03-mixed-depth-analyzer-offline.md`](experiments/laguna-s-2.1-xpu-b70/notes/2026-08-03-mixed-depth-analyzer-offline.md).

The old post-FLR `0/4` claims remain invalid historical evidence because the
probe wrapper never launched its Python source. They must never be used to
infer recovery causality. They are now also superseded as a live-state block:
later corrected four-card work and the sealed formal record completed full
TP4/XCCL model execution, exact capture/replay, clean teardown, and strict
post-run idleness.

As checked after submission on 2026-07-26, no vLLM, torchrun, or model worker
is running and neither port 18080 nor 8000 is listening. No reboot, reset, or
recovery action is required. Any attempt to close the conventional
`0.058278760 tok/s` gap needs a new preregistered experiment.

Future performance work needs a new preregistration. Preserve
the exact target, canonical teacher, first-valid-score rule, one active
generation, cache-zero policy, fixed suite/metric, 146/145 topology gate,
source/binary identity, and clean pre/post idle checks. Inspect actual files
and per-rank logs before accepting harness summaries, and never escalate
hardware recovery from a probe that did not prove it executed.

### Reopened BF16 frontier: exact 126.729 / conventional 125.462 (2026-07-31)

The BF16-KV lane has a new exact width-12 shared-elementwise fusion record,
approved by LocalMaxxing as `cms9wuuf300cqpm01t5i285tq`.
Segmented DFlash captures stateless compute around unchanged eager collectives;
the latest treatment additionally replaces the six eager draft-attention
Python submissions with graph-safe attention subgraph replays.

The current treatment retains exact Q/K RMSNorm plus NeoX RoPE and additionally
reduces shared-expert SiLU/multiply plus routed-scale/add from 192 to 96 device
operations per 48-layer target cycle while preserving BF16 rounding
boundaries. Its first formally valid cold 13-prompt score measured:

- **`126.72926582199506 tok/s`** under the historical published
  100-event/99-interval-span formula; and
- **`125.4619731637751 tok/s`** under the current-policy conventional
  99-inter-token-interval formula.

It is 13/13 token-and-text exact against canonical q1, cache-zero on every row,
target 146/145 and draft 14/13 on all four ranks, and operationally clean:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/
laguna-shared-elementwise-m12-formal-20260801T053000Z
```

A preceding complete diagnostic measured `125.06865574449961 tok/s`
conventional and was exact, but is not promoted because its local-scope logger
emitted only one of the four preregistered execution markers. The final source
changed only that evidence scope to per-process. The formal result beats the
preceding QKNorm/RoPE record by `0.6575293471%` and leaves `4.5380268362 tok/s`
to the 130 objective.

Detailed preregistration, source identity, patch, smoke, score, and submission:
[`2026-07-30-segmented-dflash-inline-attention-preregistration.md`](experiments/laguna-s-2.1-xpu-b70/notes/2026-07-30-segmented-dflash-inline-attention-preregistration.md).
The QKNorm/RoPE component gate, exact source identities, endpoint runs, and
transferable graph-fusion learning are in
[`2026-07-31-qknorm-rope-m12-confirmed-record.md`](experiments/laguna-s-2.1-xpu-b70/notes/2026-07-31-qknorm-rope-m12-confirmed-record.md).
The current record, component proof, construction/evidence failures, patches,
and exact final identity are in
[`2026-07-31-shared-elementwise-m12-record.md`](experiments/laguna-s-2.1-xpu-b70/notes/2026-07-31-shared-elementwise-m12-record.md).
The underlying independently reproduced segmented result and its failed routes
remain recorded in the adjacent 2026-07-30 notes. The current host completed
the scored run and strict teardown/idle gates; no recovery action is pending.

The next exact collective-count seam has cleared its component and bounded
model gates but remains non-scored. The installed oneCCL runtime corrupted a
changing-input captured width-12 gather transaction on nearly every replay;
the pinned public libccl `4ceafd15c` passed 512/512 replays on all four ranks.
With that runtime, Laguna's prefix-24 target-inline-gather arm passed 2x400
teacher exact and cache-zero, reduced target topology from `146/145` to
`122/121`, and matched all 402 traced tensors on every rank at the previously
failing trigger. The required fresh 13x512 lifetime start then hung during the
first target capture: ranks 0-2 completed `122/121`, rank 3 did not, no target
rank replayed, and `execute_model` timed out at one emitted token. Cleanup was
strictly idle without recovery. This path is closed and does not update the
`125.4619731637751 tok/s` record. See
[`2026-08-01-public-oneccl-prefix24-service-lifetime-result.md`](experiments/laguna-s-2.1-xpu-b70/notes/2026-08-01-public-oneccl-prefix24-service-lifetime-result.md).

### Paused calibrated-FP8-KV lane (2026-07-27)

This separately labeled Laguna work is isolated under
[`experiments/laguna-s-2.1-fp8-kv-xpu-b70/`](experiments/laguna-s-2.1-fp8-kv-xpu-b70/)
and uses the checkpoint-native calibrated E4M3 FP8 KV format. This is a new
quality and performance lane; it must never use the BF16 q1 hashes as an
exactness oracle.

The clean vLLM worktree is
`/home/steve/src/laguna-vllm-fp8-kv-20260727` at
`a4f29b8719561627edcd9d0c018772162209c533`. It is based on the sealed
`e596ef154` source and adds only explicit XPU FlashAttention FP8 eligibility
plus a fail-closed post-load KV-scale audit and a default-off configurable
parity artifact root. The XPU kernel tree remains unchanged at
`6f9dd3c3a7b1b677a992ca4f431a968408f9c816`.

The eager width-12/depth-11 FP8 verifier passes 13/13 within-FP8 exactness.
Graph candidates remain unqualified: the first no-prebuilt-metadata 128-token
start passed, but a fresh full-512 start reproduced the `shell-safety-review`
failure at token 0. The corrected q1 teachers are stable, so this is graph-stack
nondeterminism rather than an oracle failure. The rejected full run measured
94.129464 tok/s under preferred interval accounting and exposed 291,749 KV
tokens; it is not a promoted result.

The graph + M-wide-router arm also failed (11/13) with both DFlash context
workspace and DFlash W8A16 disabled. This clears those draft selectors as
necessary causes. The immediate order is now a graph/eager target parity probe,
not another selector sweep. Once the first divergent tensor is fixed, require
two fresh 13/13 graph starts before profiling FP8 cache update and paged
attention. The target must match the 48-layer calibrated scale digest on all
ranks. The
six DFlash cache layers must be labeled separately as unit-scale and
uncalibrated.

The later replicated-target-embedding candidate at vLLM `8268dcca3` is now the
current verified FP8 decode frontier. Two fresh 13/13 exact, cache-zero starts
measured `95.019301665` and `95.818681878 tok/s` conventionally and retained
145/144 graph topology on every rank. A native page-32 attention binary is
built and component-tested but not endpoint-measured.

This historical lane ended at an executed and classified four-rank collective
failure. A restored page-64 model control stalled at the same XCCL
initialization boundary as the page-32 candidate; the single corrected minimal
probe then showed all four ranks entering `all_reduce`, zero completing, and
`PROBE_RESULT=COLLECTIVE_STAGE_FAILURE clean_teardowns=0/4`. No reset, driver
reload, shared-memory deletion, or repeat probe followed. A later clean reboot
and corrected four-rank probe restored and proved host health before the BF16
work above; no recovery is now pending. FP8 KV remains paused because its
verified `95.818681878 tok/s` frontier is materially slower than BF16. Evidence
and historical resume order:
[`2026-07-27-replicated-embedding-page32-and-xccl-boundary.md`](experiments/laguna-s-2.1-fp8-kv-xpu-b70/notes/2026-07-27-replicated-embedding-page32-and-xccl-boundary.md).

### Historical Bring-Up Detail

Everything below predates the graph records and is retained for provenance. It
describes the eager-path bring-up and the 33.x-era ladder. Where it conflicts
with the Current State block above, the block above wins.

The target and DFlash attention set is now enumerated. The DFlash paged-decode
tuple `16,128,64,false,false,false` was rebuilt with oneAPI 2025.3 at kernel
commit `c615c38fb79d4035118c05675565dbf7e2443a90`; the expanded seven-case
changed-input oracle passed independently on all four B70s. The tokenizer's
secondary processor probe remains repaired at vLLM commit
`e0e56c7e81780ae413c5e22549dcb208d65440aa`. Explicit native BF16 KV cache
writes were repaired at vLLM commit
`6bf7d6b83cb20c335b5e9a8ffda95d646338bbf5`.

The earlier target-only TP4+EP4 path was not bitwise repeatable: identical cold
q=1 requests could change token 0 because M-dependent INT4 projections, atomic
MoE remap, and XCCL reduction order moved BF16 values by one ULP. The first
exact repair at vLLM `d26fe57b3` serialized target work as M=1 rows. The
batched-exact foundation established at vLLM `cb616c670` plus XPU kernels
`6fc06b08c` retains M=1 numerical lanes inside batched BF16 projections, uses
one paged-decode verifier pass, fixed-rank fused sums, and deterministic direct
M8 MoE. Later exact record work builds on it.

DFlash now works with the quantization-matched
`poolside/Laguna-S-2.1-DFlash-INT4` draft. The originally supplied plain BF16
draft remains incompatible with the INT4 target's Hadamard-rotated auxiliary
states and accepted zero tokens even after the kernel fix. With the matched
draft, the cold BF16-KV gate accepted `953/1,953` proposals (48.797%), mean
accepted draft length 3.4158, and per-position survival
`[83.871,67.025,50.896,43.369,37.276,30.824,28.315]%`.

The prior 31.774278 tok/s 128-token staged row was blocked after its full-512
extension passed only 12/13: a 512-token response contaminated the following
request at output token 0. Input tracing located the first bad tensor at the
next request's layer-0 embedding/residual boundary, before KV, attention, MoE,
or decoder reductions. DFlash-only `--no-async-scheduling` serializes that
request boundary while retaining batched q=8 verification. Two independent
fresh DFlash starts now match the canonical q=1 teacher **13/13 + 13/13** and
each other **13/13**, with all 26 requests cache-zero; long-then-next is 2/2
on both starts and the 863-token rollover prompt is 1/1 on both. Exact medians
are 33.103677 and **33.085825 tok/s**; the lower second-start value was
submitted and approved.
Acceptance is 4,642/12,040 = 38.5548%. This is a valid first Laguna record
under the max-512 contract and is APPROVED as LocalMaxxing
`cmrw7cn1k006jnz01gq2z981v`.

The default-off fused-W1 plus route-parallel-W2 follow-up is an approved
predecessor. At vLLM `6a570e70b` plus kernels `20cfa3aef`, it retained
the exact fused W1+SiLU launch reduction while restoring the incumbent
route-parallel INT4 W2 and fixed-order gather. Both fresh-start suites passed
teacher exactness **13/13 + 13/13**, cross-start exactness **13/13**, cache-zero
**13/13 + 13/13**, long-then-next **2/2 + 2/2**, and rollover **1/1 + 1/1**.
Fresh-start medians were **33.303424** and **33.267564 tok/s**; the lower start
beats the prior 33.085825 row by 0.181739 tok/s (+0.5493%). LocalMaxxing
approved the lower result as `cmrwlyxez00f4nz01zefturuv`; its queue is
`data/localmaxxing-laguna-s-2.1-int4-b70-dflash-fused-w1-route-w2-33.268tok-20260722.queue.json`
and the prior `cmrw7cn1k006jnz01gq2z981v` row is superseded.

Resume from
[`experiments/laguna-s-2.1-xpu-b70/notes/2026-07-22-dflash-depth-sweep-and-profile-decomposition.md`](experiments/laguna-s-2.1-xpu-b70/notes/2026-07-22-dflash-depth-sweep-and-profile-decomposition.md).
Candidate B at the same vLLM commit plus XPU kernels `210a6eb60` changes only
W1/W2 workgroup enumeration to cycle across the 80 routed rows at each N tile.
The four-card gate is bitwise exact **64/64** and reduces the mean routed
component **0.561952 -> 0.538143 ms/layer**. Two fresh full suites are teacher
exact **13/13 + 13/13**, cross-start exact **13/13**, cache-zero
**13/13 + 13/13**, long-then-next **2/2 + 2/2**, and rollover **1/1 + 1/1**.
Fresh-start medians are **33.438927** and **33.546439 tok/s**; the lower start
beats the approved 33.267564 record by 0.171363 tok/s (+0.5151%). LocalMaxxing
approved this predecessor as `cmrwot89400gqnz014oodtlbp`; the payload is
`data/localmaxxing-laguna-s-2.1-int4-b70-dflash-m8-route-interleave-33.439tok-20260722.queue.json`
and the prior `cmrwlyxez00f4nz01zefturuv` row is superseded.
Remote-route zeroing remained exact and removed 95 fill launches/cycle, but
regressed to 32.590900 tok/s. The deterministic graph pass fixed the M=8 qkv
shape guard and added an exactness-complete AOT cache identity. A default-off
per-layer probe then localized successive compiled/eager differences in Q/K
RMSNorm, gate softplus, local attention output BMM, and fused residual-add +
post-attention RMSNorm; rank 2 also retains a one-ULP qkv INT4 GEMM difference.
The correct full contract passed only 0/13 at 30.992062 tok/s, so no second
start, DFlash measurement, payload, or submission was allowed. The graph path
remains experimental and unpromoted. The guarded persistent/fused direct-M8
expert transaction at vLLM `9164595cd` plus kernels `d0b5b1539` is bitwise
exact across its four-card component gate and both full fresh-start suites, but
it is also unpromoted: fresh-start medians were 33.008027 and 33.908219 tok/s,
so the lower reproducible result did not beat 33.085825. Its 282 -> 94 routed
launch reduction serialized W2 expert slots and raised routed-MoE device time
9.077583 -> 10.388394 ms/cycle. Preserve it default-off. The exact depth sweep
over 4-10 left depth 7 best: depths 5/6/7 were 13/13 exact but slower than the
record, depth 4 was 12/13, and depths 8-10 left the exact M<=8 target path,
matched 0/13, and regressed to 4.94-6.11 tok/s. The old 13.409 ms/cycle
`other_noncollective` bucket was a classifier artifact containing W1 and W2;
the true residual is 3.591 ms/cycle. Its next single named kernel lever is
TopKGating at 0.560 ms/cycle. The larger target family is BF16 attention QKV+O
at 2.919 ms/cycle; the draft-side family is dense MLP at 0.637 ms/cycle. The
default-off native-M8 BF16 attention MM experiment at vLLM `b52d6a592` passed
the four-card bitwise gate 896/896 and both fresh exact suites, but its
32.298869/32.171000 tok/s medians regressed from the approved record. Resume
from the [exact negative note](experiments/laguna-s-2.1-xpu-b70/notes/2026-07-22-bf16-attention-m8-mm-negative.md);
the follow-up default-off exact M=8 Q/K RMSNorm + RoPE fusion at vLLM
`d503073ec` plus kernels `9525343e7` passed its four-card component gate
256/256 and reduced isolated launches 144 -> 48 per target cycle. Both fresh
full suites were teacher exact 13/13, cross-start exact 13/13, cache-zero
13/13 + 13/13, long-then-next 2/2 + 2/2, and rollover 1/1 + 1/1. Its medians
were 34.233360 and 33.190702 tok/s, so the lower start missed the approved
record by 0.248228 tok/s (-0.7423%); no payload was staged. Resume from the
[fusion negative note](experiments/laguna-s-2.1-xpu-b70/notes/2026-07-22-exact-m8-qknorm-rope-fusion-negative.md).
The preregistered A-B-B-A follow-up corrected the earlier interpretation:
fusion beat both adjacent controls in headline throughput, cycle time, and
11-12/13 prompt rows, but the per-position DFlash acceptance histograms
differed and the candidate's lower 33.302984 tok/s start still missed the
record by 0.4065%. All four starts remained teacher exact 13/13, cross-leg
exact 13/13, and cache-zero. It is strong directional evidence but failed the
frozen promotion gates; no fifth run, payload, or submission was allowed.
Resume from the [crossover result note](experiments/laguna-s-2.1-xpu-b70/notes/2026-07-22-qknorm-rope-crossover-result.md).
The Laguna-only XPU auxiliary-stream gate for the complete shared-expert MLP
was bitwise exact on all four cards but a decisive performance negative:
overlapped pairs were 10.03-10.77% slower on every B70. The preregistered gate
therefore stopped the lane before any endpoint. The failed candidate is
preserved at vLLM `3d1222281` and explicitly reverted at `f239a1014`; the
experiment restored the source tree to `d503073ec`. Resume from the
[negative result](experiments/laguna-s-2.1-xpu-b70/notes/2026-07-22-shared-expert-xpu-stream-negative.md).
The exact BF16-input/FP32-sigmoid M=8 router specialization at vLLM
`689ee3643` plus kernels `af6811818` passed its four-card component gate and
removed about 0.45-0.48 ms per 47-layer isolated cycle. In the frozen cold
endpoint phase it remained teacher exact 13/13 and cache-zero on both starts,
won 10/13 paired rows, improved the paired median 0.7138%, and saved 1.0301 ms
per target cycle. However, the official candidate headline was
32.310122 versus the adjacent control's 32.969012 tok/s (-1.9985%), so the
preregistered early-stop rule forbade B2/A2 and no payload was staged. Resume
from the [phase-1 result](experiments/laguna-s-2.1-xpu-b70/notes/2026-07-23-m8-bf16-router-topk-preregistration.md).

The previous approved record stacked the exact shared-elementwise bundle with
the exact Q/K RMSNorm + RoPE bundle on the route-interleaved MoE base. The
shared bundle preserves the incumbent BF16 rounding boundaries, removes 94
launches per target cycle, and saves 0.699-0.723 ms/cycle on every card. In a
preregistered A-B-B-A endpoint, candidate starts measured **34.550701** and
**33.894985 tok/s** versus adjacent controls at 32.826917 and 33.273435.
Both comparisons passed every causal gate: candidate row wins were 12/13 and
13/13, paired medians improved 4.211% and 4.225%, and target-cycle time fell
3.490 and 4.015 ms. All four legs were teacher exact **52/52**, cross-leg
exact, cache-zero **52/52**, long-next **8/8**, and rollover **4/4**. The
conservative lower candidate beats `cmrwot89400gqnz014oodtlbp` by
0.456058 tok/s (+1.36385%). LocalMaxxing approved it as
`cmrx6p5dv001bo4017hb7sixz`. Resume from the
[record note](experiments/laguna-s-2.1-xpu-b70/notes/2026-07-23-shared-elementwise-qknorm-stack-record.md)
and compact
[packet](data/laguna-s-2.1-shared-elementwise-qknorm-stack-record-20260723.json).

The current approved record adds the raw-byte- and endpoint-qualified
Breakable M8 graph runtime without changing the exact model stack. In the
preregistered fresh-service A1-B1-B2-A2 crossover, graph starts measured
**92.760717** and **92.163522 tok/s** versus eager controls at 34.491164 and
34.591123. The conservative lower graph start is a 2.71909x result over the
prior 33.894985 record. Both adjacent comparisons passed every causal gate:
graph won 13/13 and 12/13 rows, paired medians rose 169.421% and 169.365%,
target-cycle time fell 55.049 and 54.220 ms, and acceptance drift stayed below
0.000308. All four legs were canonical-teacher and cross-leg bitwise exact
**52/52**, cache-zero **52/52**, long-next **8/8**, and rollover **4/4**.
Each graph service captured and replayed the audited 146/145 segment topology
exactly once on ranks 0 through 3; the eager controls had no graph rows. Two
independent raw-artifact audits found no discrepancy or prior-run
contamination. LocalMaxxing approved the conservative result as
`cmrzjb7i906x4o401egrnm05m`. Resume from the
[record note](experiments/laguna-s-2.1-xpu-b70/notes/2026-07-24-m8-breakable-graph-record.md)
and compact
[packet](data/laguna-s-2.1-m8-breakable-graph-record-20260724.json).

The latest approved record keeps that exact Breakable graph runtime fixed and
adds persistent exact q2..q8 attention metadata. Builder-owned fixed-address
query-offset, KV-length, and expanded-block-table buffers replace repeated
per-layer metadata construction; pointer, owner, offset, active-view, and
metadata-object signatures fail closed on drift. In the preregistered
graph-vs-graph A1-B1-B2-A2 crossover, metadata-on starts measured
**94.920039** and **95.066548 tok/s** versus metadata-off controls at
92.549618 and 92.877971. The conservative lower candidate is +2.990898% over
the prior approved record. Both pairs won 13/13 rows, improved paired medians
2.351%/2.561%, saved 0.911/1.648 ms per aggregate target cycle, and kept
acceptance drift below 0.000308. Canonical exactness was 52/52, cross-leg
exactness 39/39, cache-zero 52/52, long-next 8/8, and rollover 4/4. An
independent raw-artifact audit approved the lower B start. LocalMaxxing
approved it as `cmrzrd4tf001ipa013xpx4kid`. Resume from the
[record note](experiments/laguna-s-2.1-xpu-b70/notes/2026-07-25-m8-persistent-attention-metadata-record.md)
and
[packet](data/laguna-s-2.1-m8-persistent-attention-metadata-record-20260725.json).

The subsequent persistent KV-cache-view diagnostic is an exact timing stop.
All four fresh arms produced the same 272-token greedy output with zero cached
tokens, and compiled-FA2 q2-through-q8 parity passed on all four cards. The
candidate saved `0.313646 ms` median view-preparation time and `0.085631 ms`
whole-replay time, but shifted `0.145214 ms` into median post-replay
synchronization and made the fresh generation `0.138944 s` slower. No endpoint
or submission is authorized. Preserve the
[negative result](experiments/laguna-s-2.1-xpu-b70/notes/2026-07-25-persistent-kv-cache-views-preregistration.md)
and
[structured summary](data/laguna-persistent-kv-views-diagnostic-20260725.json).

The one-replay current-stream XPU event diagnostic completed exactly and
stopped without a benchmark or submission. Both fresh 272-token arms were
bitwise identical with zero cached tokens, and all four ranks reported the
unchanged 146 graph, 97 collective, and 48 eager-attention intervals. Rank 2
was the slowest rank-local timeline at `124.614464 ms`; using only that rank's
own intervals, graph work was `80.297412 ms` (64.436671%), collective
callbacks `34.930532 ms` (28.030881%), and attention `9.386520 ms`
(7.532448%). An independent raw-artifact audit approved the sealed closure.
This remains rank-local guidance, not a proven global TP4 critical path, and
XCCL cross-stream completion is still unproven. The source map found a
two-interval prefix, 48 identical six-interval layer bodies, and one final
graph tail. The largest repeated graph class is post-attention normalization
plus local dense/MoE work at `30.126720 ms` on selected rank 2. The then-active
next lane was an isolated arithmetic-identical M=8 local-MoE device-kernel
candidate with unchanged graph coverage. The required post-run source audit
closed a pure Python
replay-loop campaign: same-stream XPU event intervals measure queued device
work rather than the host callback gap, while prior host telemetry already
bounded all 146 graph replay calls at `2.097430 ms` median per M8 replay.
Resume from the
[completed diagnostic](experiments/laguna-s-2.1-xpu-b70/notes/2026-07-25-m8-current-stream-event-profile-preregistration.md)
and
[structured summary](data/laguna-s-2.1-m8-current-stream-event-diagnostic-20260725.json).

The frozen routed-W1 N128 follow-up completed only A1/B1 after the local-NVMe
recovery gate. Both starts were canonical-teacher exact 13/13, cache-zero
13/13, long-next 2/2, rollover 1/1, and operationally clean. N128 reduced
target-cycle time by 3.752688 ms, but its 34.029105 tok/s headline lost to
N64 at 34.969419 tok/s (-2.6890%), it won only 3/13 rows, and its paired
median fell 3.0578%. The frozen analyzer classified
`phase1_failed_stop`; B2/A2 were not run and no payload or submission was
made. Preserve the [closed negative](experiments/laguna-s-2.1-xpu-b70/notes/2026-07-23-w1-n128-nvme-phase1-failed-stop.md)
and [packet](data/laguna-s-2.1-w1-n128-nvme-phase1-failed-stop-20260723.json).

The target-side follow-up audit found no clean untried MoE or
attention-adjacent lever: the apparent candidates collapse into previously
measured W1 N32/N128, QKV/O occupancy, remote-zero, native shared projection,
gather, capture, or fusion negatives. The then-active lane was instead a distinct
default-off Laguna DFlash context-KV workspace rooted directly at approved
record vLLM `ef334233d`. The host-only implementation is frozen at candidate
vLLM `4459910e2ac5a7b552887fc0a3f3e3cf9a4701c0` after 38 focused tests,
full-file pre-commit checks, and two independent source-freeze approvals. It
reuses exact-shape eager buffers only for steady
context widths 1 through 8 while preserving the incumbent RMSNorm, BMM, bias,
layout-copy, K-RMSNorm, RoPE, and cache-write order. Prompt/prefill widths stay
on the incumbent path. No XPU or model action is authorized until a separate
four-card raw-bit component gate is committed and independently reviewed.
The unexecuted gate tooling now exists and passes host syntax, lint, and 22
analyzer tamper tests. Two independent reviews approved committing and
consuming the exact packet once for component-only XPU evidence; no endpoint,
benchmark, or submission is authorized.
The first committed packet `bd84a0384` failed closed before native import
because its per-rank `xpu-smi discovery` incorrectly expected the unfiltered
four-card list after `ZE_AFFINITY_MASK` had reduced discovery to one card. Its
run root is preserved and the packet is permanently consumed. The repaired
tooling records unfiltered discovery in the launcher and validates exactly one
filtered card in each worker. Two independent reviews approved committing that
repair and consuming it once for one new component-only attempt.
That `c547b2a43` packet passed the complete exact component on physical card
zero, then failed closed before native import on card one because `xpu-smi`
renumbers the single affinity-filtered device to logical ID zero. Its UUID,
BDF, and DRM identity remained correct. Preserve the sealed run; the packet is
terminally consumed. The narrow repair requires filtered logical ID zero on
every leg while binding the stable identity fields to the selected physical
ordinal. Two independent reviews approved committing the repair and consuming
it once for another component-only attempt.
That `145050c5d` packet completed `exact_component_pass` on all four physical
cards. Its offline analyzer then false-rejected projected V because it
required storage offset zero, although V is the second view of contiguous
`[2,L,C,nkv,hd]` and correctly begins at `L*C*nkv*hd`. Do not rerun hardware:
the packet is terminally consumed and all four worker artifacts are sealed.
Commit and review the analyzer-only fix, then audit the existing evidence into
a fresh owner-private directory under the separate internal-NVMe analysis
root, recording the clean analyzer commit and exact analyzer-file hash. Two
independent reviews approved that commit and one offline-only audit; no
hardware rerun is allowed.
The sealed offline audit passed as `exact_four_card_component_pass`: 128
changing-input rows and 1,536 raw boundary/cache equality assertions passed
across all four cards, with stable workspace pointers, unchanged weights, and
capture-true rejection leaving workspace/cache/input state untouched. Promote
the [structured component summary](data/laguna-s-2.1-dflash-context-kv-component-20260725.json).
This is component-only evidence, not throughput or endpoint authority. Next,
design a fresh non-timing TP4 full-runtime selector-off/on exactness gate over
the real loaded model/cache lifecycle and full greedy target/draft/rejection
tokens and text. Do not run a cold crossover yet.
Resume from the
[DFlash workspace preregistration](experiments/laguna-s-2.1-xpu-b70/notes/2026-07-25-dflash-context-kv-workspace-preregistration.md).
The completed current-stream diagnostic still records rank-2 repeated graph
segments of `25.393732 ms` pre-attention, `23.700404 ms`
post-attention/local-O, and `30.126720 ms` post-attention/local-MLP; it does
not authorize collective capture or an attention rewrite. The
prior full-attention subgraph attempt is closed
because SYCL graph capture rejects FA2 work-group scratch memory. Shared-expert
GEMM occupancy remains a secondary lane. The
N128 endpoint treatment is closed. Do not stack
the BF16 router candidate into another endpoint trial unless a future
preregistered design explicitly isolates its contribution. Do not revisit
route buffer fills or progressively serialize the whole model into opaque
graph islands. Preserve the current record heads at
vLLM `0ce373a3115fb4498c5e7a041d4fc9212fd6b5ca` plus kernels
`4772f727590c51b72add79350b913d098cf67872`; enable
`VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE=1` and
`VLLM_XPU_LAGUNA_M8_QKNORM_ROPE=1` with the validated Breakable graph
contract only in the pinned Laguna record command.
The first next experiment, a down-only shared-expert native-M8 BF16 MM
component screen at vLLM
`75d4660463407975c16bd33711499ca560bf2034`, passed its frozen local-NVMe
four-card gate. It changes only shared `down_proj` from the stride-zero
M1-lane BMM representation to native M8 MM; gate/up, transforms, elementwise
boundaries, routed work, and reductions stay unchanged. All four physical
cards passed 128 changing exactness epochs, the actual checkpoint-selected
`RowParallelLinear` path, and 32 post-timing replay epochs. Every card won
31/31 ABBA blocks and saved 0.598-0.647 ms per complete 47-layer cycle
(25.8-27.1%). The aggregate analyzer independently regenerated the fixture
hashes and recomputed every timing result. Preserve the
[preregistration](experiments/laguna-s-2.1-xpu-b70/notes/2026-07-23-shared-down-native-m8-mm-preregistration.md),
[component result](experiments/laguna-s-2.1-xpu-b70/notes/2026-07-23-shared-down-native-m8-mm-component-pass.md),
and [structured summary](data/laguna-s-2.1-shared-down-m8-component-pass-20260723.json).
This pass authorizes only construction and audit of dedicated cold-counter
tooling. Counter execution, an endpoint, model generation, a payload, and a
submission remain unauthorized until their later frozen gates pass. The
external USB remains backup-only.
The later frozen shared-down counter capture was bitwise exact and globally
3.240% faster in GEMM time, but failed four of eight matched pairs and every
card's complete timing/XVE guardrail set. It is terminal before endpoint work.
The subsequent gate-only native-M8 screen at vLLM `3dae2ce383a009624bc6ff3e8660851fab5c12e0`
was also exact and won 31/31 card-0 ABBA blocks, but its
`0.120856 ms` median saving missed the preregistered `0.150 ms` component
minimum; cards 1-3 and counters did not run. Preserve the
[threshold miss](experiments/laguna-s-2.1-xpu-b70/notes/2026-07-23-shared-gate-component-threshold-miss.md).
The active next lane is a newly preregistered pair of separate native-M8 shared
gate and up projections. It explicitly forbids the inexact merged gate/up
forms and requires at least `0.20 ms` median saving on every card before
counters. Resume from the
[gate+up preregistration](experiments/laguna-s-2.1-xpu-b70/notes/2026-07-23-shared-gate-up-native-m8-mm-preregistration.md).
The pair implementation's future-execution identity is now vLLM
`503f7784cf9d1704109b1e4650427fb4f417d604`; XPU kernels remain
`c59aaadbbfd350c2b5f4ad663e247c2811ae3181`. Stage-0 integration found that
the prior `144f77608b6596677a9f6653b63b315e573b38b6` seal could bypass its
runtime validator when exact-attention or the pair selector was disabled
after construction, and cached selectors could hide raw drift. The corrected
source forces any still-bound verifier-M8 pair into the fail-closed contract
and validates every runtime selector as a raw literal. Final CPU-only
validation is 168 passed with three explicitly skipped device tests; Ruff,
diff checks, and two independent read-only audits passed. Three small XPU
primitive tests had run unintentionally before the explicit opt-in guard was
added. They loaded no model and produced no timing, but violated the frozen
Stage-0 ordering and are quarantined rather than used as evidence. Preserve
the
[implementation/incident note](experiments/laguna-s-2.1-xpu-b70/notes/2026-07-23-shared-gate-up-implementation-and-pytest-incident.md)
and the historical
[post-incident reaffirmation](experiments/laguna-s-2.1-xpu-b70/notes/2026-07-23-shared-gate-up-post-incident-reaffirmation.md).
The future-execution authority is the
[runtime-guard fix and unchanged-gate reaffirmation](experiments/laguna-s-2.1-xpu-b70/notes/2026-07-23-shared-gate-up-runtime-guard-fix-and-reaffirmation.md).
The pair-specific Stage-0 screen is now a production-validated pass at
tooling commit `79577851f76f078d3150a8300bad670670b4d48c` and packet-only
commit `8bb2af9ef2657aa17687bf323f310a2efaf6c902`. Its first and only authorized
run completed all 128 changing epochs with 1,152/1,152 raw-BF16 and Torch
comparisons equal, exactly two ordered native MMs, 22 incumbent BMMs, zero
fallbacks, and all 30 corruptions rejected before a primitive. Preserve the
[Stage-0 pass note](experiments/laguna-s-2.1-xpu-b70/notes/2026-07-23-shared-gate-up-native-m8-mm-stage0-pass.md)
and
[structured summary](data/laguna-s-2.1-shared-gate-up-m8-stage0-pass-20260723.json).
The subsequent pair-specific four-card component campaign is also a final
verified pass. Tooling commit
`4cef996c94502ad06233caa55d5be019d13a5114` and packet-only authorization
commit `f04d7431224017859ef892b1251f2a87fc1dee4a` produced 128 pre-timing plus
32 post-timing exact epochs per card, 5,760/5,760 raw-BF16 and Torch
comparisons equal, and identical cross-card output digests. Every physical
card won 31/31 A-B-B-A blocks; median savings per complete 47-layer ordered
gate+up cycle were 0.285200, 0.308360, 0.321073, and 0.348841 ms against the
frozen 0.20 ms minimum. Preserve the
[component pass note](experiments/laguna-s-2.1-xpu-b70/notes/2026-07-24-shared-gate-up-native-m8-mm-component-pass.md)
and
[structured summary](data/laguna-s-2.1-shared-gate-up-m8-component-pass-20260724.json).
The subsequent first-and-only cold-counter campaign completed all 16
packet-authorized arms at tooling commit
`34db11e8f9cee45e455390da7961e28c959b0441` and packet-only commit
`a8c8c595978e1803a354869d53cef77cae79781c`. All gate/up outputs were
raw-BF16 exact across arms and repeats. The frozen analyzer nevertheless
failed on its preregistered zero-SLM-traffic rule: all 416 rows reported the
same 245,760 SLM bytes read and written with zero bank conflicts. That rule is
not weakened after capture. More importantly, a diagnostic summary of the
immutable retained rows also fails required matched comparisons on cards 1,
2, and 3, card aggregates on 1 and 3, and per-card XVE/occupancy guardrails.
The diagnostic global GPU-time ratio of `0.9935168` cannot rescue those
failures. This lane is terminal before endpoint work; do not rerun or
reinterpret it. Preserve the
[terminal negative note](experiments/laguna-s-2.1-xpu-b70/notes/2026-07-24-shared-gate-up-native-m8-mm-counter-terminal-negative.md)
and
[structured summary](data/laguna-s-2.1-shared-gate-up-m8-counter-terminal-negative-20260724.json).
No model generation, payload, network access, submission, or reboot occurred.
The then-active lane was a materially different exact post-W2 fusion. It keeps
the incumbent route-parallel W2 unchanged and proposes one strict M=8 kernel
for the existing `MoeGather -> laguna_m8_scale_add` tail. The current record
already fuses scale with shared add, so the honest structural target is
`94 -> 47` launches per 47-layer target cycle. The
[preregistration](experiments/laguna-s-2.1-xpu-b70/notes/2026-07-24-routed-gather-finalize-fusion-preregistration.md)
freezes both BF16 rounding boundaries, explicit combined-output ownership,
fail-closed scope, and a per-card `0.15 ms/cycle` component minimum before any
endpoint. Stage 0 is now frozen at vLLM
`5519c08c168838b7e0a418499603b907f127cbf9` and XPU kernels
`4772f727590c51b72add79350b913d098cf67872` (production implementation
`2020d1921de1af35356fce85a8a2f7703215612c`). The diagnostic companion
exposes the routed/scaled/final BF16 evidence boundaries through the same
arithmetic helper while compiling its stores out of the unchanged production
specialization. The native/static host-oracle suite passed 16/16, the focused
vLLM suite passed 22/22, and the expanded relevant vLLM suite passed 52 with
one explicitly skipped device test. Ruff, AST, C++ formatting, whitespace,
generic-path/W1/W2 identity checks, and five independent read-only audits all
passed. The CPU-built candidate `_moe_C` is sealed on internal NVMe with
SHA-256
`6a6794249421aceb51f14980a3e2c0b0a9d7b492abf2f8d25b129b86f099bc5b`;
it has not been imported. No XPU action, model load, endpoint, generation,
payload, network access, submission, or reboot occurred. Preserve the
[Stage-0 source freeze](experiments/laguna-s-2.1-xpu-b70/notes/2026-07-24-routed-gather-finalize-stage0-source-freeze.md)
and
[structured summary](data/laguna-s-2.1-gather-finalize-stage0-source-freeze-20260724.json).
The separate Phase-A tooling was frozen at
`1bc3db422daefd2c5e7fe915eaff8dfd850ec920` and its sole packet at
`180826bea272c73e6cf767df1b02fc0b80ef018a`. The first and only authorized
execution completed the five frozen discovery probes, then failed closed on
the first strict-idle sample before the campaign root, native import, tensor
allocation, or timing. The frozen parser expected `{"process_list":[]}`, but
the installed `xpu-smi ps -j` emits `device_util_by_proc_list` and a
post-failure diagnostic contained only the querying `xpu-smi` process itself.
The packet explicitly forbids retry, so this candidate is terminal and
unmeasured; do not rerun it, replace its packet, or infer a performance or
correctness result. Preserve the
[terminal preflight note](experiments/laguna-s-2.1-xpu-b70/notes/2026-07-24-routed-gather-finalize-phase-a-preflight-terminal.md)
and
[structured summary](data/laguna-s-2.1-gather-finalize-phase-a-preflight-terminal-20260724.json).
The active work is a materially distinct standalone `MoeGather` occupancy
retile rooted directly at the approved record commits. Its fixed M=8 geometry
uses six 64-work-item hidden shards per token, raising workgroup supply from
8 to 48 while preserving each literal slot-0-through-9 FP32 accumulation, the
final BF16 gather store, and the separate `laguna_m8_scale_add` launch. It is
not a retry or rescue of gather-finalize and receives no standalone endpoint;
a four-card component pass may only bank its conservative saving for a later
preregistered exact portfolio. Resume from the
[sharded-gather preregistration](experiments/laguna-s-2.1-xpu-b70/notes/2026-07-24-m8-gather-sharded-occupancy-preregistration.md).
No implementation, native build, XPU action, model load, or generation had
occurred at registration. The default-off source is now committed as a direct
child of the record kernels at
`7e6a74026a2a4370abcb7973d28bbc9d1ddd1be6`. Its static/CPU checks pass, its
oneAPI 2025.3 `_moe_C` is sealed on internal NVMe at SHA-256
`3a16e85f7b6f324246f89e03d8aa89c37f0d6097c59d0a323ab2822dccd6d99f`,
and final linked SPIR-V inspection confirms matched visible multiply/add and
conversion structure with the incumbent. Because both paths retain matching
`AllowReassoc`/`NSZ` permissions, device raw-bit exactness remains mandatory.
The host-only Stage-0 gates are now complete. The committed installed-schema
operational preflight passed with four exact self-observer rows and no foreign
XPU process; its canonical report is sealed on internal NVMe. The fixed
288-epoch fixture corpus (256 pre-timing plus 32 post-timing) independently
passes deterministic-byte, manifest-hash, all-65,536-BF16, FP32-edge,
all-1,024-mask, all-slot, zero-row, local-formula, canonical-map,
cancellation, and midpoint proofs. Preserve the
[host-gate note](experiments/laguna-s-2.1-xpu-b70/notes/2026-07-24-m8-gather-sharded-stage0-fixture-and-operational-preflight.md)
and
[structured packet](data/laguna-s-2.1-m8-gather-sharded-stage0-host-gates-20260724.json).
Stage 0 is still not authorized for a candidate primitive: commit both
mutually bound Phase-A and conditional Phase-B packets before any
candidate/native import or device action.
Preserve the
[source/build/IR checkpoint](experiments/laguna-s-2.1-xpu-b70/notes/2026-07-24-m8-gather-sharded-source-build-ir-checkpoint.md).
The later mutually bound packet pair passed separate validation, but its sole
Phase-A execution was terminated by the outer execution wrapper during the
65-second live-idle preflight. The consumed marker proves no campaign root,
candidate import, tensor allocation, model load, or generation occurred. Its
authorization was no-retry, so the sharded-gather lane is terminal and has no
correctness or speed result. Preserve the
[terminal preflight note](experiments/laguna-s-2.1-xpu-b70/notes/2026-07-24-m8-gather-sharded-preflight-aborted.md)
and
[structured result](data/laguna-m8-gather-sharded-preflight-aborted-20260724.json).

The active work is now an exact runtime-command-graph lane rooted directly at
the approved record vLLM commit. The default-off target-only M=8 selector is
committed at vLLM `e09f34a008c31cb4c691697215a6eff3aa2eb5be`: it disables
compiler/AOT lowering, keeps DFlash and all non-M8 target calls eager, pins the
graph output, and rejects replay-time tensor identity drift. The direct
collective component probe recorded its preregistered synthetic pattern of 97
all-gathers plus one final all-reduce.
Both first samples passed every gathered and fixed-rank BF16 sum boundary, but
all four ranks failed raw equality at the final all-reduce on changing-input
sample 2. Direct collective capture is terminal and will not be rerun.
Preserve the
[negative result](experiments/laguna-s-2.1-xpu-b70/notes/2026-07-24-m8-xccl-direct-runtime-graph-negative.md)
and
[structured result](data/laguna-m8-xccl-direct-runtime-graph-negative-20260724.json).
Subsequent exact-source review corrected the real target-model topology: one
embedding BF16 all-reduce first, followed by 96 deterministic BF16
all-gathers (48 attention O, one layer-0 dense MLP down, and 47 MoE combines).
The compact FP32 logits all-gather occurs after the model forward context and
is outside this graph lane. The segmented source checkpoint is vLLM
`0964fe3d1`; it keeps all 97 in-model collectives eager in persistent buffers
and records the unchanged noncollective kernels between them. Its corrected
four-card substrate gate passed 99,328/99,328 raw comparisons and every one of
508 input plus 508 tail freshness transitions, with 97 eager collectives and
98 graph segments per replay. Preserve the
[substrate pass](experiments/laguna-s-2.1-xpu-b70/notes/2026-07-24-m8-segmented-substrate-gate-pass.md)
and
[structured result](data/laguna-m8-xccl-segmented-substrate-pass-20260724.json).
This authorizes construction/review only of the actual target-model and PTI
trace/timing gate; it is not target exactness or performance evidence. That
real-model gate must pass before any endpoint. The approved record remains
unchanged.
Also preserve the DeepSeek option-4 branch and all `preserve/*` tags.
The Laguna storage policy changed on 2026-07-23: the active target and DFlash
draft are now hash-verified under
`/mnt/fast-ai/llm-models/laguna-s-2.1`, and live cache, temp, log, run, and
recovery-evidence paths must use the internal NVMe/ext4 filesystem. The
external Corsair `ntfs3` copy is backup-only; do not use it for live model
reads or benchmark writes. Frozen historical evidence keeps its original
paths. See the
[migration note](experiments/laguna-s-2.1-xpu-b70/notes/2026-07-23-laguna-usb-backup-only-nvme-migration.md)
and
[structured packet](data/laguna-s-2.1-nvme-model-migration-20260723.json).
No Laguna endpoint or worker is running. The host is now on clean boot
`0b7f98a5-e50a-46a5-81ea-15938b55317a`, kernel `7.0.0-28-generic`, with
kernel taint `0`; model services and the display manager are inactive under
`multi-user.target`. The boot-bound local-only recovery gate was required
before the recovered W1 campaign and passed after the four fail-closed
tooling-only preflights described below. Its first local root passed model
hashing, four-card discovery/mapping, and strict idle, then failed
closed before peer/XCCL/N64 because `UR_LOG_LOADER=level_info` is invalid for
the installed oneAPI 2026 logger syntax. Kernel delta and reject files were
empty; no N128 or model generation occurred. The immutable abort is documented
in the
[SYCL preflight note](experiments/laguna-s-2.1-xpu-b70/notes/2026-07-23-w1-n128-nvme-sycl-ls-preflight-abort.md).
The corrected second root also failed closed at `sycl-ls`, before peer, XCCL,
N64, N128, or model work, because the inherited loader path omitted the
installed oneAPI UMF library and both Level Zero adapters could not resolve
`libumf.so.1`. Its evidence manifest verifies, kernel delta and reject files
are empty, and taint remains zero. See the
[UMF preflight note](experiments/laguna-s-2.1-xpu-b70/notes/2026-07-23-w1-n128-nvme-umf-preflight-abort.md).
The third root confirmed that correction by enumerating all four B70s, then
failed closed at process load for the standalone peer binary because its
command did not inherit the same path and could not resolve `libsycl.so.9`.
No peer kernel, XCCL, N64, N128, service, or model generation ran; the
manifest verifies, kernel delta and rejects are empty, and taint remains zero.
See the
[peer-loader preflight note](experiments/laguna-s-2.1-xpu-b70/notes/2026-07-23-w1-n128-nvme-peer-loader-preflight-abort.md).
The fourth root passed that peer gate and the first exact XCCL command, but
failed closed on a log-framing assertion because `torchrun` concatenated
multiple rank markers onto shared physical lines. Every required rank marker
was present exactly once and the command exited zero; the second XCCL pass,
N64, N128, service, and model generation did not run. Its manifest verifies,
kernel delta and rejects are empty, and taint remains zero. See the
[XCCL framing preflight note](experiments/laguna-s-2.1-xpu-b70/notes/2026-07-23-w1-n128-nvme-xccl-log-framing-preflight-abort.md).
The next freshly rooted gate passed completely: all 118 model hashes, exact
four-card mapping and idle, oneAPI enumeration, peer read, two independent
exact XCCL passes, four historical N64 oracles, four production N64 liveness
checks, a 66-second/41-sample idle seal, and final kernel/reject capture.
N128 and model generation remained false; the evidence manifest verifies and
taint remains zero. See the
[recovery pass note](experiments/laguna-s-2.1-xpu-b70/notes/2026-07-23-w1-n128-nvme-recovery-gate-pass.md)
and
[structured packet](data/laguna-s-2.1-w1-n128-nvme-recovery-pass-20260723.json).
It authorized A1 as the first post-recovery model generation. The frozen
campaign then ran A1/B1 and closed at the failed phase-one gate summarized
above; no further recovery action or reboot is pending.

## Optimization Transition

The Qwen3.6 27B Q4_0/DFlash optimization lane was closed on 2026-07-13. Its
`>=100 tok/s` TP1 and `>=200 tok/s` multi-B70 single-session objectives were
not reached. The final strict one-B70 record is `47.818818 tok/s`, approved by
LocalMaxxing as `cmrjbx8bc02g8mj01yzz2v701`. The authoritative closeout is
[`notes/2026-07-13-qwen27-dflash-sycl-closure.md`](notes/2026-07-13-qwen27-dflash-sycl-closure.md).

The investment-gated DeepSeek V4 Flash vLLM/XPU lane ran from 2026-07-13
through its 2026-07-21 closeout for one active generation on four B70s. It is
now paused. The frozen source was
`deepseek-ai/DeepSeek-V4-Flash` revision
`60d8d70770c6776ff598c94bb586a859a38244f1`. The first runnable candidate is
the uniform-K160 `0xSero/DeepSeek-V4-Flash-180B` smoke checkpoint at revision
`7c360e1cd4a5168099dbc54d16d929bf6df04990`. It is a 96.026 GiB standard
safetensors artifact with 160 experts in every layer, so explicit TP4 expert
parallelism assigns 40 experts per rank without heterogeneous loader surgery.
It is not yet the quality-certified final model: its hash layers are pruned,
its calibration is not reproducible, and its published ranking is not true
REAP. A later
official-source teacher and hash-preserved nested pack remain the quality path.

The controlling plan is
[`plans/2026-07-13-deepseek-v4-flash-b70-investment-gated-plan.md`](plans/2026-07-13-deepseek-v4-flash-b70-investment-gated-plan.md),
with the current handoff at
[`experiments/deepseek-v4-flash-reap-xpu-b70/HANDOFF.md`](experiments/deepseek-v4-flash-reap-xpu-b70/HANDOFF.md).
The user explicitly authorized the frozen K160 download on 2026-07-13. It is
now complete, cryptographically verified, and promoted to
`/mnt/fast-ai/llm-models/deepseek-v4-flash-xpu/current-k160`. The official-source
transfer was started, then paused without a completed weight shard so the
runnable K160 could take priority; it remains resumable later for teacher
evidence. The nonspeculative lane has crossed 40 tok/s, so speculation is now
permitted as a separate measured lane. It must retain exact target verification
and must not be mixed with the base record. The archived Qwen detail below
remains resume evidence, not an instruction to continue experimenting.

The promoted nonspeculative runtime is now vLLM `a681dbb2b` plus XPU kernels
`6522849b0` and the exact-version oneCCL 2021.17.2 size-routed, wide-epoch
runtime at `48fda4f0e`.
Persistent graph replay, native mHC, context-bounded sparse work, and direct
paged FP8 attention all pass. The current strict TP4+EP single-session record
uses split QK/LSE plus 8-by-64 tiled PV, a mutation-declared TP-only in-place
all-reduce for the 87 contiguous BF16 `[1,4096]` decode reductions, selective
W8A16 for four high-value projection families, and an exact clamp-at-10
SwiGLU plus per-128 E4M3FN quant producer for the W8A8 shared-down path. Exact
router normalization and direct M=1 routed-MoE gather raise the trustworthy
nonspeculative record to **43.766673/43.698550 tok/s** median with
`43.226357/43.186344` p10. Two further rollover suites reach
43.694210/43.667908. The same-build direct-off control is
41.991191/42.155092, so direct fusion removes 0.84-0.97 ms/token. All 48 strict
rows are cached-zero and 70 independent exact captures pass. Evidence is in
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-direct-routed-moe-wideepoch-record.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-direct-routed-moe-wideepoch-record.md),
and LocalMaxxing approved `cmrmnp7h81nntmj01lfenydgj`. The preceding
41.733256 native-router row `cmrmjd3io1nn1mj013stqoe4b` remains superseded
speed evidence. The older
`40.1357239` LocalMaxxing row `cmrm601ig1hsmmj017npoivfd` remains historical
speed evidence, but consecutive changed-prompt testing later proved its
unmodified large-SYCL-allreduce identity was not repeatability-safe. Evidence
for the repair and promoted identity is
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-kv-repeatability-and-oneccl-allreduce-routing.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-kv-repeatability-and-oneccl-allreduce-routing.md).
The corrected `40.170350` row `cmrmebmzg1nm0mj01k30nv6vw` remains the
superseded repeatability-repair authority.
The current target-verified speed record is DSpark7 with target PIECEWISE,
private breakable draft PIECEWISE at exact M=7, a persistent sharded W2
transaction, W1-only replication, exact M=8 strided-batch compressors,
selective M=8 W8A16, MXFP4 N128, exact native M=8 router normalization, and a
guarded sharded target-argmax/native target-token rejection transaction:
**80.820052 tok/s** median with `71.669556` p10. Independent strict suite
medians are 80.820052 / 76.900178 / 78.287226 tok/s;
36/36 realistic requests are fresh and cache-zero, and four six-case exact
suites pass before, between, and after the performance suites. The unchanged
K160 target verifies all accepted tokens at M=8. Evidence is in
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-18-sharded-target-argmax-record.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-18-sharded-target-argmax-record.md).
LocalMaxxing approved `cmrquta9905w3lg013m5vxoqx`. The preceding M=8 router
record remains approved as `cmrqp2uoa05ublg01lh6yluj8`. The preceding W8A16/N128
record remains superseded evidence at 78.288267 tok/s,
`cmrqlp9je05thlg01q4igkk0x`; the compressor record remains at 71.506808 tok/s,
`cmrql07qs05t4lg01p86jjybx`. The preceding W1-only
replication record remains superseded evidence at 67.501117 tok/s,
`cmrqjhpmz05snlg01ujiehc0u`; the persistent Markov record remains at 66.479103,
`cmrqiovsv05s6lg012d8v5nz8`. The preceding exact
QNorm-M2 + route-direct MTP1 record remains superseded evidence at 63.851301
tok/s, `cmrocpuhq029hlg01g3yzglko`.
The record's exact follow-up cycle attribution is complete. The eager Markov
sampler is the largest draft-side scope at about 10.50 ms/cycle. Isolating it
in a separate reusable graph preserves exact output but not its 83 kernels or
14/15 collective breaks and falls to 62.460903 tok/s; combining sampler and
model replay corrupts output. A fused three-stage context-WKV projection cuts
its local scope from 1.914 to 1.303 ms and passes 18/18 ordered exact canaries,
but two strict medians are only 64.269762/64.244449 tok/s. Both candidates are
default-off and no LocalMax submission was made. Evidence and the next
device-resident sampler/acceptance/commit boundary are in
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-18-dspark-cycle-profile-and-fusion-closure.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-18-dspark-cycle-profile-and-fusion-closure.md).
The ordered continuation plan is
[`plans/2026-07-16-deepseek-v4-flash-b70-100-200-tps-roadmap.md`](plans/2026-07-16-deepseek-v4-flash-b70-100-200-tps-roadmap.md).
It preserves the current record while pursuing four explicit options:
high-value target fusion, TP4 communication/cycle restructuring, deeper
target-verified speculation, and a fixed-geometry Intel SYCL/Level Zero
decoder. The fixed-M2 finite event chain is now closed before model load. It is
exact in two 40-epoch eager runs, with rank skew, and in fixed-address graph
replay, but its 5.60-5.70 ms eager saving falls to only 0.109546 ms/cycle once
the ordinary comparator is also captured. The production graph had already
removed the Python/c10d submission cost. The active path is now the Option-4
fixed-geometry decoder shell and cached real-model parity/replay corpus,
followed by exact M=4/M=8 verifier economics and held-out deeper-speculation
evaluation. The first shell artifact is complete: a 150 MiB content-addressed
real M=2 corpus captures 87 TP4 reductions and 85 MHC boundaries per rank, and
the no-model four-B70 worker passes 70/70 full fixed-address replays at a
4.209382 ms slowest-rank median. Evidence is in
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-17-m2-real-cycle-corpus-and-replay.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-17-m2-real-cycle-corpus-and-replay.md).
The first M-width decoder-shell extension now passes its component gate while
retaining proven segmented M=2 collectives: fixed M=4 MHC saves 1.423781
ms/cycle and fixed M=8 saves 4.311293 ms/cycle, with 16 changed eager schedules
and 70/70 graph replays exact on all four cards. A single wide `[4,4096]` BF16
collective is blocked by repeatable oneCCL corruption, so its faster timing is
excluded. This is not an endpoint record or an acceptance result. Next is
guarded integration against true sequential verifier tensors, complete-cycle
economics, and the frozen held-out predictor gate. Evidence is in
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-17-m4-m8-fixed-mhc-component-gate.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-17-m4-m8-fixed-mhc-component-gate.md).
The fresh post-portfolio eager diagnostic now attributes **17.8497 ms/cycle**
to noncollective device work versus 19.4779 ms before the promoted portfolio,
a measured 1.6283 ms reduction. Dense GEMMs remain 6.5639 ms and compact
routed MXFP4 remains the largest open kernel family at 3.9424 ms. oneCCL and
host durations remain profiler-distorted and excluded. Evidence is in
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-17-mtp1-postportfolio-eager-cycle-profile.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-17-mtp1-postportfolio-eager-cycle-profile.md).
The subgroup-split/SLM producer is now closed by an incremental upper bound
before implementation. Its best possible all-remote comparison is only about
0.123 ms/cycle above the already-promoted route-direct path, and all-remote has
no local gate/up arithmetic for subgroup splitting to accelerate. No source,
build, service, or GPU experiment was made. The fixed-M2 producer/allreduce/
consumer upper bound then passed twice and exposed two missing device edges:
the Arc LL ring discarded incoming producer dependencies, and native MHC
needed a one-BF16 graph-visible completion witness. The guarded finite chain
passed exact eager and graph correctness, but failed its graph performance
gate at only 0.109546 ms/cycle saved. It is closed before service and is not a
speed result. Evidence is in
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-17-tp4-m2-event-chain-closure.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-17-tp4-m2-event-chain-closure.md),
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-17-tp4-m2-producer-allreduce-consumer-upper-bound.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-17-tp4-m2-producer-allreduce-consumer-upper-bound.md) and
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-17-mtp1-sg-split-incremental-upper-bound-closure.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-17-mtp1-sg-split-incremental-upper-bound-closure.md).
The exact M=2 MXFP4 N32/N128 follow-up is closed without promotion. N32
regresses. N128 saves 0.247-0.283 ms per 43 routed layers in the four-card
microgate, but two strict suites reach 62.649706/63.628477 tok/s while
same-binary N64 controls span 61.205692-63.101865. The isolated improvement is
inside observed service variance and does not robustly beat the record; keep
N64 and do not submit the single above-record row. The profile's 6.580 ms dense
bucket is also decomposed into already optimized or closed families. The next
noncollective candidate must be an architectural M=2 grouped-MXFP4 change with
a measured four-card ceiling of at least 0.50 ms/cycle. Evidence is in
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-16-mtp1-m2-mxfp4-policy-closure.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-16-mtp1-m2-mxfp4-policy-closure.md).
The integration gate now permits a predeclared portfolio of compatible exact
micro-wins whose conservative, non-overlapping lower bounds sum to at least
`0.50 ms/cycle`; it no longer requires every component to clear that threshold
alone. The first same-binary B-A-B portfolio combined M=2 QNorm/RoPE/direct-KV
with N128 MXFP4. It was exact and directionally positive: its two strict
medians averaged 62.606843 tok/s versus 61.895036 for the control, a
`+0.711806 tok/s` crossover. Both bundle rows remained below the 63.349928
record, so M=1/N64 stays promoted and no LocalMaxxing submission was made.
Ten post-confirmation exact suites passed 10/10, all cached-zero. Do not rerun
this two-item bundle without another compatible component that materially
raises its conservative ceiling. Evidence and the admission policy are in
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-16-mtp1-subgate-portfolio-policy.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-16-mtp1-subgate-portfolio-policy.md).
The first attempted third portfolio component is closed before service. The
old `0.470 ms` M=2 gather/shared-add estimate overlapped the unpromoted compact
scheduler and could not be added to N128. A new isolated four-card gate passes
140/140 changed graph cases per B70, including shared-buffer aliasing, but the
actual conservative incremental projections are only `+0.0038`, `+0.00007`,
`-0.0049`, and `-0.0007 ms/cycle`. Preserve XPU `5d1a72e` and vLLM
`eb4e39b4d` as default-off exact infrastructure; do not service-test it. The
frozen inventory now has no further exact, non-overlapping component with a
defensible `>=0.25 ms/cycle` incremental ceiling. Evidence is in
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-16-mtp1-isolated-gather-shared-add-closure.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-16-mtp1-isolated-gather-shared-add-closure.md).
The first architectural scheduler screen is also closed before service. A
route-compact M=2 Xe2 scheduler is exact on 84/84 changed-input card-0 cases,
but its worst valid all-remote EP route projects only 0.262 ms saved per 43
layers against the 0.50 ms gate. Favorable routes project 0.459-0.830 ms, so
the result is route-dependent and must not be promoted from an average. The
next screen must jointly remove M=2 remap, scheduling, and permuted-gather
traffic while preserving grouped expert reuse. Evidence is in
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-16-mtp1-m2-compact-scheduler-closure.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-16-mtp1-m2-compact-scheduler-closure.md).
The combined fixed-M2 route-direct boundary is now closed as well. An audit
invalidated the first misordered upper-bound graphs before integration; the
corrected remap -> GEMM1 -> clamped SwiGLU -> GEMM2 -> gather gate passes all
84 changed-input cases bitwise exactly. Its best 12-lane/generic-gather variant
saves 0.546-0.942 ms across 43 layers when local work exists, but only 0.414 ms
for the valid all-remote EP case, below the frozen 0.50 ms minimum. Four-lane
GEMM scheduling, direct gather, and 2/4/12-lane routed activations are preserved
losses. No service load or LocalMaxxing submission occurred. The next bounded
screen must remove a launch, led by source-direct GEMM1 folding the route map
into its first N tile. Evidence is in
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-16-mtp1-m2-route-direct-boundary-closure.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-16-mtp1-m2-route-direct-boundary-closure.md).
The first launch-removing follow-up is also closed before service. Fusing the
exact clamped SwiGLU calculation into GEMM2's A loader passes all 84
changed-input cases bitwise, but the GEMM2 output-N grid recomputes the same
activation for every N tile. It regresses every route with local work, with a
worst projection of `-9.133 ms` over 43 layers. Signed XPU experiment commit
`cfb0155` is preserved; do not integrate it. A deletion-only remap upper bound
is also marginal and unstable (`0.5002/0.4774 ms`). The next bounded audit is
paired gate/up production in the GEMM1 epilogue so each activated value is
formed once. Evidence is in
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-16-mtp1-m2-fused-swiglu-gemm2-closure.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-16-mtp1-m2-fused-swiglu-gemm2-closure.md).
That paired producer is now closed too. It passes `84/84` cases bitwise, but
the dual B payload and dual FP32 accumulator working set loses up to
`2.655 ms/43 layers` at GRF256 and `4.502 ms/43 layers` at GRF128. The
compiler reports no spill for the paired kernel, so lower occupancy and live
payload are the architectural limit. Single-workgroup and SLM-premapped remap
variants are also exact but top out at only `0.403-0.430 ms` fail-closed.
Preserve signed XPU commits `33e3ce4`, `5ea7608`, and `c069ed8`; do not service
test them. The next bounded producer design must split gate/up ownership across
subgroups and exchange rounded BF16 fragments through SLM, retaining the same
`0.50 ms` every-route gate. Evidence is in
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-16-mtp1-m2-remap-and-paired-gemm1-closure.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-16-mtp1-m2-remap-and-paired-gemm1-closure.md).
The exact gather/shared-output-add widening is also below the real gate. Its
real route-direct chain saves `0.535 ms/43 layers` for six-local work but only
`0.448 ms` on all-remote; an empty-routed fast path raises all-remote to
`0.470 ms` while leaving six-local at a noise-fragile `0.501 ms`. With that
fast path, literal remap deletion plus fused gather/add passes twice at
`0.538/0.527 ms`, leaving only `0.638-0.894 us/layer` for an implementation.
The upstream unique-route router is exact over 40 changing eager and 32 graph
epochs, but its best local-memory/subgroup-ballot emitter costs
`3.132 us/layer` (`0.125 ms/cycle`). The WG32/local-barrier shell costs only
`0.076 us/layer`, proving stable table construction is the blocker. Netting the
best exact emitter against the two deletion ceilings leaves only
`0.413/0.402 ms/cycle`, below the `0.50 ms` gate before downstream consumption.
Preserve signed XPU commits `820ecc5`, `4e2ce07`, `e7685b1`, `9360422`,
`579db66`, `c71bd3e`, `fdc4765`, and `70e3824`; no service test occurred. No
measured noncollective M=2 source boundary now clears the integration gate.
Evidence is in
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-16-mtp1-m2-gather-shared-add-gate.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-16-mtp1-m2-gather-shared-add-gate.md).
The preceding native M=2 MHC record remains approved LocalMaxxing evidence at
60.264242 tok/s, ID `cmrmvjbok1np3mj01p9il8486`.
The follow-up M=2 QNorm/KV fusion, exact M=2 in-place all-reduce, and MTP draft
local-argmax reduction are preserved exact candidates but did not independently
confirm above the record. They remain disabled; do not stack them without a new
complete-cycle performance reason. See
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-16-mtp1-post-record-fusion-sweep.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-16-mtp1-post-record-fusion-sweep.md).
Future deeper speculation must follow the freeze-before-reveal held-out policy
in [`experiments/deepseek-v4-flash-reap-xpu-b70/quality/spec-eval-contract-v1.json`](experiments/deepseek-v4-flash-reap-xpu-b70/quality/spec-eval-contract-v1.json);
the repeatedly used public 12-prompt suite is now a continuity screen, not
sufficient promotion evidence by itself.
The preceding target-verified record is row-exact attached MTP1 with a
strided-batch FP32 compressor and selective M=2 W8A16 verification:
**55.524496 tok/s** median with `52.029542` p10; independent support is
54.708889 tok/s. Twenty ordered exact captures pass, including ten after both
strict suites, and measured acceptance is 77.96%. LocalMaxxing approved
`cmrmgacdq1nmimj01i4sfqytp`. Both real compressor shapes pass 40/40 changing
eager and graph-replay comparisons on every B70. Evidence is in
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-mtp1-batched-compressor-record.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-mtp1-batched-compressor-record.md).
The uncorrected
50.74/50.10 MTP1 screen is
invalid because a later replay leaked prompt text after `437`; the repair is
`VLLM_XPU_V4_COMPRESSOR_M2_ROW_EXACT=1`. Evidence and failure detail are in
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-mtp1-rowexact-record.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-mtp1-rowexact-record.md).
The M=2 W8A16 record mechanism and four-card gates are in
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-mtp1-w8a16-m2-record.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-mtp1-w8a16-m2-record.md).
MTP2 reuse is closed without a speed result: its initial M=3 exact gate passes,
but second-position acceptance is only about 0.5-2.2% and a realistic request
deadlocks the engine. Do not test larger repeated-single-layer widths. See
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-mtp2-reuse-deadlock-closure.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-mtp2-reuse-deadlock-closure.md).
The gain comes from changing split FP8 QK from four 16-head/8-warp programs to
sixteen 4-head/16-warp programs; complete attention microbenchmarks improve
22-42% across short and 128-token C4/C128 shapes. The preceding 34.0671207
tok/s shared-expert-fusion result remains the matching control.
The previous 30.295 and 33.887 rows are invalid: generic scale prepacking also
transposed DeepSeek's special `wo_a` BMM scales, while its BF16 cache interpreted
them as canonical. Correcting that layout changed 77% of the first 96 greedy
tokens versus the invalid path. Corrected W8A16 is fast (`34.015` and `33.924`
tok/s) but the all-W8A16 path is rejected as a quality side lane: it matches
only 83.3% of early W8A8 greedy tokens and corrupts the frozen long
math-invariant case that W8A8 solves correctly. The promoted selective path
keeps shared-down W8A8 and passes that invariant. A later scheduler audit found
that the earlier MXFP4 N32 replay failure and N128 output changes came from an
in-kernel global-counter reset racing other workgroups. An ordered queue reset
makes both geometries bitwise exact over 40 changed graph epochs, but fixed N32
saves only 1.05 us per complete MoE layer and fixed N128 is 0.3% slower than
N64. The fix was diagnosed and explicitly reverted; keep N64. The
register-resident M=1 MHC post/pre
plus RMSNorm candidate is now closed before a server run: it introduced small
changed-state reduction drift and regressed `20.326 -> 22.427 us`, a projected
`0.179 ms/token` loss across 85 boundaries. Under the promoted selective W8A16
mix, fused FP8 output for the K4096 projections would also be unused. The
active work is therefore the ordered 87-collective producer/consumer boundary.
The prior general MHC/RMS fusion and oneCCL twoshots lanes remain preserved
losses.
The post-reboot 87-call oneCCL recording-path gate is closed. Forced recording
added only `0.051506 ms` against the mean of two exact controls, about one tenth
of the `0.50 ms` integration gate. Sequence/update-to-ring fusion is therefore
rejected; communication work must overlap or shorten the ring/consumer
critical path. Evidence is in
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-oneccl-recording-sequence-upper-bound.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-oneccl-recording-sequence-upper-bound.md).
The first two-stream hardware upper bound passes twice, hiding `0.642` and
`0.612 ms` only when the independent MHC stream is submitted before the ring.
The next source experiment is a test-only persistent consumer waiting on
epoch-tagged per-wire readiness, with a `<=1 us` marker-tax gate and
`>=6 us/boundary` slowest-rank savings gate. The cheaper LL-threshold-8192 path
saved only `0.169 ms/87`, and ARC LL256 corrupted every sequential-replay
epoch, so neither proceeds. Evidence is in
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-tp4-consumer-overlap-feasibility.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-tp4-consumer-overlap-feasibility.md).
Subsequent cheap gates are closed. LL workgroup geometry saved at most
`0.360 ms/87` against mean controls; exact two-round recursive doubling was
`0.0656 ms/87` slower than paired ring controls. Round-robin expert ownership
reached the intended interleaved map but failed the first changed-input replay
(`1369 -> 361 -> 1369` versus `1073 -> 437 -> 1073`), exposing a remaining
contiguous-expert assumption in packed MXFP4 state. A profiler trace confirms
87 collectives but cannot measure cross-device arrival skew because profiling
distorts and serializes the events. See
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-late-tp4-collective-and-placement-gates.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-late-tp4-collective-and-placement-gates.md).
The ring-readiness prerequisite passes. The default-off marker route is
bitwise exact over 24 changing epochs and adds at most `0.446 us` per boundary
against the faster paired control, below its `1 us` gate. The dependent
second-queue resident MHC consumer is rejected: its polling workgroup prevents
the ring queue from advancing, while a low-priority queue makes no progress.
The next microgate is a compact 256-thread version of the preserved in-ring
MHC post/pre boundary; require exact state and `>=6 us/boundary` savings before
a model server run. See
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-ring-readiness-marker-gate.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-ring-readiness-marker-gate.md).
Failure detail is in
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-resident-mhc-consumer-forward-progress-failure.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-resident-mhc-consumer-forward-progress-failure.md).
The following compact in-ring post/pre screen is also closed. Although its
256-thread isolated boundary was bitwise exact and more than 2x faster than the
honest promoted reference, 256- and 512-thread full-model graph runs produced
nondeterministic arithmetic. Exact 87-position, alias, multi-replay, rank-skew,
and dependent-producer probes all passed; stable double buffers and an explicit
producer barrier did not repair the model. No speed suite was run. A future
retry requires captured real-model intermediate tensors. The fresh record-lane
noncollective timeline is now complete. A corrected seven-token eager trace
attributes about 6.582 ms/token to dense GEMMs, 3.479 ms/token to MXFP4 MoE,
2.890 ms/token to the MHC kernel, and 1.452 ms/token to tuned split attention.
Do not add the enclosing `mhc_post_pre_m1_out` operator duration; that
double-counted the same device work in the earlier roughly 4 ms estimate.
Exact auxiliary-stream overlap, generic C4 projection fusion, approximate
Triton compressor GEMV, MHC geometry, and fixed MXFP4 N32/N128 have all failed
their hardware or full-model gates. The same-hour paired control remains
40.023086 tok/s. The next server-scale candidate must first demonstrate at
least 0.50 ms/token on an exact real-model producer/consumer gate, most likely
an exact heterogeneous attention prologue or a different large boundary. The
former compact-ring prerequisite is now complete: one real M=1 token captured
692 tensors (571,072,236 bytes; aggregate SHA-256
`6f8b7b9e7a1c78cc7a2005e2d92d292a80811405725dc43e190526e1be5a59eb`),
including all 87 reductions, all 85 MHC post/pre calls, the final post, and 42
real alias boundaries. The compact candidate is bitwise exact against that
corpus in eager mode and over eight graph replays. Full-model observers then
isolated the former corruption to a missing post-kernel graph-visible
completion edge in the direct oneCCL hook: one BF16 post-kernel read makes six
alternating requests exact. The repaired path is nevertheless closed because
it reaches only 34.708355 tok/s, 13.28% below the record, and changes all 12
strict-suite hashes. Do not retune or reintegrate this boundary. See
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-compact-ring-mhc-post-pre-closure.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-compact-ring-mhc-post-pre-closure.md)
and
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-record-lane-noncollective-gates.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-record-lane-noncollective-gates.md)
and
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-real-mhc-capture-and-graph-fence-closure.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-real-mhc-capture-and-graph-fence-closure.md).
The subsequent TP4 rank-arrival probe is measurement-closed. Its same-device
elapsed-clock design avoided invalid raw cross-GPU timestamp comparisons and
completed exact all-reduce gates, but every LL256 marker sample timed out,
including self, and some clock calibrations exceeded the 2% validity gate. No
full-model run, skew claim, speed claim, or LocalMax submission followed. Both
runtime patches are preserved in experiment/revert history and production
source is restored. See
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-tp4-rank-arrival-trace-closure.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-tp4-rank-arrival-trace-closure.md).
The next exact noncollective candidate is also closed. A native M=1 dual
Q1024/KV512 RMSNorm operator matches Triton's reduction order and passes
160/160 changing eager cases plus 32/32 changing graph replays across four
B70s. Although isolated timing projected 0.893-1.290 ms/token saved, paired
full-model testing regressed: 39.9928 and 39.9174 tok/s with the flag on versus
40.0950 for the same-commit flag-off control. Keep vLLM `d8d7cf198` and XPU
kernels `ef307a8` as default-off evidence; do not substitute a standalone
graph node again. The next candidate must remove the WQ_B producer boundary
with Q normalization/RoPE/KV insertion and clear an exact real-model gate.
See
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-native-dual-rmsnorm-graph-loss.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-native-dual-rmsnorm-graph-loss.md).
The following producer/consumer fusion succeeds. One M=1 Triton program now
performs Q RMSNorm/RoPE and direct UE8M0 FP8 KV-cache insertion while retaining
the old BF16 KV rounding point internally. It removes one graph node and the
temporary KV row. Four-card gates pass 160/160 changed eager cases and 32/32
graph replays bit-for-bit; the isolated boundary is 2.02-2.08x faster. Two
strict suites reach 40.1357/40.1037 tok/s, both above the old public record,
and LocalMaxxing approved `cmrm601ig1hsmmj017npoivfd`. Keep this fusion on and
continue into the preceding WQ_B projection epilogue. See
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-fused-qnorm-rope-kv-insert-record.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-fused-qnorm-rope-kv-insert-record.md).
The attempted WQ_B extension is now closed before model integration. A padded
M16 DPAS proof was 8.13x slower than oneDNN. A true-M1 subgroup proof reaches
23.559-23.700 us across the four B70s, but it is not bitwise exact and its fast
geometry spreads each 512-wide head across workgroups. The topology capable of
head-wide in-kernel normalization already costs 53.330-53.644 us for projection
alone, so it cannot clear the 11.63 us/layer complete-boundary gate. Preserve
XPU-kernel commit `de979b9` as a benchmark proof and do not connect it to the
model. The next bounded lane is the attached one-layer MTP, kept separate from
the 40.135724 tok/s nonspeculative record. See
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-wqb-m1-producer-fusion-closure.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-15-wqb-m1-producer-fusion-closure.md).
TP2+DP2+EP4 has been recovered for correctness, localizing its stall to a
oneCCL fast-SYCL switch cycle between disjoint TP and crossed DP communicators.
All safe fallbacks are performance-closed: the best fresh screen is only
`2.495917 tok/s`, so this topology must not displace the TP4 lane without a
communicator-scoped fast-SYCL or dedicated fused DPEP transport. Evidence is in
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-14-tp2-dp2-dpep-recovery.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-14-tp2-dp2-dpep-recovery.md).
The 40 tok/s base gate is now cleared. Speculation may proceed only as a
separate exact target-verified lane. Detailed history is in the lane handoff and
[`experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-14-xpu-graph-recovery-and-tp4-profile.md`](experiments/deepseek-v4-flash-reap-xpu-b70/notes/2026-07-14-xpu-graph-recovery-and-tp4-profile.md).

### Archived Qwen3.6 27B lane detail

- [Controlling requirements and execution plan](plans/2026-07-12-qwen27-tp1-max-speed-requirements-and-execution.md)
- [Archived experiment workspace](experiments/qwen27-dflash-sycl-b70/README.md)
- [Initial Q4_0 and speculation diagnostic](experiments/qwen27-dflash-sycl-b70/notes/2026-07-12-initial-dflash-mtp-benchmark.md)
- [Current MMVQ dispatch-fix result](experiments/qwen27-dflash-sycl-b70/notes/2026-07-12-mmvq-dispatch-fix.md)
- [Native DFlash draft-KV correctness isolation and first >68 result](notes/2026-07-13-qwen36-native-dflash-sycl-fa-isolation.md)
- [Prior promoted vLLM result packet](results/qwen36-27b-autoround-int4-b70/README.md)

The target product is one B70. The intended route combines persistent cached
development workers, B70-native offline weight packs, full useful device
replay/fusion, true multi-row Xe2 verification, and the fastest measured
target-verified MTP/DFlash policy. The main engineering target is a strict
quality-valid result above `100 tok/s` on the fixed realistic suite, with
higher workload-specific code throughput where DFlash acceptance supports it.

Phase 0 implementation now has direct MMVQ rows 1-17 correctness at 34/34,
strict graph-off medians of `25.783 tok/s` no-spec and `47.244 tok/s` MTP3,
and four independent MTP3 calibration medians of `47.976-49.708 tok/s` with
all cold/cached-zero gates passing. Mixed-suite DFlash5 is closed as a global
policy at `11.505 tok/s`; preserve long DFlash for targeted code/adaptive work.
The guarded persistent executable-graph cache now achieves exact direct replay
(381/384 hits) and deterministic output parity, but strict no-spec throughput
was unchanged (`25.848` cache versus `25.854 tok/s` graph off), so graph remains
off by default. Native event timing locates steady M=1 work at about `37.0 ms`
(`12.2-12.5 ms` host submission) and MTP3 at roughly a `42.5-45.8 ms` target
verifier plus about `9.7 ms` of draft/state graphs. Standalone MMVQ+residual
fusion hits 128 pairs/pass and saves about `0.3 ms`, but failed the 3% MTP gate.
The first block-scaled Xe2 DPAS verifier layout is closed at only `1.11x` M=4
and `1.09x` M=8 versus vector, below its `1.5x` integration gate.

The larger guarded fusion stack now reaches `50.390 tok/s` strict MTP3 versus
`48.796 tok/s` without direct GDN cache commit (`+3.27%`) across an eight-run
four-card crossover.  RMS/Q8 sharing and repaired SwiGLU/Q8 are retained behind
flags.  Two further 48-layer boundaries are closed as losses: the matched GDN
output epilogue was neutral (`25.89` versus `25.93-25.94 tok/s` M=1), while
moving sigmoid/softplus raw-gate work into GDN regressed strict MTP3 by `6.67%`
(`46.321` versus `49.632 tok/s`).  Both remain default off.  These results show
that launch-count reduction alone is insufficient when fusion enlarges the GDN
kernel or adds transcendental work to its critical path.

Direct GDN epilogue-to-Q8 output projection, direct SSM convolution cache
commit, and fused SSM convolution/QK normalization are also implemented behind
default-off flags and confirmed to match the real graph. The output-Q8 path was
only `+1.00%` in the AOT eight-run crossover (`49.978` versus `49.486 tok/s`),
below promotion threshold. Combining it with convolution cache regressed AOT
MTP3 by `1.10%` (`49.418` versus `49.969 tok/s`), and QK normalization was
neutral. Preserve these implementations and results, but do not enable them in
the production stack. JIT had overstated these gains, so AOT crossover remains
mandatory before interpreting future fusion wins.

A second Xe2 joint-N verifier briefly appeared to clear the verifier gate, but
independent review found its repeated-vector control reread weights per row,
unlike production reordered MMVQ. The corrected exact-production comparator,
including activation quantization and joint reduction, measured only `1.407x`
and `1.374x` on two critical M=4 shapes; a `1.662x` down-projection case missed
correctness. M=8 square passed at `1.925x`, but is not the MTP3 floor. Runtime
integration is therefore closed; no verifier-v2 dispatch flag was added.

Fresh strict MTP3 cycle accounting measures `2.788` emitted tokens per cycle
at `59.64%` proposal acceptance. The M=4 target verifier is `45.646 ms`
(`80.3%`), aggregate draft preparation `9.700 ms` (`17.1%`), and everything
else only `1.566 ms`, for `56.848 ms` accounted. At current acceptance, 68
tok/s requires a `41.00 ms` cycle and 100 tok/s a `27.88 ms` cycle; even
deleting all draft cost reaches only about `59.1 tok/s`. Per-op device timing
attributes `5.43 ms` of the M=4 penalty to projections, but an explicit Xe2
SIMD4 DP4A variant was only `1.004-1.012x` versus the exact compiler-optimized
production kernel. Crossing 68 now requires materially higher accepted tokens
per cycle (roughly `>=3.1`) as well as device-resident MTP staging; generic
launch fusion and another multi-column loop rewrite are closed.

Focused policy validation (`p_min 0.025-0.80` plus MTP2) produced no rescue:
best strict throughput was `50.895 tok/s`, and even a hindsight per-prompt
oracle across policies was only `52.245 tok/s` median. Existing intrinsic-MTP
adapter experiments are tied to a different HF/vLLM checkpoint, lack a safe
GGUF merge path, and their best offline acceptance gain is far below what is
required. Under the fixed single-B70 Q4_0 model and mixed strict suite, the
`>68 tok/s` objective is now blocked by the combination of Q4 weight bandwidth,
M=4 verifier time, and MTP3's four-token ceiling. Meaningful continuation
requires at least one scope change: a compatible substantially better draft,
lower-bit/reduced-weight target, or a context-owned device-unrolled MTP engine
plus verifier below `29.8 ms`; current safe optimizations cannot meet 68.

The context-owned device-resident MTP3 phase-one path is now implemented and
correct: persistent candidate/`h_nextn` staging, ordered same-device input
copies, a fixed three-step submission loop, and a poisoned-host parity/lifetime
test all pass. A SYCL top-k leading scratch entry initially collapsed
acceptance; selecting the exact production-equivalent candidate restored normal
acceptance. The strict cold suite nevertheless measured only `50.164 tok/s`
median with all gates passing, so host-boundary removal alone is closed as a
speed lane. The serialized draft graphs still execute and the `45.646 ms` M=4
target verifier remains the dominant blocker.

Native DFlash is no longer rejected based on the earlier near-zero-acceptance
result. The failure was caused by using Q8_0 for the native DFlash draft KV
cache, not by DFlash weights, Q4 quantization, or flash attention itself. The
missing controlled run—FA enabled with F16 draft KV—restored `100/106`
acceptance (`94.3%`) and `73.47 tok/s`. The earlier Q8_0 draft-KV run managed
only `7/470`, so quantized draft KV is prohibited until its numerical/backend
failure is fixed. A focused 12-case D=128/GQA4/iSWA/sparse-mask backend test
found Q8-K SYCL/CPU parity (NMSE below `6.6e-6`, no argmax mismatches over 960
rows), so current evidence favors DFlash model sensitivity to Q8 K-cache
quantization rather than a generic FA kernel error. The existing Q4_K_M draft likewise recovered to
`104/115` acceptance and `74.01 tok/s`, proving that the original Q4 result was
not ordinary quantization damage. This is the first valid local lane above the
68 tok/s milestone, but it is workload-specific rather than a production
promotion: native Q8 DFlash5 reached only `40.203 tok/s` median on the strict
12-prompt mixed suite.

Complete native DFlash timing now accounts for the mixed-workload cycle. At
`n_max=5`, steady state is about `58.7 ms` target width-6 verification,
`10.0 ms` DFlash block decode/sampling, `1.0 ms` feature injection, and
`0.3-1.2 ms` acceptance/commit: roughly `70-71 ms` total. The measured primary
blocker is therefore the generic small-M target verifier. The next decisive
work is an offline-packed Xe2 DPAS/XMX verifier plus projection fusion; generic
configuration sweeps and another global DFlash rejection are closed.

The production Xe2 width-6 verifier now covers 130 Q4_0 gate/up tensors plus 57
Q4_0 down tensors. Same-layer gate/up shares one activation quantization and
one dual-matrix ESIMD submission; down consumes canonical Q8_1 metadata, which
reduced its real shadow error to `1.01e-7`. The guarded BMG-native mirrors
preserve target-verifier semantics while materially reducing small-M cost. The
initial integrated kernel returned all zeros because the host packer
numerically converted a half-precision scale object into the raw
`ggml_fp16_t` storage type; copying the two representation bytes fixed the
scales and reduced the real one-tensor shadow error to `0.00036323` maximum.
The first corrected BMG-AOT strict suite passed at `39.249 tok/s`, versus the
matching FA-on, target-KV8, draft-KV-F16 baseline of `37.967 tok/s` (`+3.38%`), and was
approved by LocalMaxxing as `cmriq995z0210mj01fl13xmuc`. The joint gate/up plus
down BMG-AOT successor passed at `42.641 tok/s` (`+8.64%` over that row),
with JIT support at `45.484 tok/s`. Stacking the exact GDN snapshot-cache
commit fusion then raised the strict BMG-AOT record to `44.255 tok/s`, another
`3.79%`, approved as `cmrj8s2sy02a4mj01f18hanvc`. The next independent
boundary fused the Q6_K draft vocabulary head and exact top-1 into one M=6
device operation. Its strict confirmation reached **`47.819 tok/s`**, versus
an exact AOT control of `44.221 tok/s` (`+8.14%`), and LocalMaxxing approved it
as `cmrjbx8bc02g8mj01yzz2v701`. The compact path has guarded graph identity,
lowest-ID tie semantics, and an ordinary-logit rollback/redecode path after a
read failure. Do not compare these
identities with the older `40.203 tok/s` row, which used FA off and F16 target
and draft KV. An experimental 65-tensor QKV/Q expansion was rejected after its
paired strict result failed to improve throughput and introduced larger
summation drift. The next high-value measured boundary is target-side M=6
vocabulary verification: return six exact masked greedy IDs without copying
the full `6 x 248320` logits tensor to the host, then replace its vector head
with the offline-packed Xe2 verifier if the compact boundary clears its gate.

The separate promoted two-B70 vLLM result remains durable reference evidence:
graph-safe FlashAttention plus ReplaySSM transactions reached **95.384868
tok/s median**, passed exact/repeat128/baseline-parity/1K gates, and was
approved by LocalMaxxing as `cmrh35ct50092mj01h7jgydqj`. It is not the active
target configuration.

### Protected Qwen research state

The following main-repository paths contain the committed Qwen experiment
packet and must remain discoverable even though the lane is closed:

- `experiments/qwen27-dflash-sycl-b70/`;
- `notes/2026-07-12-b70-qwen27-prior-art-research.md`;
- `patches/qwen36-27b-autoround-int4-b70/llamacpp-sycl-mmvq-ncols17-q4_0-20260712.patch`;
- `plans/2026-07-12-qwen27-dflash-sycl-single-b70-plan.md`;
- `plans/2026-07-12-qwen27-tp1-max-speed-requirements-and-execution.md`.

`/home/steve/src/llama.cpp` is also protected at base `e3546c794`. It contains
the broader Qwen verifier/fusion/speculation stack plus uncommitted trace and
QKVZAB integration work across multiple files. Its closure-time tracked binary
diff SHA-256 and scoped snapshots are recorded in the
[closure note](notes/2026-07-13-qwen27-dflash-sycl-closure.md). Preserve it,
inspect Git status before building, and do not reset or clean the tree for a
new model lane. Treat the external vLLM, XPU-kernel, oneCCL, build, cache, and
result trees as mutable research state as well.

## Paused And Bookmarked Lanes

- [Laguna S 2.1 INT4 pause closeout](experiments/laguna-s-2.1-xpu-b70/notes/2026-08-08-laguna-lane-pause-closeout.md)
- [DeepSeek V4 Flash uniform-K160 closed frontier](results/deepseek-v4-flash-k160-b70/README.md)
- [Gemma 4 26B A4B Q8](results/gemma4-26b-a4b-q8-b70/HANDOFF.md)
- [MiniMax M2.7 INT4](results/minimax-m27-int4-autoround-b70/README.md)
- [Qwen3.6 35B Quark INT8](results/qwen36-35b-quark-int8-b70/README.md)
- [Qwen3.6 27B AutoRound INT4 TP2 result](results/qwen36-27b-autoround-int4-b70/HANDOFF.md)
- [All model effort packets](docs/model-effort-index.md)

These are reproducible or resumable lanes, not claims about the currently
loaded service.

## Immediate Manager Actions

1. Advance the Muse Glimmer 30B quality-first bring-up
   (`experiments/muse-glimmer-30b-b70/README.md`): finish the staged
   downloads with SHA capture, smoke Arm B (2xB70 UD-Q8_K_XL + DFlash) and
   Arm A (2xB70 BF16), bank no-spec vs DFlash ladders with exact-output
   guards, then run the Arm B vs Arm A quality gate before any production
   claim. Keep the runtime tree clean-master until baselines are banked.
2. The Qwen3.6 27B Q8_0 lane is closed and banked as of 2026-08-10; do not
   continue it without a new decision. Its retained record follows in the
   next item for reference.
3. Banked Qwen lane record: continue only under its adaptive
   strategy. The trustworthy short c1 full-512 baseline and c2 fit now exist.
   The canonical per-vector Q8 crossover is sealed `NO_EFFECT`; close that
   source lane. Bank the official isolated short and near-32K
   `UBATCH_SIZE=1024` PP/TTFT rows, but reject the setting as a broad default:
   the middle exact-output guard failed while its same-GPU `-ub 128` control
   exactly matched the old oracle. The balanced VDR screen then gave VDR2 a
   repeatable roughly 10% D100/D511 lead over VDR4 on all four cards with exact
   output and neutral PP/TTFT; its official isolated GPU-0 follow-up passed and
   banks the scoped short decode win. The official middle `-ub 128` and
   near-32K `-ub 1024` guards also pass exact, giving VDR2 an official
   `8.2%--10.0%` decode lead across all three bands with neutral PP/TTFT.
   Conventional D511 remains below `18 tok/s` throughout. The balanced VDR1
   screen then lost `13.1%--13.3%` decode on every card with neutral PP/TTFT;
   reject and close VDR1. The directly overlapped all-VDR2 four-service screen
   then retained `99.76%` of ideal four-times-isolated decode and passed every
   exactness/lifecycle gate. Four-service validation is complete. The formal
   near-32K VDR2 c2 packet then passes functional exactness and occupancy but
   fails primary/stretch performance at `10.144217 tok/s` aggregate D511,
   `5.185072 / 10.391849 tok/s` per request, and `0.498956` fairness. Keep it as
   the ordinary-c2 comparator; do not claim the eight-slot objective or rerun
   the unchanged recipe. The separate embedded-MTP identity passes its fixed
   cold realistic suite against a matched fresh control at `2.107154x` median
   D99 with exact full tokens/content on all 12 prompts, and its isolated
   LocalMaxxing record is already approved as `cmsn6b0bm0074o001uw5f9kod`.
   Preserve the source packet's legacy-oracle `FAIL` and separate supplemental
   PASS. Its recovered cross-band packet then retains D99/D511 gains of
   `2.784953x / 2.962436x` at middle and `2.899193x / 3.036799x` near 32K. Its
   four-service realistic packet retains `1.003634x / 0.998850x` aggregate
   D99/full-window rate with `0.970874 / 0.976385` normalized fairness. Both are
   nonpromotable, non-LocalMaxxing parallel evidence, not c2 or eight-slot
   claims. Full MTP c2/32K is a `~32,683 MiB` fit `NO-GO`; do not launch it or
   use CPU offload. Advance to at least 100 mixed cold requests, one hour of
   four-service turnover, clean-build/isolated reproduction where needed, and
   production routing/lifecycle generalization. Do not promote either
   concurrent screen or rerun the banked VDR2 packets. Directly measure a
   synchronized natural-stop pair as a separate relevance gate. Add a held-out
   prompt that naturally sustains 512 tokens so the serving scorecard does not
   depend only on forcing short JSON answers past EOS. Do not reuse Laguna
   flags or result directories implicitly.
4. Recheck processes, listeners, Git status, device health, memory, and model
   storage before launch. The idle statement above is a closure-time fact, not
   standing authorization.
5. Schedule a non-operational workspace consolidation before substantially
   more history accumulates: review the inherited branch name and unpublished
   commits, make durable remote/integration decisions, compact this authority,
   and repair stale indexes without deleting chronological notes or patches.
6. Keep Laguna paused and its dynamic M12-to-M1 cutoff rejected. Any Laguna
   restart requires a new decision and preregistration; the closeout records
   the correctness and stability gates that would come first.
7. Preserve the exact Laguna, DeepSeek, and Qwen source/patch/result identities.
   Do not reset protected worktrees or relabel default-off experiments as
   promoted records.
8. Continue to publish only verified new matching LocalMaxxing records after
   the applicable cold realistic gate, complete identity capture, and
   correctness pass.

The detailed state formerly accumulated in this file remains available in Git
at commit `95b4ca413` (`git show 95b4ca413:CURRENT.md`).
