# Qwen3.6 27B Q8_0 GGUF on one B70

Status: one-B70 target-only baseline validated through 32K; the simultaneous
four-replica 4K topology and the four-band full-512 functional wave both pass.
The official isolated short full-512 c1 baseline also passes and is reproduced
exactly. Two F16-KV 32K slots fit on one card; synchronized forced streams retain
the complete correct answer prefixes and later sequential natural-stop probes
pass. The strict c1/c2 exactness gate is blocked by replicated
workload-sensitive, slot-1-associated behavior only in the forced continuation
beyond a separately measured sequential natural-stop boundary. A four-card
compact matrix made duplicate-B exact in both slots while swapped
B+A matched the historical A/slot-1 stream prefix through generated token 128
on two cards. Two repeat waves completed the fixed A/B matrix: A+A and B+B were
exact, while both mixed directions reproduced the first slot-1 split after the
separately measured answer boundary. A synchronized natural-stop pair is still
unmeasured. The canonical MMVQ/DMMV control completed its same-card crossover
as `NO_EFFECT` and is closed. A later near-32K four-card screen found a
`4.0063x` prompt-processing lead for `-ub 1024`; its official isolated near-32K
and short full-512 PP/TTFT gates pass. The matched middle gate fails exact
output, so `-ub 1024` is not a broad default. A balanced four-card VDR
crossover then gave VDR2 a repeatable roughly 10% short D100/D511 lead over
VDR4 with exact output. Its official isolated GPU-0 follow-up passes and banks
the scoped short `-ub 1024` decode win. Official middle `-ub 128` and near-32K
`-ub 1024` guards also pass, banking an `8.2%--10.0%` VDR2 decode lead across
all three bands with neutral PP/TTFT. Conventional D511 remains below
`18 tok/s`. A balanced four-card VDR1 screen then lost `13.1%--13.3%` decode
on every card with neutral PP/TTFT, so VDR1 is closed. All-VDR2 four-service
validation then passed with `99.76%` of ideal four-times-isolated decode and
direct overlap. The sealed formal VDR2 near-32K c2 packet is now a functional
PASS but a primary/stretch performance FAIL: both full-512 streams exactly
match the fresh sequential phase with true M=2 occupancy, while aggregate D511
is only `10.144217 tok/s`, the requests measure `5.185072 / 10.391849 tok/s`,
and fairness is `0.498956`. Aggregate PP passes at `598.149228 tok/s`. This
banks an honest ordinary-c2 comparator, not the per-card or eight-slot serving
objective. The separate integrated-MTP identity now passes the fixed cold
12-prompt realistic suite against a matched fresh control: median D99 improves
`17.107772 -> 36.048707 tok/s` (`2.107154x`) with full candidate/control token
and content equality on all prompts. A recovered two-wave crossover retains
that identity's gain at middle and near-32K, with D99 ratios
`2.784953x / 2.899193x` and D511 ratios `2.962436x / 3.036799x`. A three-wave
four-service realistic gate then retained `1.003634x` aggregate D99 and
`0.998850x` full-window rate versus the prompt-balanced isolated reference,
with normalized fairness `0.970874 / 0.976385`. Both later packets are
nonpromotable, non-LocalMaxxing parallel evidence. They cover four independent
one-slot services, not c2, eight slots, or production. Full integrated-MTP
c2/32K remains a fit `NO-GO` at a projected `~32,683 MiB`; it was not launched
or hidden with CPU offload.

LocalMaxxing approved the integrated Q8_0 record as
`cmsn6b0bm0074o001uw5f9kod` at `36.04870684253697 tok/s`.

The durable goal, integrity boundary, adaptive research loop, four-GPU model,
and recurring subagent roles are in [`STRATEGY.md`](STRATEGY.md). Dated plans
are replaceable tactical proposals beneath that strategy.

## Scope

This lane has one primary identity:

- target-only `Qwen3.6-27B-Q8_0.gguf`;
- text-only, with no multimodal projector;
- one Intel Arc Pro B70 with 32 GiB VRAM;
- validated reference context of 32,768 tokens with F16 KV;
- primary target of two F16-KV 32K slots per card; the formal VDR2 packet passes
  fit, simultaneous full-512 cross-phase exactness, selected natural-stop
  retrieval, canaries, and M=2 occupancy, but fails the primary and stretch
  throughput/fairness targets;
- optional later stretch capacity of 100K to 128K with Q8 KV;
- no MTP, DFlash, n-gram, prompt-cache, or response-cache acceleration.

MTP and vision are optional, separate identities. They must not be mixed into
the target-only baseline identity or result packet. The integrated publisher
MTP artifact now has a matched-control realistic-suite PASS described below.
Its middle/near-32K retention and four independent one-slot service gates also
pass, but those are explicitly `performance_promotable=false` and
`localmaxxing_submission_ready=false`. They are not same-server c2, eight-slot,
or production evidence; the approved isolated record remains separate.

The selected deployment direction is four independent one-GPU processes. The
primary candidate is two slots per process, for up to eight cluster-wide
requests. The ordinary VDR2 c2 identity is functionally valid but too slow to
qualify that serving objective. In llama.cpp, `-c` is the total budget across
all `-np` slots, so two 32K slots require `-c 65536 -np 2`.

`UD-Q8_K_XL` is excluded from the one-card lane because its file is already
larger than one B70 before KV cache and runtime buffers. `Q8_0` is the intended
Q8 fit candidate.

## Pinned model

- Repository: `unsloth/Qwen3.6-27B-GGUF`
- Revision: `82d411acf4a06cfb8d9b073a5211bf410bfc29bf`
- File: `Qwen3.6-27B-Q8_0.gguf`
- Size: `28,595,763,424` bytes (`26.631880 GiB`)
- SHA-256: `f93f517f38e696d35a1a7df2c0e3155a64f4c4dcd662107a146ae263f7fb14ce`
- Canonical USB path: `/mnt/usb-models/models/qwen36-27b-q8-gguf/Qwen3.6-27B-Q8_0.gguf`

The machine-readable identity is in [`model-manifest.json`](model-manifest.json).
The canonical USB file independently passed the declared size and SHA-256.
Its GGUF table has 64 blocks (`0` through `63`), no block-64 tensors, and no
MTP/projector/vision-named metadata or tensors. The internal staging copy was
removed only after the USB checksum passed.

## Validated fit

The GGUF file is 26.63 GiB. With a 32,768-token F16 KV allocation, the server
fully offloaded `65/65` layers and XPU-SMI reported `28,372 MiB` loaded on one
B70. The retained buffers include a `25,972.29 MiB` model buffer, `2,048 MiB`
KV buffer, `149.62 MiB` recurrent-state buffer, and `38.50 MiB` device compute
buffer.

Qwen3.6 27B has 64 layers with conventional attention every fourth layer. With
16 conventional-attention layers, four KV heads, head dimension 256, and F16
K/V, the conventional KV allocation is 64 KiB per token, matching the retained
2 GiB allocation at 32K. The F16 lane therefore fits with roughly 4.3 GiB of
reported device-memory headroom; Q8 KV is not needed for the validated 32K
reference or the primary c2/32K target. It would be required only for the
optional 100K-or-more stretch target on one 32 GiB card.

Measured-memory modeling predicts F16 c1/64K can fit. F16 c2/32K is now a
measured fit result: `-c 65536 -np 2 --no-kv-unified` fully offloaded `65/65`
layers, used `30,570 MiB`, and left `1,814 MiB` free while allocating 4 GiB of
F16 KV. Its performance/exactness score is not promoted because the forced-tail
gate below failed. The later formal VDR2 `-ub 1024` run independently loaded
`30,839 MiB`, left `1,544 MiB` free, and passed its scoped fresh-sequential/
simultaneous functional gate, but failed the concurrency performance targets.
Q8_0 KV is predicted to permit c1/100K and probably c1/128K;
those are optional capacity rows, not immediate work. The exact estimates,
slot semantics, stop conditions, and validation order are in
[`notes/2026-08-08-context-concurrency-mtp-vision-plan.md`](notes/2026-08-08-context-concurrency-mtp-vision-plan.md).

Validated results under the correctness-qualified default
`GGML_SYCL_ENABLE_DNN=0`, `GGML_SYCL_ENABLE_OPT=1`:

- fixed cold 12-prompt, 128-token suite: `15.550257 tok/s` median tokens 1--100,
  p10 `15.548172`, mean `15.550044`; 12/12 stream/replay exactness checks
  passed, all native cache-reuse counts were zero;
- one UTF-8 byte-fallback token at generated index 89 was intentionally absent
  from SSE; the complete replay uniquely aligned it and retained valid token-1
  and token-100 timing endpoints;
- calibrated 4,369 / 17,274 / 31,846 prompt-token retrieval rows all passed
  exact JSON fields with zero cached tokens;
- 32K prefill median `156.043 tok/s`; decode-after-TTFT median `14.025 tok/s`,
  ranging from `15.240` at 4K to `12.783` at 31.8K;
- a balanced four-card same-card near-32K screen changed only
  `-ub 128 -> 1024` and raised mean approximate PP
  `155.2815 -> 622.1037 tok/s` (`4.0063x`) while reducing mean TTFT
  `205.0883 -> 51.1965 s`; all eight 31,846-token rows were cache-zero,
  retrieval-exact, fully offloaded, and output-identical, but remain
  `legacy-validation`, `performance_promotable=false`;
- the official isolated GPU-0 near-32K `-ub 1024` full-512 packet passes
  `PASS_ORACLE_EXACT`, intrinsic/exact-result/post-canary gates, full offload,
  and clean teardown. Median PP is `629.2050 tok/s`, TTFT `50.6598 s`, primary
  conventional decode `12.6475 tok/s`, and full-window conventional decode
  `12.6433 tok/s`. This promotes only near-32K PP/TTFT; decode remains below the
  `18 tok/s` target;
- the official isolated short `-ub 1024` full-512 packet also passes
  `PASS_ORACLE_EXACT` and all intrinsic/result/post-canary, full-offload, and
  cleanup gates. PP is `605.8453 tok/s`, TTFT `7.1909 s`, and full-window
  decode `15.0835 tok/s`; bank only short PP/TTFT because the `20 tok/s` decode
  target remains unmet;
- the official isolated middle `-ub 1024` guard is `FAIL_ORACLE_EXACT`. Row 1
  is exact; row 2 has LCP 92 and first differs at generated token 93
  (candidate `90`, oracle `71093`). Its JSON answer is semantically correct and
  stream/replay exact, but its timing is diagnostic only and it has no
  completion marker. A same-GPU `-ub 128` control passed and both rows exactly
  matched the old GPU-1 oracle, isolating the divergence to ubatch rather than
  card or epoch;
- the balanced two-wave, same-card VDR2/VDR4 short full-512 screen passed all
  eight exact oracle, intrinsic/result/post-canary, cache-zero, full-offload,
  runtime-binding, and cleanup gates. VDR2/VDR4 D100 ratios are
  `1.09963 / 1.09849 / 1.10087 / 1.10054` on GPUs 0--3; D511 ratios are
  `1.10025 / 1.09846 / 1.10081 / 1.09931`. PP and TTFT are neutral. These are
  concurrent `parallel-functional-screen`, `performance_promotable=false`
  diagnostics, not an official score;
- the official isolated GPU-0 VDR2 short full-512 packet is `PASS`,
  `evidence_valid=true`, and `performance_promotable=true`. Both rows are
  `PASS_ORACLE_EXACT`, cache-zero, `65/65` offloaded, post-canary exact, and
  clean. Against the official isolated VDR4 short baseline, D100 is
  `16.5872 / 15.0813 = 1.09985x`, conventional D511 is
  `16.5889 / 15.0835 = 1.09980x`, and legacy D512 is
  `16.6211 / 15.1129 = 1.09980x`; PP and TTFT remain neutral. This banks the
  scoped official short decode win, but D511 remains below the immediate
  `18 tok/s` target;
- the official isolated GPU-0 VDR2 middle `-ub 128` packet is also exact and
  promotable. Against the matched VDR4 baseline, D100 is
  `15.1382 / 13.8697 = 1.09146x` and D511 is
  `15.0773 / 13.8194 = 1.09102x`; PP and TTFT ratios are neutral at
  `0.99993x` and `1.00010x`;
- the official isolated GPU-0 VDR2 near-32K `-ub 1024` packet is exact and
  promotable. Against the official VDR4 baseline, D100 is
  `13.6895 / 12.6475 = 1.08238x` and D511 is
  `13.6862 / 12.6433 = 1.08249x`; PP and TTFT ratios are neutral at
  `0.99934x` and `1.00062x`. All three official VDR2 bands retain cache-zero,
  `65/65` offload, exact canaries, and clean teardown, but remain below the
  immediate `18 tok/s` D511 target;
- the balanced two-wave, same-card VDR1/VDR2 short screen passed all eight
  exact-output, canary, cache-zero, full-offload, runtime-binding, artifact,
  and cleanup gates. Median same-card VDR1/VDR2 ratios were `0.868858` D100
  (`-13.1142%`), `0.866553` D511 (`-13.3447%`), and `0.866555` legacy D512;
  zero of four cards favored VDR1. PP `1.000334x` and TTFT `0.999569x` were
  neutral. This is `parallel-functional-screen`,
  `performance_promotable=false` evidence: reject and close VDR1, retain VDR2;
- the all-VDR2 four-service short screen directly overlapped all four listeners
  and task-0 decode. Every lane passed exactness, canary, cache-zero,
  full-offload, runtime-binding, artifact, and cleanup gates. Aggregate D100
  was `66.193839 tok/s` (`99.7667%` of ideal four-times isolated), D511
  `66.197483 tok/s` (`99.7617%`), legacy D512 `66.326092 tok/s` (`99.7617%`),
  and PP `2414.184 tok/s` (`99.5843%`). This establishes essentially linear
  scaling across four independent services, but remains a nonpromotable screen
  and makes no same-server concurrency claim;
- the formal GPU-0 VDR2 near-32K c2 packet is sealed, evidence-valid, and
  `PASS_ORACLE_EXACT` against its fresh sequential phase. Both 512-token rows,
  selected natural-stop retrieval, local/external canaries, cache-zero,
  `65/65` offload, M=2 occupancy, and cleanup pass. Aggregate PP is
  `598.149228 tok/s`, but aggregate D511 is `10.144217 tok/s`; per-request D511
  is `5.185072 / 10.391849 tok/s` and fairness is `0.498956`. This fails the
  primary `30` aggregate / `13` each and stretch `35` aggregate / `16` each
  targets. Bank functional evidence and the negative performance measurement;
  do not claim the c2 serving objective;
- the separate integrated publisher-MTP short diagnostic now has a valid
  prospective confirmation. MTP3 measures primary 99-interval decode
  `44.696620` versus `16.586788 tok/s` control (`2.694712x`) and matched
  full-window D511 `48.037351` versus `16.590928 tok/s` (`2.895399x`). Both
  two-prompt full-512 rows, replays, post-canary, cache-zero, counter binding,
  `66/66` offload, fit, and cleanup pass. Acceptance is `0.934465`. This is
  `official-isolated-diagnostic`, `performance_promotable=false` evidence, not
  a fixed realistic-suite, cross-band, second-card, c2, production, or
  LocalMaxxing result;
- the follow-up fixed cold realistic-suite capture has a valid offline
  matched-control classification of `PASS_REALISTIC_MTP_WIN`. The original
  complete run remains immutably `FAIL` solely because its identity-mismatched
  legacy 4K/128 oracle matched 6/12 current 32K/512 control prefixes. Under
  `matched_fresh_control_v1`, candidate and control full tokens and content are
  exact on all 12 prompts. Median D99 is `36.048707` versus
  `17.107772 tok/s` (`2.107154x`), matched full-window throughput is
  `34.545186` versus `17.017022 tok/s` (`2.030037x`), native throughput is
  `34.612807` versus `17.050342 tok/s` (`2.030036x`), TTFT is `1.028123x`,
  and every prompt gains at least `1.757122x` on D99. MTP counters bind 3,709
  accepted / 6,448 draft tokens over 2,152 verifications. Eleven prompts
  reached 512 tokens; `customer-email` stopped normally at 248, after the
  required generated-token 1/100 timing endpoints for D99. LocalMaxxing policy
  does not require padding a natural EOS row to the 512-token request cap. The
  exact Q8_0 queue passes local preflight and authenticated no-write server
  dry-run. LocalMaxxing approved the final record as
  `cmsn6b0bm0074o001uw5f9kod` at `36.04870684253697 tok/s`. This clears the
  scoped isolated realistic-suite gate only; later parallel packets do not
  change its claim class;
- the recovered two-wave, same-card middle/near-32K MTP crossover classifies
  `PASS_CROSSBAND_MTP_RETENTION_WIN`. All eight arms pass two full-512 scored
  rows plus replay, cache-zero, full-offload, counter, and cleanup gates;
  same-card control/MTP tokens and content are exact. Middle retains
  `-ub 128` and measures D99/D511 ratios `2.784953x / 2.962436x`; near-32K
  retains `-ub 1024` and measures `2.899193x / 3.036799x`. First scored
  four-way overlap is `65.930913 / 65.114247 s`. The 260-entry root manifest
  `40e8892a...`, comparison `53d739a2...`, and completion `1e791ec0...` verify,
  as do all eight child manifests. This remains a nonpromotable,
  non-LocalMaxxing `parallel-functional-screen`;
- the fixed realistic suite also passes a three-wave, four-service scaling
  gate with one independent `-c 32768 -np 1` service per B70. All 12 rows are
  exact under the sealed retained-position policy and cache-zero; each service
  is `66/66` offloaded at `29,911 MiB` and returns `43 -> 43 MiB`. Four-way
  overlaps are `8.747546 / 15.359000 / 15.232755 s`. Aggregate D99 is
  `139.098563 tok/s` (`1.003634x` of the prompt-balanced isolated reference),
  full-window rate is `136.884848 tok/s` (`0.998850x`), and normalized fairness
  is `0.970874 / 0.976385`. Manifest `e9329ff9...`, gate `c91df0d9...`, and
  completion `bc2aa4e2...` verify. The packet is nonpromotable and non-
  LocalMaxxing; it is not c2 or an eight-slot claim;
- full integrated-MTP c2/32K remains a fit `NO-GO`. Measured one-slot MTP3
  residency is `29,911 MiB`; the second target/draft KV and recurrent-state
  allocations project about `32,683 MiB` before useful headroom. Do not launch
  the unchanged shape or use CPU offload to relabel the miss;
- both correctness-qualified validation runs exited cleanly, returned GPU 0 from 28,372 or
  26,573 MiB to 43 MiB, and retained empty device/server fault scans.

The first official isolated short full-512 c1 packet measured `156.917 tok/s`
prompt processing, `27.699 s` TTFT, `15.0716 tok/s` over tokens 1--100, and
`15.0737 tok/s` over the 511 intervals from token 1 through token 512. A fresh
same-card repeat was token/content exact and measured `156.872`, `27.708`,
`15.0709`, and `15.0703` respectively. Both packets are authoritative,
detached-seal PASS evidence; neither meets the Goal-1 speed targets yet.

The formal c2 short lane proved true M=2 occupancy. Both synchronized forced
streams contained the complete correct JSON answer prefixes, and later
sequential natural-stop probes passed on both slots; a synchronized natural-stop
pair has not yet been measured. The forced 512-token comparison intentionally
suppresses EOS. In forward order slot 1 diverged from M=1 at token 71, after the
answer boundary later measured at token 70; after prompt reversal slot 1
diverged at token 96, after the other prompt's measured boundary at token 95,
while slot 0 became 512/512 exact. A later four-GPU 128-token matrix matched
the historical A/slot-1 stream prefix through token 128 on two cards, including
the 33-token divergent suffix, while duplicate-B was 128/128 c1-exact
in both slots on two other cards. This rules out a simple unconditional slot-1
failure and establishes replicated workload-sensitive, slot-1-associated
forced-tail behavior, not prompt B or SSE loss. Duplicate-A was exact in both
slots on two cards and repeated exactly;
forward A0/B1 reproduced B's first split at token 71 on both cards and both
waves. Its later tail was stable on each fixed lane but differed across GPU 1
and GPU 3 after token 71, with card and launch-order effects still confounded.
The default-off combined canonical per-vector Q8 control now passes its
isolated real-shape GPU gate with selector-off/on bitwise equality and verified
dispatch activation. A fresh four-card no-sleep Phase-1 cohort now also passes:
both selector replicas are full-512 exact to the official c1 packet, selector
off emits no canonical route marker, and selector on retains the exact flat
first-hit before release with no recurrent hit or violation. Its sealed
selector-matched oracles fed the sealed two-wave selector-off/on same-card
crossover. It classified `NO_EFFECT`: every ON and OFF lane reproduced B71 or
A96 with no pre-boundary regression, despite exact ON-route activation. GPU 0's
later forward tail differed across selector states, so complete ON/OFF output
equality is not claimed. The forced-512 crossover is diagnostic-only and makes
no natural-stop or performance claim; canonical single-column MMVQ plus
recurrent-output DMMV is closed as a source lane. See
[`notes/2026-08-10-canonical-q8-c2-crossover-no-effect.md`](notes/2026-08-10-canonical-q8-c2-crossover-no-effect.md).

Bank the official short and near-32K PP/TTFT wins, reject the middle result, and
do not integrate `UBATCH_SIZE=1024` as a broad default. The VDR2 diagnostic
screen passes on all four cards and its official isolated GPU-0 short follow-up
banks the scoped roughly 10% decode win. The official middle `-ub 128` and
near-32K `-ub 1024` guards also pass, banking VDR2 across all three bands with
an `8.2%--10.0%` decode lead and neutral PP/TTFT. The balanced VDR1 screen is
an exact `13.1%--13.3%` decode loss and closes that lane. The directly
overlapped all-VDR2 four-service screen retains `99.76%` of ideal decode and
completes independent-service validation. The formal near-32K VDR2 c2 packet
then passes functional exactness and occupancy but fails primary/stretch
performance at `10.144217 tok/s` aggregate D511 with `0.498956` fairness.
Retain it as the sealed comparator for a materially different concurrency
candidate; do not rerun the unchanged recipe. See
[`notes/2026-08-10-vdr2-vdr4-short-crossover.md`](notes/2026-08-10-vdr2-vdr4-short-crossover.md).

The integrated publisher-MTP lane then produced a confirmed, bounded short
lead. The pinned model is revision
`5cb35eb3dcbf52dbce5f87dbc64df6aaffadcace`, size `29,047,084,160`, SHA-256
`9408dcb356cc061a05c139e5647cbde0698ff980c6a69f7fc214e9989f86cfa8`.
Two pre-measurement packets are intentionally retained: manifest `99a07a5f...`
stopped on invalid `-fitp`, and manifest `42239f5f...` stopped on a stale
next-token-layer log matcher. The first valid packet (manifest `35820eb...`,
completion `f52d9093...`, comparison `bc484bc4...`) was exact and showed the
same large gain, but keeps its historical `ONE_BOUNDED_NMAX_PMIN_FOLLOWUP`
label because the original classifier compared unlike timing horizons. Commit
`d878aecb9` prospectively co-gated matched all-512 D511/native timing while
retaining the policy 99-interval metric. The unchanged confirmation (manifest
`2d044a5c...`, comparison `0fde58da...`, completion `56755607...`) then passed
as `ADVANCE_FULL_VALIDATION`. Its MTP counters are 1,597 accepted / 1,709
drafted over 572 verifications, or `2.791958` accepted and `3.791958`
effective target-verified tokens per verification. Control/MTP loaded
`28,642 / 29,911 MiB`; both arms returned `43 -> 43 MiB` without a survivor or
forced kill. The exact identities, hashes, measurements, and preserved false
starts are in
[`notes/2026-08-10-embedded-mtp-short-diagnostic-advance.md`](notes/2026-08-10-embedded-mtp-short-diagnostic-advance.md).

Do not tune from the historical bounded label or rewrite either realistic run's
status. The first realistic attempt stopped safely on a partial verbose
`id_slot` sentinel mismatch and was fixed by commit `612f6660d`. The complete
measurement packet remains `FAIL` with manifest `8b0e18c...`; the separate
supplemental packet preserves it and seals manifest `d44cef31...` as
`PASS_REALISTIC_MTP_WIN`. The old-oracle mismatch is not evidence of
context-caused quality loss: the identities differ, prior evidence favors
ubatch sensitivity, and the cause remains unresolved. The subsequent
cross-band retention and four-service gates now pass, but remain nonpromotable
and non-LocalMaxxing. Preserve the two failed crossover roots as negative
evidence: the first contains the GPU-2 reset/orphan and stale seal; the second
contains the masked-ordinal telemetry failure plus real BDF-43 fault
contamination. The successful passive-first recovery used an all-four B70
unbind and `xe` module reload without FLR or reboot, then passed mapping, idle,
peer, per-card compute, four-rank XCCL, generation, journal, and cleanup gates.
Advance to turnover, durability, isolated reproduction where needed, and
production lifecycle/routing work. See
[`notes/2026-08-10-embedded-mtp-realistic-suite-matched-control-pass.md`](notes/2026-08-10-embedded-mtp-realistic-suite-matched-control-pass.md).
The complete failed-attempt, recovery, crossover, and scaling chronology is in
[`notes/2026-08-10-embedded-mtp-crossband-four-service-recovery-closeout.md`](notes/2026-08-10-embedded-mtp-crossband-four-service-recovery-closeout.md).

The validation sequence remains useful for future runtimes:

1. 4K target-only compatibility smoke with a 4K F16-KV allocation and full GPU
   offload.
2. Fixed cold realistic suite through llama.cpp's native streaming endpoint to
   establish the Q8_0 exact-token regression oracle and conventional 100-event/
   99-interval baseline speed.
3. A separately labeled 32K F16-KV allocation and calibrated long-context
   retrieval gate.
4. A full-512 c1 packet, then simultaneous F16-KV c2/32K fit, exactness,
   retrieval, turnover, aggregate-rate, latency, and fairness gates.
5. Q8_0 KV only for an optional larger-context target. Treat Q8 KV as a
   separate quality identity and compare it against the F16-KV corpus.
6. Optional MTP only if ordinary c2 does not meet the serving objective. The
   integrated publisher artifact has passed its scoped one-B70 short realistic
   suite against a matched fresh control, plus nonpromotable middle/near-32K
   retention and four independent one-slot service gates. Full MTP c2/32K is a
   fit `NO-GO`. Run turnover/durability and production generalization next,
   with isolated reproduction where needed. Do not cross-pair converters
   without tensor and metadata validation, and do not graft the third-party
   head-only extraction into the baseline.
7. Optional vision only after the text optimization and context envelope are
   settled. Use the same-repository, same-revision F16 projector pinned in
   [`optional-artifacts-manifest.json`](optional-artifacts-manifest.json).

The full-512/c2 measurement foundation is now implemented, offline-tested, and
validated by a sealed four-card functional wave. The formal near-32K VDR2 c2
packet is a valid functional pass and performance-target failure; it does not
qualify the serving goal. The metric definitions, paired prompt counts,
integrity gates, and four-card first wave are preregistered in
[`notes/2026-08-09-goal1-measurement-foundation.md`](notes/2026-08-09-goal1-measurement-foundation.md).
For new full-512 and c2 packets, only a verified detached
`completion-status.json` is an authoritative PASS; a `run-status.txt` file by
itself is not completion evidence.

If full GPU offload fails even with Q8 KV and a smaller microbatch, do not hide that result with CPU layer offload. The product goal is one fast, independent B70 lane, so partial offload is a separate capacity diagnostic rather than a successful configuration.

## Historical evidence

A historically recorded local May 2026 `ggml-org` Q8_0 artifact of the same model family fit one B70 and measured `15.275 tok/s` at p512/n128 with F16 KV. That historical file differed by 928 bytes from today's pinned Unsloth artifact, its SHA/revision and full command were not retained, and the raw logs and old source tree were later removed for disk pressure. It is a trend anchor, not a strict reproduction or a 32K proof.

The preserved summary is [`results/qwen36-b70-followup-2026-05-04-q8-allreduce-profiling.md`](../../results/qwen36-b70-followup-2026-05-04-q8-allreduce-profiling.md). The deletion is recorded in [`notes/2026-05-07-model-retention-cleanup.md`](../../notes/2026-05-07-model-retention-cleanup.md).

The later Q4_0/DFlash lane contains relevant benchmark and speculative-decoding lessons but not a Q8 target kernel result. In particular, the locally named Q8 fusion flags optimized Q8_1 activations feeding Q4 weights and must not be carried into this baseline. See [`notes/2026-07-13-qwen27-dflash-sycl-closure.md`](../../notes/2026-07-13-qwen27-dflash-sycl-closure.md).

## Runtime identity

Initial compatibility smoke uses the archived community-validation build:

- llama.cpp commit `15586e2d7165570fb3aa7c26e0d442e289ef69de`;
- runtime version `10298 (15586e2d7)`;
- IntelLLVM / oneAPI 2026.0.0;
- restored path `/dev/shm/llama.cpp-pr19-15586/build-sycl/bin/llama-server`;
- archive `/mnt/usb-models/models/runtime-builds/llama.cpp-15586e2d7-oneapi2026.0-sycl-worktree.tar.zst`;
- archive SHA-256 `0ab088aac2cb2c12331fd18c4dbda4a30228a25e06bc2a8a95f770693da8d4d8`.

This build is a reproducible compatibility baseline, not automatically the optimization winner. Before source changes, create a dedicated clean worktree and preserve its commit, build flags, binary hash, and patch. Do not modify `/home/steve/src/llama.cpp`; that tree contains protected Q4/DFlash experiments.

The archived build's DNN selector is not correctness-safe for this Q8 target.
With DNN enabled, the fast path stayed near `15.55 tok/s` but four of twelve
temperature-zero replay rows diverged; an immediate A/A repeat also diverged.
Disabling the broader optimization stack restored exactness but fell to
`5.033 tok/s`. Disabling only DNN restored exactness at `15.551 tok/s` in the
focused A/A test and `15.550 tok/s` across the full suite. The DNN-off 32K
confirmation paid about 2.8% in median prefill versus the DNN-on diagnostic,
with no meaningful decode change. Keep DNN-off as the lane default.

## Four-GPU use

Four one-card processes will be used for independent functional or optimization
lanes, each with its own source worktree, build, port, GPU ordinal, and run
directory. Parallel runs are screening or aggregate-service evidence. Official
single-card throughput comparisons remain isolated, same-card bracketed, and
confirmed on a second card. The working protocol is in
[`notes/2026-08-08-four-gpu-optimization-and-c2-plan.md`](notes/2026-08-08-four-gpu-optimization-and-c2-plan.md).

The simultaneous four-replica functional smoke passed: all four services were
resident at 4K with `26,573 MiB` on each card, fully offloaded, and generated
the same sealed 128-token output concurrently before clean teardown to 43 MiB.
This proves the process topology, not a four-card performance score. See
[`notes/2026-08-08-four-replica-functional-smoke.md`](notes/2026-08-08-four-replica-functional-smoke.md).

The later Goal-1 wave simultaneously completed 18 full-512 rows spanning 4K,
17K, near-32K, and the 12-prompt realistic suite. Every child and outer
checksum chain passed, all post-workload canaries were exact, and every card
returned cleanly to 43 MiB. Its rates are explicitly diagnostic because four
cards were active. See
[`notes/2026-08-09-four-gpu-goal1-functional-screen.md`](notes/2026-08-09-four-gpu-goal1-functional-screen.md).

## Entry points

- Target-only server: [`scripts/serve-target-only.sh`](scripts/serve-target-only.sh)
- Validation runner: [`scripts/run-validation.sh`](scripts/run-validation.sh)
- Four-replica functional smoke: [`scripts/run-four-replica-smoke.sh`](scripts/run-four-replica-smoke.sh)
- Exact emitted-token capture/comparison and 99-interval primary metric: [`scripts/capture-exact-tokens.py`](scripts/capture-exact-tokens.py)
- Synchronized exact c2 capture and occupancy proof: [`scripts/capture-simultaneous-c2.py`](scripts/capture-simultaneous-c2.py)
- Fresh-server c2 validation lifecycle: [`scripts/run-c2-validation.sh`](scripts/run-c2-validation.sh)
- Four-card Goal-1 functional wave: [`scripts/run-goal1-four-gpu-wave.sh`](scripts/run-goal1-four-gpu-wave.sh)
- Paired 4K/17K/near-32K c2 suite: [`c2-long-context-suite-v1.json`](c2-long-context-suite-v1.json)
- Pinned paired-suite calibration: [`data/c2-suite-calibration-v1.json`](data/c2-suite-calibration-v1.json)
- Model identity: [`model-manifest.json`](model-manifest.json)
- Runtime identity: [`runtime-manifest.json`](runtime-manifest.json)
- Optional future artifact identities: [`optional-artifacts-manifest.json`](optional-artifacts-manifest.json)
- Short realistic suite: [`repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json`](../../repro/qwen36-27b-autoround-int4-b70/realistic-suite-v1.json)
- Calibrated 4K/17K/31K retrieval ladder: [`long-context-suite-v1.json`](long-context-suite-v1.json)
- Long-context harness: [`scripts/bench-openai-long-context-suite.py`](../../scripts/bench-openai-long-context-suite.py)
- Result summary: [`data/baseline-summary-20260808.json`](data/baseline-summary-20260808.json)
- Chronological result note: [`notes/2026-08-08-one-b70-baseline-and-dnn-exactness.md`](notes/2026-08-08-one-b70-baseline-and-dnn-exactness.md)
- Four-replica result: [`notes/2026-08-08-four-replica-functional-smoke.md`](notes/2026-08-08-four-replica-functional-smoke.md)
- Four-band full-512 functional result: [`notes/2026-08-09-four-gpu-goal1-functional-screen.md`](notes/2026-08-09-four-gpu-goal1-functional-screen.md)
- Four-band structured summary: [`data/goal1-four-gpu-functional-summary-20260809.json`](data/goal1-four-gpu-functional-summary-20260809.json)
- Current c1/c2 scorecard: [`data/goal1-c1-c2-scorecard-20260809.json`](data/goal1-c1-c2-scorecard-20260809.json)
- Context/concurrency and optional-feature plan: [`notes/2026-08-08-context-concurrency-mtp-vision-plan.md`](notes/2026-08-08-context-concurrency-mtp-vision-plan.md)
- Four-GPU optimization and c2 execution plan: [`notes/2026-08-08-four-gpu-optimization-and-c2-plan.md`](notes/2026-08-08-four-gpu-optimization-and-c2-plan.md)
- Goal-1 measurement preregistration: [`notes/2026-08-09-goal1-measurement-foundation.md`](notes/2026-08-09-goal1-measurement-foundation.md)
- First c2 attestation failure and fix: [`notes/2026-08-09-c2-nonunified-kv-attestation-fix.md`](notes/2026-08-09-c2-nonunified-kv-attestation-fix.md)
- Concurrent token-512 failure diagnostic: [`notes/2026-08-09-c2-concurrent-endpoint-diagnostic.md`](notes/2026-08-09-c2-concurrent-endpoint-diagnostic.md)
- Canonical Q8 component GPU result: [`notes/2026-08-09-canonical-q8-component-gpu-pass.md`](notes/2026-08-09-canonical-q8-component-gpu-pass.md)
- Canonical Q8 four-card c1 oracle pass: [`notes/2026-08-09-canonical-q8-c1-phase1-pass.md`](notes/2026-08-09-canonical-q8-c1-phase1-pass.md)
- Canonical Q8 c2 crossover no-effect result: [`notes/2026-08-10-canonical-q8-c2-crossover-no-effect.md`](notes/2026-08-10-canonical-q8-c2-crossover-no-effect.md)
- Near-32K ubatch crossover screen: [`notes/2026-08-10-near32k-ubatch-screen.md`](notes/2026-08-10-near32k-ubatch-screen.md)
- VDR2/VDR4 short full-512 crossover: [`notes/2026-08-10-vdr2-vdr4-short-crossover.md`](notes/2026-08-10-vdr2-vdr4-short-crossover.md)
- Formal VDR2 near-32K c2 result: [`notes/2026-08-10-formal-c2-near32k-vdr2-functional-pass-performance-fail.md`](notes/2026-08-10-formal-c2-near32k-vdr2-functional-pass-performance-fail.md)
- Embedded publisher-MTP diagnostic runner: [`scripts/run-embedded-mtp-vdr2-diagnostic.sh`](scripts/run-embedded-mtp-vdr2-diagnostic.sh)
- Embedded publisher-MTP diagnostic closeout: [`notes/2026-08-10-embedded-mtp-short-diagnostic-advance.md`](notes/2026-08-10-embedded-mtp-short-diagnostic-advance.md)
- Embedded publisher-MTP realistic runner: [`scripts/run-embedded-mtp-vdr2-realistic.sh`](scripts/run-embedded-mtp-vdr2-realistic.sh)
- Embedded publisher-MTP realistic closeout: [`notes/2026-08-10-embedded-mtp-realistic-suite-matched-control-pass.md`](notes/2026-08-10-embedded-mtp-realistic-suite-matched-control-pass.md)
- Embedded publisher-MTP cross-band runner: [`scripts/run-embedded-mtp-vdr2-crossband-crossover.sh`](scripts/run-embedded-mtp-vdr2-crossband-crossover.sh)
- Embedded publisher-MTP four-service runner: [`scripts/run-embedded-mtp-four-service-realistic.sh`](scripts/run-embedded-mtp-four-service-realistic.sh)
- Embedded publisher-MTP recovery/cross-band/four-service closeout: [`notes/2026-08-10-embedded-mtp-crossband-four-service-recovery-closeout.md`](notes/2026-08-10-embedded-mtp-crossband-four-service-recovery-closeout.md)
- Embedded publisher-MTP LocalMaxxing packet builder: [`scripts/build-embedded-mtp-localmaxxing-packet.py`](scripts/build-embedded-mtp-localmaxxing-packet.py)
- Embedded publisher-MTP approved submission queue: [`localmaxxing/qwen36-27b-mtp-q8_0-vdr2-embedded-mtp3-realistic-36tok-20260810.queue.json`](localmaxxing/qwen36-27b-mtp-q8_0-vdr2-embedded-mtp3-realistic-36tok-20260810.queue.json)
- Embedded publisher-MTP HTTP-201 submission receipt: [`localmaxxing/qwen36-27b-mtp-q8_0-vdr2-embedded-mtp3-realistic-36tok-20260810.submission-receipt.json`](localmaxxing/qwen36-27b-mtp-q8_0-vdr2-embedded-mtp3-realistic-36tok-20260810.submission-receipt.json)
- Durable adaptive optimization strategy: [`STRATEGY.md`](STRATEGY.md)
- Sourced living idea queue: [`../../suggestions/qwen36-27b-q8-gguf/README.md`](../../suggestions/qwen36-27b-q8-gguf/README.md)

The exact-token file is a self-regression oracle for later runtime/kernel/MTP
changes; it is not an external proof that Q8_0 reproduces BF16. Do not publish
or submit a rate until the model hash, runtime identity, fixed cold suite,
native `cache_n=0`, 100 token events/99 intervals, full-offload evidence, clean
teardown, and relevant context/quality gate are retained together.

The 128-token fixed suite is the bring-up and regression gate. A promotable
performance packet additionally needs TTFT, request-wall throughput, and the
workspace-standard full 512-token decode measurement. A long-context run with
`CASE_ID` selects a diagnostic subset; only the default run with all three
declared cases is the complete 4K/17K/31K retrieval gate.
