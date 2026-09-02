# Qwen3.8 FP8 TP2 row-invariant W8A16 kernel track, R120 to R146

Date: 2026-09-02 (chronology written by the CR2 review; every result below
is Codex's, recorded in `data/` and `DO-NOT-REPEAT.md` at the time)

Status: **no serving promotion; one endpoint result (R140) with the identity
question still open; R147 relaunches it under the CR1 oracle rule.**

## Why this track exists

The CR1 review closed layer-local isolation and reduced the c2 identity
failure to the whole-model oneDNN `fp8_gemm_w8a16` kernel: its FP32
reduction order depends on the M row-count class, so any batch shape can flip
an exact float16 logit tie. CR1 set the target as a row-invariant W8A16 GEMM
for all M, gated by the kernel census, followed by a regenerated c1 oracle and
the c1-c64 identity ladder. Two constraints bound every arm here: bitwise
row/permutation/repeat invariance across M=1..512 for the six per-rank
shapes, and call-count-weighted latency no worse than natural oneDNN at c1,
c64 (M128), and prefill M168/M256.

## Arms, in order

| arm | mechanism | identity | latency | verdict |
| --- | --- | --- | --- | --- |
| R120-R120e | oneDNN runtime-M primitive (`DNNL_RUNTIME_DIM_VAL`) | all six shapes invariant, repeat-exact M=1..512 | 1.9-5.2 ms per M=2 call, 24-123x static | closed; correctness reference only |
| R121 | Triton fixed-16-row block-FP8 | exact | 5.6-26x slower at M=2 | closed |
| R122/R122b | fixed-M4 broadcast-weight batched oneDNN | 5-6 row-0 classes as B changes | 0.99-1.14x | closed for identity |
| R123-R126a | pinned natural JIT strategies, fixed-M32 batching | exact | 1.24-1.33x geometric, up to 1.86x | closed |
| R127-R133 | Xe2 CUTLASS BLOCK_FP8 tiles, grouped and direct grids | exact, at most one FP16 ULP vs oneDNN | 1.28-2.02x geometric with the production NT weight view | closed; R127-R132 latency screens used the wrong weight layout |
| R134 | runtime switching between frozen M32 and M128 strategies | 0/90 outputs match across strategies | n/a | closed: shared `k128` tokens do not make switching safe |
| R135 | uniform exact source-M32 decode ladder | exact | +33% at c64/M128, +62-93% at prefill | closed; exact reference retained |
| R136 | fixed-K scheduling variants | M128 32x32 `wgK=2 ikr ki64 k128` matches M32 on 90/90 | 1.0169x natural at c64 | **accepted geometry** |
| R137/R137a | source selector, activation gate | activation miss | n/a | rejected before dense expansion |
| R137b | selector with default C alignment | passes all-shape dense gate | 1.0328x c64, missed 1.03 by 0.0028 | arithmetic accepted; paired confirmation ordered |
| R138 | paired natural/source A-B-B-A | exact | passes c1-c64 and stability gates | operator-qualified |
| R139 | portable serving image over the exact R62 base | build only | n/a | image `sha256:901ae9e0...` |
| R140 | two-B70 endpoint on R139 | operator gate passed in the production image, including repeat and 168-to-200 padding exactness; **8/12 vs the frozen natural R54a oracle** | 53.803 tok/s class-balanced, -1.14% vs the R119 center, below the 54.0 floor | rejected on both; ladder and probe never ran |
| R141 | M4-anchored catalog geometries | source-M4 eight-way local-K strategy reproduces natural M1/M2/M4 arithmetic | all four candidates rejected at M128 | anchor proven, catalog closed |
| R142 | direct-grid Xe2 K8-split ascending reduction, 16x64 tile | bitwise equal to natural-M1 rows at every M | 3.4-7.2x | mechanism accepted, geometry closed |
| R143 | larger K8 tiles with sliced SLM reduction | exact | 1.5-2.7x; 64x128 spilled 167 registers | closed |
| R144 | oneDNN eight-live-register K8 reduction | 72/72 exact to natural-M1 rows | 0.970x at M64, 1.314x at M128 | arithmetic accepted, geometry closed |
| R145 | `wg8x4` scheduling audit | exact | 1.316x at M128 | closed |
| R146 | two-buffer serial K8, 32x32 tile | preregistered, not run | | pending |

## What the track established

- A row-invariant, repeat-deterministic W8A16 GEMM at production cost exists:
  the R136/R137b fixed-K selector, packaged as R139 and confirmed in the
  production image by R140's operator gate. It also closes the 168-256-row
  repeat-determinism hole at the operator level.
- Its arithmetic is the source-M32 class, not the natural M1/M2/M4 class. Any
  such kernel changes a few near-tie tokens relative to the natural R54a
  oracle; R140 measured 4 of 12 arrays.
- Reproducing natural-M1 arithmetic bit for bit requires the eight-way
  64-K-chain reduction order (R141/R142/R144), and every geometry that
  preserves it has so far cost at least 1.31x at M128.

## Review finding (CR2)

R140 gated identity against the frozen natural oracle. CR1 step 4 said to
regenerate the c1 oracle from the invariant build, because the frozen oracle
is one arbitrary M-class answer and a localization tool. R141 through R146 are
therefore spending effort on a constraint the identity claim does not need.
The publication contract is same-image MTP1 equals same-image MTP0, canaries
pass, and c1 repeats are deterministic. R140's remaining defect is a
single-server 1.14% throughput miss inside the host's 3% control-vs-control
band. R147 reruns the R139 image under the CR1 rule with two MTP0 controls,
two MTP1 candidates, the medium-prefill probe, and the c1-c64 ladder; R146 is
paused until R147 answers whether natural-M1 anchoring is needed at all.

Evidence: `data/2026-09-02-qwen38-fp8-w8a16-*-r1{20..46}-*.json`,
`data/2026-09-02-qwen38-fp8-mtp1-fixed-k-{serving-r139,endpoint-r140}-result.json`,
`DO-NOT-REPEAT.md` rows dated 2026-09-02.
