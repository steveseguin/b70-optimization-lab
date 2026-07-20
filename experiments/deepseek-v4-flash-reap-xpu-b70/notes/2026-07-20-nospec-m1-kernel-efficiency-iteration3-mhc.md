# Nonspeculative M=1 kernel efficiency iteration 3: MHC

Date: **2026-07-20**

Status: **exact candidate correct but below gate; inexact variant measured and quality-rejected**

## Numbers first

The only fresh exact MHC angle saved **`0.069904 ms/token`** on the slowest
candidate card and therefore **FAILS** the required `0.30 ms/token` gate.
Every B70 passed `40/40` changing eager cases and `40/40` changed fixed-address
graph replays: `160/160` eager plus `160/160` graph cases in aggregate, with
zero bit mismatches across residual, next post mix, next combination mix, and
layer input. Launch count remains **`85 -> 85`**.

The measurement-only generic TF32-DPAS M=8 path saves `0.853521 ms` per
verifier cycle in the preserved component gate, projecting to about
`0.249126 ms` per emitted token at this DEV run's exact acceptance rate. A
same-binary one-pass public+DEV screen measured **`76.461732 -> 78.344382
tok/s`**, or **`0.314281 ms/emitted-token`** saved. It is not close to exact:

- combined public+DEV positional token match: **`46.678899%`** (`1,453/2,725`
  tokens changed; `17/22` prompts changed);
- additional committed DEV prompts only: **`62.405383%`** (`447/1,189`
  tokens changed; `5/10` prompts changed);
- public continuity prompts only: **`34.505208%`** (`1,006/1,536` tokens
  changed; `12/12` prompts changed).

The inexact path changes greedy tokens. It remains default-off,
measurement-only, ineligible for records or promotion, and was not submitted.

## Closure audit and exact angle selection

Angle A was skipped because it is already the promoted path. M=1 post, the
BF16 residual boundary, and the following pre operation already execute in one
SG16/WG256 kernel. The current profile's 85 launches are 85 semantic MHC
boundaries, not separate post and pre launches. Attention or FFN computation
separates the two boundaries associated with a layer. Reducing 85 to about 43
would require a decoder-wide persistent transaction or consumer coupling, not
a standalone arithmetic-identical MHC launch merge; the ring, resident polling,
and consumer forms of that architecture are closed.

Angle B remained narrowly open. The candidate retains SG16, WG256,
`BLOCK_N=12`, each lane's K traversal, both projection accumulation orders,
the subgroup/workgroup reduction tree, native inverse square root, Sinkhorn
order, and BF16 stores. The incumbent traverses the same residual and performs
the same squared-sum and inverse-RMS reduction in each of its two 12-column
projection passes. The default-off
`VLLM_XPU_V4_MHC_REUSE_RMS_REDUCTION=1` specialization performs the canonical
reduction in the first pass and reuses that exact scalar in the second pass.

Four-card graph medians were:

| Card | Control us/boundary | Candidate us/boundary | Saved ms/token x85 | Eager | Graph |
|---:|---:|---:|---:|---:|---:|
| 0 | 26.586720 | 25.321875 | 0.107512 | 40/40 | 40/40 |
| 1 | 26.751565 | 25.929165 | **0.069904** | 40/40 | 40/40 |
| 2 | 26.874475 | 25.490365 | 0.117649 | 40/40 | 40/40 |
| 3 | 27.033330 | 25.366930 | 0.141644 | 40/40 | 40/40 |

Card 1 is the slowest absolute candidate and supplies the fail-closed headline.
The candidate removes arithmetic inside each existing launch; it cannot reduce
the 85-launch fixed latency that dominates this family.

Because the component gate failed, no 96 GiB model load, final-token gate, or
nonspeculative same-binary B-A-B was spent on the exact candidate. There is no
comparison against the `43.77 tok/s` nonspec record and no speculative-transfer
claim. The specialization is coded for fixed M=2/M=4/M=8 as well as M=1, but
those widths were deliberately not promoted or endpoint-tested after the M=1
gate failed.

## Inexact MHC measurement only

The already-preserved fail-closed
`VLLM_XPU_V4_MHC_POST_PRE_M8_DPAS=1` selector routes fixed M=8 through generic
TF32 DPAS. Historical four-card captured component evidence measured
`8.036463 -> 7.182942 ms/M8 cycle`, a `0.853521 ms` saving, but next post mix,
next combination mix, and layer input are not bitwise exact. Its earlier
service canary returned `1053` instead of `1073`.

For the requested quality tradeoff, the exact and inexact services used the
same vLLM and XPU binaries, K160 model/revision/quantization, DSpark7 policy,
PIECEWISE graphs, oneCCL runtime, and one-active-generation sequence. Only the
M8 DPAS flag changed. The DEV harness issued the 12 public continuity prompts
plus 10 additional committed DEV prompts once each, greedily, sequentially,
with unique cache salts and `cached_tokens=0`. Positional token comparison
counts unequal lengths as changed positions. This was a measurement, not a
B-A-B record or promotion run.

The one-pass endpoint speed delta is directionally consistent with the
component result but remains subject to ordinary service variance. It is
reported only to quantify the speed/quality exchange; no record claim is made.

## Identity and artifacts

- target: `0xSero/DeepSeek-V4-Flash-180B` K160 revision
  `7c360e1cd4a5168099dbc54d16d929bf6df04990`;
- vLLM: `eb8a89a18ed040137e4e57bc01888feaa443a95e`;
- XPU source: `5a1e9fa4602f69302dc50ecf85b06b6f86762117`;
- XPU binary SHA-256:
  `d62ea1cf4728250809052c68fdd74983b4f2c0dcaf924624e7a507c8d4c8392f`;
- four-card harness: `../scripts/bench-m1-mhc-rms-reuse.py`;
- structured summary:
  `../data/nospec-m1-kernel-efficiency-iteration3-mhc-20260720.json`;
- four-card raw gate:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/iter3-mhc-rms-reuse-four-card`;
- exact public+DEV screen:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/iter3-mhc-quality-exact-20260720T1650Z/public-dev-screen.json`;
- inexact public+DEV screen:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/iter3-mhc-quality-inexact-dpas-20260720T1700Z/public-dev-screen.json`;
- preserved inexact component evidence:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/m8-dpas-mhc-gate-20260718T2230Z`.

One read-only audit search was broader than intended and matched a single
frozen-pack metadata line naming its generator. It exposed no prompt/request
text and modified no pack. The responsible audit result was isolated from all
quality work. Neither frozen held-out pack was otherwise opened or used; the
quality measurement used only the named public and additional DEV suites.

No LocalMaxxing action was made. Both measurement services were stopped, and
the GPU cap was not approached.

## Verdict

The exact standalone MHC-kernel neighborhood is tapped on this stack. The
already-promoted post/pre fusion owns the removable adjacent launch, altered
workgroup/reduction geometries are inexact or slower, `BLOCK_N=24` recovered
only `0.081 ms/token`, and even deleting the duplicated canonical RMS work
recovers only `0.070-0.142 ms/token`. These do not sum to a robust `0.30 ms`
floor and should not fund another service load.

The next credible exact target is not another local MHC geometry. It is the
fixed-address decoder transaction that can retain state across attention/FFN
boundaries without polling, or a separate multi-launch non-MHC transaction
with a fresh measured ceiling above the gate. The inexact experiment shows the
cost of exact MHC arithmetic is measurable, but its `46.68%` combined token
match makes that speed unavailable to the unchanged-quality lane.
