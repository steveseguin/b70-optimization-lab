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
