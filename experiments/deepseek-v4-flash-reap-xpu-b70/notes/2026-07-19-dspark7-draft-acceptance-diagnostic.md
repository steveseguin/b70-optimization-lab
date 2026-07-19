# DSpark7 draft-acceptance diagnostic — 2026-07-19

## Numbers first

- Exact K160/DSpark7 record recipe confirmed at **80.65083273112313 tok/s**
  median generated-token throughput for tokens 1-100 after TTFT on the public
  12-prompt continuity suite. All 12 requests had `cached_tokens=0`. This is a
  DEV sanity confirmation, not a record or promotion run.
- The combined 22-prompt DEV diagnostic produced **1,958 accepted / 5,467
  drafted tokens = 35.8149%**, **781 target cycles**, and **3.5070 emitted
  tokens/cycle** by the standard `1 + accepted/cycles` convention.
- **Position-1 acceptance was 78.2330%** overall. It was 76.3636% on the public
  continuity subset alone. Position 1 is not the main loss.
- Marginal acceptance decayed from **78.23% at position 1 to 8.45% at position
  7** overall. On the public continuity subset it fell from 76.36% to 3.84%.
- Primary diagnosis: **(b) a deeper/stronger multi-position predictor is
  required**. A fundamentally better adapted DSpark/DFlash/DEAGLE-style block
  draft, option (d), is the likely implementation vehicle. This is not an (a)
  single-step problem. Category specialization (c) is secondary: prose is much
  weaker than the structured categories, but every substantial category still
  loses marginal acceptance with depth.

## Identity and sanity

The successful service used:

- target: `/mnt/fast-ai/llm-models/deepseek-v4-flash-xpu/current-k160`;
- target revision: `7c360e1cd4a5168099dbc54d16d929bf6df04990`;
- served model: `deepseek-v4-flash-k160`;
- draft pack: `dspark-draft-pack-aa22cb0`, M=7 draft / M=8 target verify;
- vLLM: `264c7f2f7df21ddeeab32ecca0353133344f1ac9`;
- XPU kernels: `31315673737d95da0f79179c8f755260ef02c1d6`;
- oneCCL: `48fda4f0e074db005596d6899d5227d3f0316c12`;
- target and draft compile levels: `PIECEWISE`;
- exact record-path flags, including exact-query capture, fused greedy
  rejection, sharded target argmax, fixed M7 target inputs, persistent Markov,
  replicated W1, and the documented M8 kernel width guards. Rejected
  host/event/sharded-Markov alternatives remained zero.

The identity matches the record commits, model revision, quantization, draft
pack, and flags. The text diff consists of the detached exact-commit worktree
paths plus identity fields newly emitted by the current launcher (explicit
sharded-target-argmax/default-zero fields and unique IPC names).

Two public continuity screens were retained. The first was 77.6533 tok/s
median; a same-recipe confirmation was **80.6508 tok/s median**, 69.4548 p10,
77.9471 mean, and 328.300 ms median TTFT. The confirmation passed the script's
fresh-response checks with 128/128 token-ID events on every row and zero cached
tokens. The spread between the two screens is run variance; the confirmation
establishes the expected approximately 78-81 tok/s path.

## DEV workload and method

The final diagnostic used the public 12-prompt continuity suite plus ten
explicitly DEV prompts: two each for code, prose, math, extraction, and
low-locality copying/transformation. The public prompts were assigned a
category without changing their text. Requests were sequential, used unique
request IDs and cache salts, greedy seed 1, and had no prefix cache reuse.

The committed frozen evaluator has no DEV/non-frozen mode: it requires the two
fixed frozen packs and validates their identities. It was therefore not
invoked. The DEV profiler reads only the public suite and the new DEV suite and
snapshots existing vLLM Prometheus counters immediately before and after each
request. It has no frozen-pack path or pack knowledge.

For cycle count `D` and accepted-at-position counts `A1..A7`:

- marginal position `i` acceptance is `Ai / D`;
- conditional position 1 acceptance is `A1 / D`;
- conditional position `i > 1` acceptance is `Ai / A(i-1)`;
- run-length counts are `D-A1`, `A1-A2`, ..., `A6-A7`, `A7`;
- emitted tokens/cycle is `1 + sum(Ai)/D`.

Every request passed `draft_tokens = 7 * cycles`, and each request's seven
position counts summed to its accepted-token count. No other generation was
active. The low-locality outputs ended naturally at 177 tokens total, so the
observed completion/cycle number is also reported where useful; it differs
slightly from the standard emitted/cycle estimator because of EOS and final
boundary truncation.

## Per-position acceptance

Combined 22-prompt DEV result, 781 cycles:

| Draft position | Accepted count | Marginal | Conditional |
|---:|---:|---:|---:|
| 1 | 611 | 78.23% | 78.23% |
| 2 | 470 | 60.18% | 76.92% |
| 3 | 336 | 43.02% | 71.49% |
| 4 | 223 | 28.55% | 66.37% |
| 5 | 149 | 19.08% | 66.82% |
| 6 | 103 | 13.19% | 69.13% |
| 7 | 66 | 8.45% | 64.08% |

The public 12-prompt subset independently shows the same shape: marginal
`[76.36, 55.15, 35.35, 20.81, 12.73, 7.47, 3.84]%`, conditional
`[76.36, 72.22, 64.10, 58.86, 61.17, 58.73, 51.35]%`, 30.2453% total draft
acceptance, and 3.1172 emitted tokens/cycle over 495 cycles. This subset is
close to the historical record-screen structure (about 31.5% and 3.20/cycle).

## Per-category acceptance

Marginal probability that a cycle accepts through each draft position:

| Category | Prompts | Cycles | P1 | P2 | P3 | P4 | P5 | P6 | P7 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| code | 5 | 198 | 74.24% | 57.07% | 40.40% | 25.76% | 15.15% | 7.58% | 5.56% |
| prose | 9 | 382 | 75.13% | 52.09% | 32.72% | 19.90% | 10.73% | 7.07% | 3.40% |
| math | 2 | 53 | 84.91% | 79.25% | 71.70% | 54.72% | 49.06% | 33.96% | 22.64% |
| extraction | 4 | 114 | 86.84% | 73.68% | 56.14% | 40.35% | 33.33% | 28.07% | 21.93% |
| low-locality | 2 | 34 | 97.06% | 94.12% | 85.29% | 61.76% | 41.18% | 32.35% | 14.71% |

Conditional probability at each position, given all earlier positions survived:

| Category | P1 | P2\|P1 | P3\|P2 | P4\|P3 | P5\|P4 | P6\|P5 | P7\|P6 |
|---|---:|---:|---:|---:|---:|---:|---:|
| code | 74.24% | 76.87% | 70.80% | 63.75% | 58.82% | 50.00% | 73.33% |
| prose | 75.13% | 69.34% | 62.81% | 60.80% | 53.95% | 65.85% | 48.15% |
| math | 84.91% | 93.33% | 90.48% | 76.32% | 89.66% | 69.23% | 66.67% |
| extraction | 86.84% | 84.85% | 76.19% | 71.88% | 82.61% | 84.21% | 78.12% |
| low-locality | 97.06% | 96.97% | 90.62% | 72.41% | 66.67% | 78.57% | 45.45% |

Category summary:

| Category | Draft-token acceptance | Emitted tokens/cycle | Observed completion tokens/cycle |
|---|---:|---:|---:|
| code | 32.25% | 3.258 | 3.232 |
| prose | 28.72% | 3.010 | 3.016 |
| math | 56.60% | 4.962 | 4.830 |
| extraction | 48.62% | 4.404 | 4.386 |
| low-locality | 60.92% | 5.265 | 5.206 |

Prose is the most important weak category: it supplies 382/781 cycles and only
3.010 emitted tokens/cycle. The arbitrary-code tasks were unexpectedly easy
for this draft, likely because exact copying and repeated code structure make
local transitions useful; with only 34 cycles, low-locality is directional,
not a standalone model-selection result. Math also has only 53 cycles. The
large category spread supports category-aware analysis, but it does not change
the primary depth-decay diagnosis.

## Accepted-run-length distribution

`Accepted draft tokens` ranges from 0 through 7. Adding the always-produced
target fallback/bonus gives the corresponding 1 through 8 emitted-token width.

| Accepted draft tokens | Corresponding emitted width | Cycles | Probability |
|---:|---:|---:|---:|
| 0 | 1 | 170 | 21.77% |
| 1 | 2 | 141 | 18.05% |
| 2 | 3 | 134 | 17.16% |
| 3 | 4 | 113 | 14.47% |
| 4 | 5 | 74 | 9.48% |
| 5 | 6 | 46 | 5.89% |
| 6 | 7 | 37 | 4.74% |
| 7 | 8 | 66 | 8.45% |

Only 21.77% of cycles fail immediately, but 69.01% stop by the end of draft
position 3. That is the compact evidence for a depth problem rather than a
globally weak first token.

## Draft confidence

No acceptance-versus-confidence curve was collected. The exact greedy DSpark
path exposes selected token IDs and acceptance counters but not a numeric draft
confidence. The model loader explicitly drops `confidence_head` weights because
the head is not wired into inference. Capturing full Markov/draft logits would
add a new synchronization and telemetry path to the timed recipe, so it was not
cheap or nonperturbing enough for this run.

## Diagnosis and first experiment

The answer is **(b), depth/multi-position prediction**, with **(d), an adapted
block draft**, as the likely solution family:

- position 1 is already **78.23%**, so strengthening only the next-token draft
  cannot recover the dominant loss;
- conditional survival falls to roughly 64-69% at the deep positions, and the
  compounding product leaves only 8.45% marginal survival at position 7;
- prose is worse, but the decay exists in all nontrivial categories, so a
  category router alone will not fix it;
- repeating K160's one-layer MTP to M4 is already rejected and should not be
  repeated.

The first concrete draft-improvement experiment should be a **DEV-only,
position-weighted adaptation of the parallel DSpark/DFlash block drafter**, not
another target optimization and not repeated one-layer MTP. Keep the exact
K160 target, M8 verifier, quantization, and current cycle harness fixed. Train
or adapt only the draft on target-generated DEV continuations, weighting exact
greedy agreement at positions 3-7 more heavily while protecting position 1.
Before any endpoint integration, score it offline on disjoint DEV prompts with
this same per-position evaluator. Require position-1 acceptance no worse than
the 76.36% public baseline, a material lift in positions 3-7, and at least 45%
overall DEV draft-token acceptance before paying integration cost. Then measure
accepted tokens per complete wall cycle; acceptance without cycle-cost parity
is not a win. A DEAGLE/DFlash-style or properly adapted multi-head MTP draft is
the next family if the existing DSpark block cannot meet that offline gate.

## Artifacts

Run directory:

`/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/dspark7-acceptance-diagnostic-20260719T184837Z`

Important files and SHA-256:

- `identity.txt`: `0d3f87080fd9e972fa5253ccba87b72ee13ab52acebe6de1246f1cc5df436a19`;
- `sanity-screen.json`: `e64f673c58d48e226f2a0dfb630c4f8bbace628d0accd1cde8ac0a4e37bdb5bd`;
- `sanity-confirm.json`: `5f287b599934216eb0bd5f47bb938169ffbbf543c96d6d4d83c6aa9ec7dc0f64`;
- `draft-acceptance-dev-v2.json` (final):
  `5ee17ce93718529c1a4dc0d43a9955e1742284b2059b0d8d406b6d792e6812d8`;
- `draft-acceptance-dev.json` (preserved superseded short low-locality pass):
  `956ebeb50069bfb04b605ae51f81dde5911d32d9c2ecd2fa3d425ddb34327dfd`;
- `server.log`: `8fa7ff996abf25a2a09bc38db37588d2f784f972b9947f6fef760bf805396831`.

Repository additions:

- `data/dspark7-draft-acceptance-dev-suite-v1.json`;
- `scripts/profile-dspark-draft-acceptance-dev.py`;
- this note.

No LocalMaxxing submission or record claim was made. The frozen held-out pack A
and pack B files were not opened, read, modified, or passed to any command. The
service was stopped cleanly after the run, no serving processes remained, and
all four XPU allocators reported zero allocated bytes.
