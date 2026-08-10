# Qwen3.6 27B Q8 goals and long-horizon plan

## Mission

Make the pinned target-only Qwen3.6 27B Q8_0 model exceptionally fast on one
Intel Arc Pro B70 from short prompts through 32K, then scale it to four GPUs
and useful concurrency without changing the model, losing quality, or gaming
the measurement.

## Starting line

| Regime | Validated result |
|---|---:|
| Short decode, tokens 1--100 | `15.550 tok/s` |
| Long-context prompt processing | `156.043 tok/s` |
| Decode at 4K / 17K / 31.8K | `15.240 / 14.025 / 12.783 tok/s` |
| F16-KV context | `32,768` tokens |
| Two simultaneous 32K slots | fresh-sequential/simultaneous exactness PASS; aggregate D511 `10.144 tok/s`, performance target FAIL |

These are baselines, not goals.

The optional integrated publisher-MTP identity has separately cleared a scoped
fixed cold 12-prompt realistic-suite gate under
`matched_fresh_control_v1`. Full candidate/control tokens and content are exact
on all prompts. Median primary 99-interval decode improves
`17.107772 -> 36.048707 tok/s` (`2.107154x`), matched full-window throughput
improves `17.017022 -> 34.545186 tok/s` (`2.030037x`), TTFT is `1.028123x`,
and the minimum per-prompt D99 gain is `1.757122x`. This does not alter the
target-only starting line. It remains a scoped one-B70 short result: one prompt
stopped normally at 248 tokens after the required generated-token 1/100 timing
endpoints for D99.
The no-all-512 LocalMaxxing policy audit, local preflight, and authenticated
server dry-run pass. LocalMaxxing approved the final Q8_0 record as
`cmsn6b0bm0074o001uw5f9kod` at `36.04870684253697 tok/s`.
A recovered two-wave same-card crossover now retains the MTP gain at middle
and near-32K: D99 ratios are `2.784953x / 2.899193x`, and D511 ratios are
`2.962436x / 3.036799x`. A separate 12-prompt, three-wave four-service gate
measures `139.098563 tok/s` aggregate D99 (`1.003634x` of its prompt-balanced
isolated reference) and `136.884848 tok/s` full-window rate (`0.998850x`), with
normalized fairness `0.970874 / 0.976385`. Both are parallel, nonpromotable,
non-LocalMaxxing evidence rather than replacements for the isolated record.
They cover four independent one-slot services, not c2 or the eight-slot goal.
Full MTP c2/32K remains a fit `NO-GO` at a projected `~32,683 MiB` before
useful headroom; no launch or CPU-offload workaround is authorized. Production,
turnover, clean-build/isolated reproduction where needed, and sustained
durability gates remain open.

## Goals

### 1. Complete the honest scorecard

Measure prompt processing, TTFT, request-wall time, tokens 1--100, and a full
512-token decode at short, middle, and near-32K context for c1 and two genuinely
simultaneous requests. Reproduce the complete packet on a second B70.

### 2. Hit the one-B70 speed targets

Primary identity: Q8_0 weights, F16 KV, target-only text generation.

| Metric | Target | Stretch |
|---|---:|---:|
| 4K-class prompt processing | `>=300 tok/s` | `>=350 tok/s` |
| Near-32K prompt processing | `>=250 tok/s` | `>=300 tok/s` |
| 4K-class sustained decode | `>=20 tok/s` | `>=21 tok/s` |
| Near-32K sustained decode | `>=18 tok/s` | `>=20 tok/s` |
| 4K-class TTFT | `<=15 s` | `<=13 s` |
| Near-32K TTFT | `<=130 s` | `<=110 s` |

Decode targets apply to the full 512-token window. No important context band
may regress more than 5%.

### 3. Make concurrency worthwhile

- One card: two occupied F16-KV 32K slots, `>=30 tok/s` aggregate decode,
  neither request below `13 tok/s`, and `>=400 tok/s` aggregate PP.
- Stretch: `>=35 tok/s` aggregate decode, both requests at `>=16 tok/s`.
- Four cards: eight usable 32K slots, `>=120 tok/s` aggregate decode, and at
  least 90% of ideal four-times scaling under a sustained mixed workload.

### 4. Preserve quality and generality

Equivalent changes retain exact greedy output. Other arithmetic or KV formats
must pass separate semantic and long-context gates. Gains must survive unseen
prompts and neighboring shapes. Cold tests use zero cached prompt tokens. No
prompt detection, answer reuse, shortened output, hidden rows, or favorable-only
reporting. Vision and MTP remain optional separate identities.

### 5. Make the result reproducible and dependable

Reproduce material gains from a clean build, repeated same-card controls, and a
second card. Seal all identities and raw evidence. Complete at least 100 mixed
requests and one hour of turnover without quality, fairness, device, service,
memory, or cleanup failures. All four services must return cleanly to idle.

## Plan

Repeat until Goals 1--5 pass together:

1. Search upstream code, papers, non-Intel backends, local notes, failed patches,
   and identified mistakes.
2. Re-profile PP, decode, context, and concurrency; choose at most three
   performance ideas plus one falsification or robustness challenge.
3. Use all four GPUs to screen, profile, reproduce, and stress those ideas.
4. Independently audit quality, overfitting, identity drift, noise, and whether
   the proposed code actually executed.
5. Confirm wins with same-card A/B, a quiet host, broad context coverage, and a
   second card; integrate compatible wins.
6. Record every result, including failures and the condition for retrying them.

The immediate bounded frontier is turnover, durability, and production
generalization of the banked embedded-MTP identity: at least 100 mixed cold
requests, one hour of four-service turnover, clean restart/idle behavior, and a
production-facing routing/lifecycle design. Add clean-build or isolated
second-card reproduction where the parallel crossovers do not satisfy an
official isolated claim. Preserve all prior statuses: the short diagnostic
keeps its historical `ONE_BOUNDED_NMAX_PMIN_FOLLOWUP`; the first realistic
parser run remains `FAIL`; and the complete realistic measurement root remains
`FAIL` because its identity-mismatched legacy oracle matched 6/12 rows. The
separate immutable supplement, not a rewrite, classifies the same captures as
`PASS_REALISTIC_MTP_WIN` against the matched fresh control. The recovered
cross-band packet is `PASS_CROSSBAND_MTP_RETENTION_WIN`; the four-service packet
is `PASS_REALISTIC_MTP_FOUR_SERVICE_SCALE`. Both remain nonpromotable and
non-LocalMaxxing. Do not tune against the stale oracle or resubmit the approved
isolated record. The ordinary VDR2 c2 packet remains the honest functional
comparator and performance failure; integrated MTP c2/32K remains a fit
`NO-GO` unless a materially different lower-memory design is preregistered.

The four rotating GPU lanes are: reference/reproduction, prompt processing,
decode/state, and concurrency/long-context or independent challenge. Parallel
runs screen ideas; close performance claims remain isolated.

Use subagents as capacity: external research, internal history/problem solving,
and independent quality/result review. The main agent owns live GPU safety and
integration. Improve the harness and orchestration after false wins or repeated
failures; create a versioned optimization skill only from practices proven over
several cycles.

Keep live state in `CURRENT.md`, the validated frontier in the lane `README.md`,
sourced ideas in
[`suggestions/qwen36-27b-q8-gguf/`](../../suggestions/qwen36-27b-q8-gguf/), and
every attempt in dated notes, patches, and data. Promote only independently
validated work to `results/` and `repro/`.

Do not reboot automatically. Follow the passive-first recovery and xe-reload
ladder in [`docs/local-ops.md`](../../docs/local-ops.md); reboot is an explicitly
authorized last resort.

## Definition of done

The mission is complete when the one-B70 targets, c2/32K targets, eight-slot
four-GPU service, unchanged quality, broad-context generalization, sustained
reliability, and independent reproduction all pass in one reviewed result
family. Then pursue the stretch targets or restart validation for a successor
27B model as a new identity.
