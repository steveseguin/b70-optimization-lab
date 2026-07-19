# DSpark no-training speculation screen

Date: **2026-07-19**

Status: **DEV screen complete; incumbent M=7 retained; no held-out candidate**

## Numbers first

- Exact-record public-continuity sanity: **79.305186 tok/s** median tokens
  1-100 after TTFT (p10 68.834994, 12/12 cache-zero).
- Best same-patched-binary DEV result: **79.801765 tok/s** at the incumbent
  static DSpark width **M=7**, **3.507042 emitted tokens/cycle**, effective
  **43.946926 ms/cycle**.
- Qualified public record for comparison: **80.820052 tok/s**. The DEV winner
  is **1.018287 tok/s (1.26%) below** the record, so it is **not a candidate**
  and requires no held-out reveal.
- All completed policies passed the six ordered exact canaries with
  `cached_tokens=0`. No LocalMaxxing action was taken.

The DEV workload is the 12 public continuity prompts plus the ten explicitly
DEV prompts in `data/dspark7-draft-acceptance-dev-suite-v1.json`. Twenty rows
reached the 100-token timing window; both low-locality rows ended earlier and
remain in the acceptance/cycle totals but not the median throughput.

## Width sweep

`Cycle ms` below is the effective cycle time derived from measured median net
rate and measured emitted tokens/cycle. Target verification is always exact and
uses M+1 rows.

| Requested M | Actual mechanism | Emitted/cycle | Cycle ms | Net tok/s | Accepted/drafted |
| ---: | --- | ---: | ---: | ---: | ---: |
| 4 | M=5 DSpark backbone, verifier prefix capped to 4, synchronous handoff | 3.189977 | 136.468140 | 23.375248 | 1,879/3,432 (54.75%) |
| 5 | native static M=5 | 3.265476 | 42.789628 | 76.314666 | 1,903/4,200 (45.31%) |
| 6 | native static M=6 | 3.465234 | 47.597192 | 72.803326 | 1,950/4,746 (41.09%) |
| **7** | **record static M=7/M=8 verify** | **3.507042** | **43.946926** | **79.801765** | **1,958/5,467 (35.81%)** |
| 8 | native M=8/M=9 verify; generic router fallback | 3.470812 | 47.007700 | 73.834972 | 1,947/6,304 (30.89%) |

M=4 is not a native pack geometry: the checkpoint declares DSpark block size
five and the runtime rejects a smaller backbone because it produces invalid
drafts. The table therefore reports the honest lower-bound proxy: pay the full
M=5 backbone/Markov work, schedule only four tokens, and disable asynchronous
scheduling so the per-request length reaches the scheduler. It is not directly
competitive with the static-width rows.

M=8 initially failed closed with `VLLM_XPU_V4_ROUTER_NORM_MAX_M=8`: the native
router contract supports the record's target M=8 verifier but not the draft's
256-expert M=8 call. Setting the flag to 7 is invalid by configuration. The
measured row uses the allowed value 0, which sends both new widths through the
generic exact router. Both failed attempts are preserved beside the measured
run.

### M=7 per-position acceptance on DEV

| Draft position | Accepted | Marginal | Conditional |
| ---: | ---: | ---: | ---: |
| 1 | 622 | 79.64% | 79.64% |
| 2 | 462 | 59.15% | 74.28% |
| 3 | 318 | 40.72% | 68.83% |
| 4 | 226 | 28.94% | 71.07% |
| 5 | 160 | 20.49% | 70.80% |
| 6 | 107 | 13.70% | 66.88% |
| 7 | 63 | 8.07% | 58.88% |

## Native no-training mechanism survey

| Mechanism | Feasibility and result |
| --- | --- |
| Official DSpark/DFlash-style predictor | **Already the incumbent.** The local pack is the official three-trained-stage parallel DSpark block plus sequential Markov correction, using target features from layers 40-42. Static M=7 gives the best DEV result above: 79.801765 tok/s and the listed per-position acceptance. There is no second/deeper compatible DSpark checkpoint locally. |
| Checkpoint-attached one-layer target MTP | Feasible only as MTP1 and historically qualified at 63.851301 tok/s; it proposes one position and is not a deeper alternative to DSpark7. Reusing the single layer is closed, not a new learned deeper head. |
| Repeated attached MTP layer (MTP2/MTP3) | **Closed; do not repeat.** The MTP2 realistic run had first-position acceptance about 73-81%, second-position only 0.5-2.2%, then hung without a valid throughput result. A later repeated-to-M4 screen had second-draft 5.0-22.6%, third-draft 0.0-3.2%, and only 46.247281 tok/s on eight eligible cold rows versus MTP1 63.851301. |
| DSpark trained confidence head | **Feasible, measured below.** The pack contains the trained FP32 `confidence_head.proj.weight`; the record loader previously discarded it. The guarded patch loads it and applies the reference cumulative survival rule. |
| Tree/beam drafting | **Not available as a no-training/native switch.** The DSpark verifier path is flat; there is no tree layout/verification implementation for this K160 path. Adding beam/tree expansion would be new runtime and policy work, with multiple Markov/LM-head proposals per level, not a native deeper checkpoint mechanism. |
| EAGLE/DEAGLE | Requires learned draft weights/training; outside this no-training screen. |

The repeated-MTP evidence is preserved in
`2026-07-15-mtp2-reuse-deadlock-closure.md` and
`2026-07-18-sequential-mwidth-verifier-and-predictor-pivot.md`.

## Confidence-gated prefix sweep

The checkpoint confidence is a conditional acceptance estimate for each
position. The policy uses the cumulative product and schedules the longest
prefix whose survival probability meets the threshold. The implementation is
default-off and exact-target-verified.

Important limitation: the current official DSpark implementation computes the
full parallel backbone and all seven sequential Markov proposals before this
decision. It therefore trims target-verifier work but does **not** avoid draft
backbone/tail cost. Variable-length handoff also requires
`--no-async-scheduling` in this runtime. This is verifier-prefix trimming, not
a claimed zero-cost early draft stop.

| Threshold | Mean scheduled M | Emitted/cycle | Cycle ms | Net tok/s | Accepted/drafted |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0.000 (plumbing control) | 7.000 | 3.437892 | 43.248808 | **79.491026** | 1,943/5,579 (34.83%) |
| 0.010 | 5.965 | 3.510911 | 45.415619 | 77.306254 | 1,956/4,647 (42.09%) |
| 0.025 | 5.483 | 3.526316 | 45.570380 | 77.381751 | 1,968/4,271 (46.08%) |
| 0.050 | 4.953 | 3.408240 | 46.163685 | 73.829455 | 1,929/3,967 (48.63%) |
| 0.100 | 4.337 | 3.351648 | 46.963656 | 71.366854 | 1,926/3,552 (54.22%) |
| 0.200 | 3.644 | 3.321602 | 45.997561 | 72.212566 | 1,913/3,003 (63.70%) |
| 0.300 | n/a | n/a | n/a | n/a | guarded startup hung; stopped and preserved |

No nonzero threshold beats either the confidence-plumbing control or the
static M=7 incumbent. The confidence ranking is directionally useful—drafted
token precision rises monotonically through 0.20—but the saved verifier rows
do not pay for the scheduling/shape cost on this runtime.

## Selected DEV policy and recommendation

Retain the **unchanged static M=7 DSpark / exact M=8 target verifier record
recipe**. It is the best no-training operating point on DEV at 79.801765 tok/s,
but it does **not** beat 80.820052 and is therefore **not a held-out candidate**.
Do not promote or submit anything from this screen.

The no-training surface is exhausted enough to justify the next investment:
train a real deeper feature-based draft (EAGLE-class or a new calibrated DSpark
depth), with prose emphasized because it remains the dominant weak category.
Do not repeat the attached one-layer MTP, and do not invest further in host-side
confidence scheduling unless variable prefix length can stay device-resident
inside a persistent decoder transaction.

## Identity, exactness, patches, and evidence

- Target: K160 revision
  `7c360e1cd4a5168099dbc54d16d929bf6df04990`, unchanged quantization and
  TP4+EP topology.
- Record sanity runtime: vLLM `264c7f2f7df21ddeeab32ecca0353133344f1ac9`,
  XPU kernels `31315673737d95da0f79179c8f755260ef02c1d6`.
- Guarded vLLM confidence/width patch final commit:
  `1675864aa4415b56969974a3c2ff9740f4948187` (preceded by `00e781059`,
  `22895545b`, all on branch
  `codex/deepseek-v4-dspark-confidence-screen-20260719`).
- Lab harness and identity patch: `4cc659e0856e93ba200e09059f0309c0d81600f9`.
- Record sanity artifact:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/dspark-notraining-record-sanity-20260719T204500Z/continuity.json`.
- DEV artifact root:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/dspark-notraining-screen-20260719T211500Z/`.
- Every completed row has `identity.txt`, `dev-screen.json`, and passing
  pre-canary score; static widths also have passing post-canary scores. The
  initial confidence weight-map/shape failures, both M=8 router failures, and
  threshold-0.30 hang are retained under that root.
- Services were stopped cleanly after the screen; no generation process was
  left active.

## Protocol incident

All policy choices and measurements above used only the public+DEV workload,
and no frozen held-out pack was modified or used for a request. After the DEV
selection was already complete, however, a late overly broad `rg` evidence
lookup inadvertently emitted one matching line from each frozen held-out JSON
file. Their text was not used in this analysis. This agent must nevertheless
be treated as exposed and must not participate in any future held-out reveal
or scoring. If a later candidate merits held-out confirmation, Claude should
use an evaluator with no exposure to those packs.
