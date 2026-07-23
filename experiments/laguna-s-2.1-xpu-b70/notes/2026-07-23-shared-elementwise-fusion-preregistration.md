# Laguna exact M=8 shared-elementwise fusion preregistration

Date registered: 2026-07-23 America/Toronto

Status at registration: design and gates frozen before implementation, native
build, formal component timing, or endpoint generation. Two read-only source
audits independently selected this lane.

## Why this lane

The approved route-interleaved profile attributes these target-cycle costs to
four pointwise kernels:

- shared-expert SiLU plus multiply: `0.246532 ms`;
- routed-output BF16 scale by `2.5`: `0.083971 ms`; and
- shared+routed BF16 addition: `0.104015 ms`.

The proposed bundle removes one launch at each boundary without changing a
GEMM, routed gather, reduction, collective, or DFlash operation. It attacks
`0.434518 ms` per 47-layer target cycle and is expected to save about
`0.18-0.24 ms`.

This follows a decisive rejection of the initially attractive shared gate/up
projection merge. A card-0 changing-input screen measured:

| Projection form | Median per 47 layers | Raw BF16 exact epochs |
| --- | ---: | ---: |
| incumbent two B=8, M=1, N=256 BMMs | 4.878882 ms | reference |
| one B=8, M=1, N=512 BMM | 2.887278 ms | 24/64 |
| broadcast logical-B=16, M=1, N=256 | 4.406169 ms | 18/64 |

The oneDNN primitive's batch, stride, and N geometry are therefore part of the
arithmetic identity. Both merged forms are disqualified despite their speed.
No packed-weight or loader change is allowed in this experiment.

## Candidate arithmetic

The default-off umbrella selector is:

```text
VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE=1
```

It enables two independently gated native operations.

### Separate-input shared SiLU and multiply

The incumbent remains:

```text
gate = exact B=8/M=1/N=256 BF16 BMM
up = exact B=8/M=1/N=256 BF16 BMM
silu = BF16(F.silu(gate))
activated = BF16(silu * up)
```

The candidate accepts separate contiguous BF16 `gate` and `up` tensors with
shape `[8,256]`. It must retain the BF16 SiLU intermediate before multiplying;
it must not concatenate, copy, widen, merge, or retile either projection.

The existing packed `_C.silu_and_mul` is not copied blindly. A pre-build
semantic screen compared its raw output to `F.silu(gate) * up` for every
finite BF16 gate bit pattern. It found one mismatch among 65,280 values:

```text
gate bits 0x40be = 5.9375
PyTorch BF16 SiLU bits 0x40bd = 5.90625
existing fused-op bits 0x40be = 5.9375
```

This is an exponential-approximation midpoint. The new operation must match
the PyTorch result for this value and all other finite BF16 inputs. A random
256-epoch check alone is insufficient; it previously missed this case.

### Routed scale plus shared add

The incumbent performs two BF16 tensor operations:

```text
routed_scaled = BF16(routed * 2.5)
result = BF16(shared + routed_scaled)
```

The candidate performs both in one native kernel but must explicitly
materialize the first BF16 rounding in a local BF16 value before the addition.
The late fixed-rank all-reduce and every following consumer remain unchanged.

## Fail-closed runtime contract

Enabling the selector must raise rather than silently fall back unless all of
these are true:

- Intel XPU execution;
- Laguna target, not DFlash draft;
- the exact speculative target path and explicit verifier marker;
- exactly eight rows;
- contiguous BF16 gate/up tensors `[8,256]`;
- contiguous BF16 shared/routed/output tensors `[8,3072]`;
- configured TP4, EP4, DP1, and PP1;
- eager execution with XPU graph and deterministic graph disabled;
- depth-7 DFlash with one active cached request and seven draft tokens;
- one shared expert, routed scale exactly `2.5`, no routed-output transform;
- the approved exact batched-MoE, fused-W1/route-W2, and route-interleave
  selectors are enabled; and
- both rebuilt native symbols are present.

M=1, verifier tails M=2..7, prefill, draft, non-Laguna models, graph execution,
LoRA, and incompatible shared-expert layouts retain the literal incumbent
path. The enabled matching M=8 path must prove both native dispatches occurred.

## Four-card component gate

Run each physical B70 independently with one visible Level Zero device. One
failure stops the lane before an endpoint.

Correctness for the shared activation must include:

- all 65,280 finite BF16 gate bit patterns with `up=1`;
- the same gate set paired with reversed finite BF16 up values;
- signed-zero and subnormal up values;
- at least 256 changing random `[8,256]` gate/up epochs;
- raw `uint16` equality and `torch.equal` against `F.silu(gate) * up`;
- unchanged gate and up input hashes;
- candidate repeat determinism; and
- a complete post-timing replay, including gate bits `0x40be`.

Correctness for scale+add must include:

- every finite BF16 routed value crossed with shared values zero, one, signed
  zero, and a reversed finite-value vector;
- at least 256 changing random `[8,3072]` shared/routed epochs;
- a literal two-operation PyTorch reference with a BF16 scaled intermediate;
- raw `uint16` equality and `torch.equal` for the final sum;
- unchanged shared/routed input hashes and candidate repeat determinism; and
- a complete post-timing replay.

The formal gate must also prove that M=1, M=2..7, prefill, draft, wrong dtype,
wrong shape, noncontiguous inputs, graph mode, and a missing symbol cannot
silently execute the treatment.

## Frozen timing gate

Time the activation fusion, scale+add fusion, and combined pair separately.
Exclude fixture creation, hashing, allocations, input reset, and CPU work.
Reuse identical buffers and synchronize only at arm boundaries.

For every card and every timing family:

- 20 untimed 47-layer cycles per arm;
- 31 A-B-B-A blocks;
- 64 complete 47-call cycles per arm in each block; and
- a changing fixture rotation outside the timed arm.

Each individual candidate must win at least 24/31 paired blocks and have a
strictly positive median saving on every card. The combined candidate must:

- win at least 28/31 paired blocks on every card;
- save at least `0.15 ms` per 47-layer cycle on every card;
- reduce exactly 94 device launches per cycle; and
- pass the full post-timing raw-exact replay on every card.

Do not average away a failing card. If the combined threshold fails, preserve
the exact component result and stop before any endpoint.

## Endpoint boundary

No endpoint treatment is frozen by this note. If and only if all four
component gates pass, write a separate endpoint preregistration before
starting a service. That note must decide in advance whether the elementwise
bundle is tested alone or stacked with already component-proven exact
micro-optimizations. Any stack must use new cold services, the fixed 13-prompt
suite, the canonical q=1 teacher, cache-zero proof, and a sequential early-stop
A-B-B-A design. No result from the projection-merge screen is eligible for an
endpoint or LocalMaxxing submission.
