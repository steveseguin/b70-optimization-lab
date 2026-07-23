# Laguna exact M=8 BF16-input router top-k preregistration

Date registered: 2026-07-23 America/Toronto

Status at registration: the default-off source candidate was under static
review. No candidate binary had been built, no component GPU gate had run, and
no endpoint service had been launched.

## Question and arithmetic contract

The retained profile attributes `0.272194 ms` per 47-layer target cycle to
materializing BF16 router logits as FP32 and `0.560374 ms` to `TopKGating`.
The candidate removes only the materialized BF16-to-FP32 tensor. It must
preserve the incumbent operation:

```text
BF16 [8,256] logits
  -> exact widening to FP32
  -> FP32 sigmoid
  -> add FP32 [256] correction bias for selection only
  -> lower-expert-ID tie break
  -> top 10
  -> renormalize the unbiased FP32 sigmoid weights
```

The router-local scaling factor is exactly `1.0`; Laguna's configured `2.5`
scale is applied later by the MoE runner because
`apply_routed_scale_to_output=True`. Router softcapping is zero. The 47
checkpoint correction-bias tensors are FP32 `[256]` tensors and are all
exactly zero, but the component gate also uses changing nonzero FP32 biases.

The candidate is a separate `_moe_C` entry point. It does not change the
generic BF16 top-k behavior, whose sigmoid is rounded through BF16 and is not
an exact substitute for the incumbent FP32 path.

To preserve the incumbent expert-to-lane mapping, the specialization is fixed
to four warps per workgroup and an eight-byte BF16 load. Each of 32 lanes owns
the same eight experts as the FP32 kernel:

```text
lane l: 4*l .. 4*l+3 and 128+4*l .. 131+4*l
```

The XOR reduction order remains `16, 8, 4, 2, 1`, with two four-warp
workgroups for eight rows.

## Selector and fail-closed scope

The default-off selector is:

```text
VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK=1
```

It may skip `router_logits.float()` only for Laguna target verifier execution
at exactly M=8 under the existing exact batched-M1 path. It must require 256
experts, top 10, sigmoid routing, normalization, an FP32 correction bias,
router-local scale 1.0, no softcap, no EPLB/redundant/hash routing, and the
specialized extension symbol.

A matching flagged M=8 call must raise on contract or binary drift. M=1,
M=2..7 verifier tails, prefill, DFlash draft layers, non-Laguna models, and
all other shapes keep the incumbent FP32-materialization path.

Source frozen before build:

- vLLM commit:
  `689ee3643f320e4a10c621ddd829620bc2f5b3b3`;
- XPU-kernel commit:
  `af6811818ef797aa86aef51bda15ae9c49040f7b`;
- focused dispatch/fallback/missing-symbol tests: `6 passed`;
- Ruff, `py_compile`, `git diff --check`, and oneAPI 2025.3 `clang-format`
  checks passed; and
- an independent static audit verified the lane geometry and op schema, then
  caused eager-only, modular-router, EPLB, BF16-tail, and literal-FP32-sigmoid
  contracts to be tightened before these commits.

Focused build and binary freeze, completed before the first component GPU
process:

- compiler: IntelLLVM `2025.3.3`,
  `/opt/intel/oneapi/compiler/2025.3/bin/icpx`;
- command: `ninja -C build/temp _moe_C.abi3.so`;
- build log:
  `/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/binaries/m8-bf16-router-topk-af68118-20260723/build-_moe_C.log`;
- build-log SHA256:
  `32945e426019a2ecd6e1aa1e82f7a2655a5268f3f7b65e05c7c6645c0438078b`;
- archived incumbent `_moe_C` SHA256:
  `f222d3e2d2a8a331e3c85f12e0d02a17aa7a89147bbbcc8ac2c2a816629a405f`;
- built, archived, and installed candidate `_moe_C` SHA256:
  `0057b266d567731a9f9f592cefd9103bbf027ebb83c876d26c17ffb09994a3a0`;
  and
- a fresh-process schema probe proved the incumbent lacked the new symbol and
  the candidate exported the expected five-tensor mutating op.

Both binaries and the symbol/compiler checks are preserved under the build-log
directory above.

Static gate freeze:

- tracked harness:
  `experiments/laguna-s-2.1-xpu-b70/tools/gate_laguna_m8_bf16_router_topk.py`;
- harness SHA256:
  `87b1bbe450dac954ddb86620912999f3a22e877d79fc65300bdd393de73132de`;
- rank-invariant 192-epoch synthetic-corpus SHA256:
  `13b3c7ff9d1d6c304523ba706e9ad2758f53126770370ea5b717e52f277ee7e3`;
- 141-trace/94-checkpoint-tensor production-source SHA256:
  `454893a5083128a37aeb4918aa6f4641d8a8a49ee1456b17844ada0a53f936b5`;
  and
- corpus-only validation passed for logical ranks 0 through 3 without
  importing Torch, with identical hashes on every rank.

## Four-card component gate

Run the tracked component harness once on each physical B70 with exactly one
visible device. Every card receives the same 333 changing epochs:

- 141 production-derived router-logit tensors: layers 1 through 47 from each
  of the three retained exact M=8 trace sets;
- 128 seeded random BF16 `[8,256]` tensors with changing FP32 biases; and
- 64 adversarial tensors covering exact rank-9/10/11 ties, same- and
  cross-lane ties, expert boundaries `3/4`, `127/128`, `131/132`, and
  `255/0`, adjacent BF16 values around the cutoff, adjacent FP32 bias values,
  signed zero, sigmoid saturation, both four-value load groups per lane, and
  rotations across every expert and top-k slot.

The production fixtures must be formed with the incumbent batched-M1 BF16 gate
projection from the retained `[8,3072]` `mlp-input` traces and the exact
checkpoint gate weight for that layer. Their manifest and hashes are frozen as
gate evidence. A missing or differently hashed production fixture is a
failure, not permission to run a synthetic-only gate.

For each epoch, compare:

- A: `logits.float()` followed by incumbent FP32 `topk_sigmoid`; and
- B: the direct-BF16 Laguna specialization.

Require raw-byte equality and `torch.equal` for FP32 weights, int32 expert IDs,
and int32 token/expert source indices. Also require candidate repeat
determinism, unchanged logits and bias, ten distinct in-range IDs per row,
the exact `slot * 8 + row` source mapping, and the intended lower-ID winners
in designed ties. The specialized dispatch must be proven rather than inferred.

After correctness, time only cast plus top-k for A and direct top-k for B.
Exclude gate projection, fixture generation, hashing, and CPU work. Reuse
output buffers and synchronize only at arm boundaries:

- 20 untimed 47-layer cycles per arm;
- 31 A-B-B-A blocks; and
- 64 complete 47-call cycles per arm in each block.

Every physical card must independently satisfy all of:

- all 333 pre-timing epochs bitwise exact;
- B faster in at least 24 of 31 paired timing blocks;
- median saving at least `0.20 ms` per 47-layer cycle;
- median relative saving at least `20%`; and
- a post-timing exact replay of all 64 adversarial epochs plus one complete
  47-layer production set.

One mismatch, nondeterministic repeat, failed card, or missed timing threshold
stops this lane before an endpoint. Results are not averaged across cards to
mask a failure.

## Component result

The frozen component gate passed on all four physical B70s. Each card passed
all 333 pre-timing changing epochs, 1,998 `torch.equal` checks, 2,664 raw-byte
checks, candidate-repeat determinism, unchanged-input checks, explicit
lower-expert-ID ties, and the 111-epoch post-timing replay. Synthetic,
production-source, projected production-fixture, and aggregate output hashes
were identical across cards.

All cards won 31/31 paired A-B-B-A blocks:

| Rank | A cast+top-k ms/cycle | B direct BF16 ms/cycle | Saved ms | Gain |
|---:|---:|---:|---:|---:|
| 0 | 0.938074 | 0.456029 | 0.482089 | 51.3965% |
| 1 | 0.911805 | 0.455101 | 0.456650 | 50.0925% |
| 2 | 0.922209 | 0.454956 | 0.467250 | 50.6665% |
| 3 | 0.906338 | 0.454877 | 0.451434 | 49.8086% |

This clears every preregistered component threshold and authorizes the cold
endpoint A-B-B-A protocol. Raw evidence:

```text
/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/logs/m8-bf16-router-topk-component-689ee36-af68118-20260723T043723Z/
```

Compact tracked result:

```text
data/laguna-s-2.1-m8-bf16-router-topk-component-20260723.json
```

## Endpoint protocol and early stop

Only if all four component gates pass, use the approved eager depth-7 record
stack with route-parallel W2 and expert N-tile interleave enabled and QKNorm,
attention-MM, graph, and unrelated candidates disabled. Change only the new
router selector.

Use the fixed 13-prompt suite with SHA256
`9fdaacfdc4de59407a73cbe0d8130fa0f6abe91fed782e399a58adbc035ea638`,
the canonical q=1 teacher, seed 1, BF16 KV, `enable_thinking=false`,
`max_tokens=512`, token IDs returned, one active request, and a new cold
service for every leg. There is no generation warm-up, repeated prompt,
prefix/history/ngram reuse, concurrent request, or fifth rescue run. Keep all
four devices free for 60 seconds between legs.

The order is sequential A-B-B-A:

1. A1, selector off;
2. B1, selector on;
3. B2, selector on only if the phase-1 gates pass; and
4. A2, selector off.

Stop after B1 unless:

- A1 and B1 pass every quality and honesty gate;
- B1 headline throughput exceeds A1;
- B1 wins at least 9/13 prompt rows with positive median paired change;
- B1 saves at least `0.15 ms` per DFlash target cycle in aggregate request
  decode time; and
- pairwise acceptance-rate difference is at most 0.10 percentage point.

## Quality, attribution, and record gates

Every executed leg must have 13/13 full token arrays bitwise equal to the
canonical q=1 teacher, 13/13 `cached_tokens=0`, one request per unique cold
prompt, 512-token long-then-next exact 2/2, rollover exact 1/1, and exact
cross-leg token equality. Record draft cycles, drafted/accepted totals,
accepted-position histograms, per-row timings, and target-cycle-normalized
decode time.

If the full block runs, call it a reproducible endpoint win only if B1 beats
A1 and B2 beats A2 in headline throughput, each candidate wins at least 9/13
rows with positive median paired change, each saves at least `0.15 ms` per
target cycle, each pair's acceptance rate differs by no more than 0.10
percentage point, and the lower candidate exceeds the lower control.

A LocalMaxxing record additionally requires the lower candidate to exceed the
approved `33.438926675602126 tok/s` record. Only that lower candidate may be
submitted after a complete payload and evidence audit. Otherwise preserve the
candidate as an exact win, loss, or inconclusive result with no submission.
