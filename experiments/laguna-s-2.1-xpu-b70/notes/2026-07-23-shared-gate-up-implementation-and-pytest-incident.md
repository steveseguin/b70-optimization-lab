# Laguna shared gate+up implementation seal and pytest incident

Date: 2026-07-23 America/Toronto

Status: source implementation is committed and independently audited. Device
correctness remains unproved. Three unpacketized primitive-test executions are
quarantined and cannot be used as evidence.

## Sealed implementation

The separate native-M8 shared gate+up treatment is committed in the vLLM
experiment tree as:

```text
144f77608b6596677a9f6653b63b315e573b38b6
xpu: select separate Laguna M8 shared gate and up MMs
```

The tracked patch snapshot is:

```text
patches/vllm-xpu-laguna-shared-gate-up-m8-mm-20260723.patch
sha256 2f2bc91425f41d8244ef8d1d419e7f5fb735b3f73b9448f4501d56cd65c14c90
```

No XPU-kernel source or binary changed. The kernel tree remains
`c59aaadbbfd350c2b5f4ad663e247c2811ae3181`.

The implementation adds the default-off
`VLLM_XPU_LAGUNA_M8_SHARED_GATE_UP_MM` selector and preserves two independent
projections in gate-then-up order. It does not merge, concatenate, fuse,
pack, reorder, or overlap them. The guarded candidate uses one native
`torch.mm` for shared gate and one native `torch.mm` for shared up.

The model and primitive contracts now require:

- the new selector to be raw literal `1`;
- standalone gate and shared-down selectors to be raw literal `0`;
- the frozen exact eager record stack, including DFlash depth 7,
  TP4/EP4/DP1/PP1, one sequence, shared elementwise, QKNorm/RoPE,
  route-interleaved W1/W2, and literal W1 N64;
- canonical target layers 1 through 47 only;
- separate role-bound gate and up prefixes;
- one shared weak pair object proving that both projection markers, scopes,
  exact-target markers, weights, layouts, devices, and biases remain valid
  before either native MM may launch; and
- runtime revalidation of every dynamic record selector before dispatch.

A genuinely unmarked M8 projection retains incumbent BMM. A projection that
was bound as part of the pair but later loses its marker retains its pair
scope, enters validation, and raises. M1 through M7, prefill, draft, dense,
routed, shared-down, and other unmarked paths retain the incumbent.

Two read-only subagent audits initially found literal-selector, runtime-stack,
pair-integrity, and false-reference gaps. Those gaps were fixed. The final
audits found no remaining implementation blocker. One nonblocking performance
caveat remains: the production path deliberately performs strong Python-side
runtime and pair validation on every candidate projection. Component timing
of direct primitives will not include that overhead, so only a later frozen
endpoint can decide whether the end-to-end lane wins.

## CPU-only validation

The corrected construction command explicitly disables device tests:

```text
PYTHONDONTWRITEBYTECODE=1
VLLM_XPU_RUN_DEVICE_TESTS=0
python -m pytest -q
  tests/models/test_laguna_shared_gate_mm.py
  tests/models/test_laguna_shared_down_mm.py
```

Result:

```text
145 passed, 3 skipped, 14 warnings
```

The three skipped tests are XPU primitive tests. Their decorators now
short-circuit before `torch.xpu.is_available()` unless
`VLLM_XPU_RUN_DEVICE_TESTS=1` is explicitly supplied. Ruff, whitespace, and
staged-diff checks passed.

The CPU suite proves environment/AOT identity, selector literalness, record
stack drift rejection, constructor scope, pair lifecycle while live, role
binding, current/peer corruption rejection before GEMM, prefill and unmarked
fallback, and actual `LagunaMLP` gate -> up -> down call order. It does not
prove XPU arithmetic.

## Unpacketized XPU pytest incident

Before the explicit opt-in guard was added, two intended CPU-only pytest
commands ran three small XPU tests because this development host reports XPU
available:

- standalone shared-gate primitive dispatch;
- new shared gate+up primitive dispatch; and
- shared-down primitive dispatch.

The commands allocated small BF16 XPU tensors and launched primitive GEMMs.
No model was loaded, no generation or endpoint ran, no timing/counter loop
ran, no performance value was recorded, and no LocalMaxxing action occurred.
Nevertheless, this violated the original gate+up preregistration's required
ordering: Stage-0 tooling and its tracked authorization packet were supposed
to be sealed before any new XPU tensor-bearing command.

The affected results are quarantined. In particular, the then-current
gate+up test compared native MM with native MM and was not an incumbent-BMM
exactness proof. It influenced no threshold, treatment, or promotion choice.
The corrected opt-in XPU test now constructs a literal stride-zero BMM
reference, but it has not been executed and is not evidence.

The detailed local mistake entry is:

```text
/home/steve/identified-mistakes/2026-07-23-laguna-unpacketized-xpu-pytest.md
```

The original preregistration remains the source of the treatment and frozen
thresholds, but it is no longer sufficient execution authority. A separate
post-incident reaffirmation preserves those rules unchanged and requires a
fresh independently audited Stage-0 packet before any further XPU command.
