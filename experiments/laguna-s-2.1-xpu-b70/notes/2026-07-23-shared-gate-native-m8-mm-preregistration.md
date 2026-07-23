# Laguna shared-gate native M=8 BF16 MM preregistration

Date registered: 2026-07-23 America/Toronto

Status at registration: the single treatment, staged stopping rules, quality
requirements, timing/counter thresholds, and endpoint boundary are frozen
before source changes, XPU execution, model service startup, model generation,
payload creation, or submission.

## Decision and prior evidence

The shared-down native-M8 treatment is closed after a valid frozen-counter
failure. Its global GPU-time mean improved, but four of eight matched pairs
lost and no card passed every timing and XVE guardrail. The routed-W1 N128
treatment is also closed after an exact endpoint phase-one loss.

An independent source-only review ranked a separate shared gate projection as
the highest-upside remaining occupancy screen. The incumbent shared MLP issues
three unquantized BF16 projections per target layer:

```text
gate: [8,3072] @ [3072,256] -> [8,256]
up:   [8,3072] @ [3072,256] -> [8,256]
down: [8,256]  @ [256,3072] -> [8,3072]
```

Gate and up together cost about `4.878882 ms` per 47-layer component cycle in
the prior changing-input screen. The current exact verifier presents each as
eight independent M=1 lanes through a stride-zero BF16 BMM. A native M=8 MM
may expose more row-by-N scheduling opportunity and remove batched-M1
bookkeeping for the K-heavy, narrow-N geometry.

This arithmetic risk is not assumed safe. A prior merged gate/up N512 BMM was
bitwise exact in only 24/64 epochs, and a logical-B16 form was exact in only
18/64. The treatment therefore changes the gate projection only. It does not
merge, concatenate, pack, broadcast, fuse, or introduce any explicit custom
or merged gate/up tile. Native MM may select a different internal oneDNN JIT
geometry, which is precisely the arithmetic risk this protocol gates. Up and
down remain literal incumbents. A separate up experiment is forbidden until
this gate-only lane is completely classified and independently recorded.

## Frozen starting identity

- approved LocalMaxxing record:
  `cmrx6p5dv001bo4017hb7sixz`;
- conservative approved throughput:
  `33.89498511171744 tok/s`;
- main repository before this note:
  `b1e7be146feed723d7ffa349765033cbd5d0d55e`;
- vLLM:
  `75d4660463407975c16bd33711499ca560bf2034`;
- XPU kernels:
  `c59aaadbbfd350c2b5f4ad663e247c2811ae3181`;
- target revision:
  `4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb`;
- DFlash revision:
  `5e07c246915c86dc6920fead03d019989224f2ba`;
- checkpoint config SHA-256:
  `9f139560db8fd723a75ee4adc24a9fece4101df0e8e7f1cce6549f7eba5b14e6`;
- installed `vllm_xpu_kernels/_C.abi3.so` SHA-256:
  `126da37b23e5eff6840dd256c90164e3a282469e5fafa27830530e63ff36bce2`;
- installed `vllm_xpu_kernels/_xpu_C.abi3.so` SHA-256:
  `f5f672130cc1b1d550646f732a6d576952c49514eba7a10db60fc1c361938fd8`;
- installed `vllm_xpu_kernels/_moe_C.abi3.so` SHA-256:
  `0057b266d567731a9f9f592cefd9103bbf027ebb83c876d26c17ffb09994a3a0`;
- installed `vllm_xpu_kernels/libgrouped_gemm_xe_2.so` SHA-256:
  `fc74a6452b95643768889e2598df77bc4f4aa2b0925257a4c0eff371b1cf6c96`;
- Torch:
  `2.12.0+xpu`;
- XPU driver:
  `1.15.38308+1`;
- PTI unitrace source:
  `a5bab309f4ffdd78bd127035c46f5f75371160f8`;
- PTI unitrace binary SHA-256:
  `5aaca1f418a212a1d298cac27afb6c471bf1fcf47a1622e0c20d1a2cf43fc85a`;
- boot ID:
  `0b7f98a5-e50a-46a5-81ea-15938b55317a`; and
- approved runtime shape: eager exact target, DFlash depth 7, BF16 KV,
  TP4/EP4/DP1/PP1, one active request, literal routed-W1 N64.

The vLLM and kernel starting commits contain default-off failed candidates.
They must remain off. Their presence in source does not authorize stacking.

## Single treatment

Add one default-off selector:

```text
VLLM_XPU_LAGUNA_M8_SHARED_GATE_MM=1
```

The control remains:

```text
gate = stride-zero B=8, M=1, K=3072, N=256 BF16 BMM
```

The candidate is:

```text
gate = native M=8, K=3072, N=256 BF16 MM
```

Both arms retain separate incumbent shared up, exact shared SiLU/multiply,
incumbent shared down, routed scale/shared add, fixed-rank reduction, routed
experts, router, attention, DFlash, and all collectives. In particular:

```text
VLLM_XPU_LAGUNA_M8_SHARED_DOWN_MM=0
VLLM_XPU_LAGUNA_M8_W1_N_TILE=64
VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK=0
VLLM_XPU_LAGUNA_M8_BF16_ATTN_MM=0
VLLM_XPU_LAGUNA_DETERMINISTIC_GRAPH=0
VLLM_XPU_ENABLE_XPU_GRAPH=0
VLLM_USE_AOT_COMPILE=0
XPU_GRAPH=0
```

No native XPU-kernel source or binary change is expected: the candidate uses
the existing eager `torch.mm` primitive under a strict vLLM marker. Any
unexpected native-binary change rejects the lane.

## Fail-closed runtime scope

Only `LagunaMoE.shared_expert.gate_proj` in the exact target verifier may
receive the marker. Dispatch additionally requires:

- Intel XPU eager execution outside a compiler;
- exactly eight contiguous BF16 rows `[8,3072]`;
- `UnquantizedLinearMethod`;
- one contiguous BF16 weight `[256,3072]` on the same device;
- no bias;
- the exact approved shared-elementwise plus QKNorm/RoPE record stack;
- literal W1 N64;
- shared-down MM, BF16 attention MM, BF16 router, deterministic graph,
  auxiliary shared stream, remote zero, and fused transaction all disabled;
  and
- DFlash depth 7 with TP4/EP4/DP1/PP1 and one active request.

An enabled matching M=8 call that violates dtype, shape, layout, method,
device, bias, source-stack, or execution mode must raise rather than fall
back. M=1 decode, M=2..7 verifier tails, prefill, draft, dense MLPs, shared up,
shared down, and unmarked linears retain the exact incumbent path.

## Stage zero: one-card exactness kill screen

This note authorizes only construction, source freezing, CPU tests, and
independent review of the stage-zero tooling. Physical card 0 may run one
exactness-only kill screen only after a tracked authorization packet commits
the exact source commits, tool hashes, fixture hashes, native binaries,
runtime identity, command, output root, and all downstream-false flags. No
timing result is eligible from this stage.

Use exactly 128 deterministic changing epochs from one hash-frozen fixture
generator and ordered epoch list committed before the first XPU command. The
tooling packet must freeze the generator SHA-256 plus every expected
rank-invariant input, weight, routed-input, and reduction-input fixture hash.
Change both `[8,3072]` BF16 inputs and `[256,3072]` BF16 weights, including
finite random values,
signed-zero/subnormal patterns, large finite values, cancellation-heavy
patterns, and rank-boundary bit patterns. For every epoch require:

- raw `uint16` equality and `torch.equal` between the literal stride-zero BMM
  gate output and native-M8 MM output;
- deterministic candidate repeat;
- unchanged input and weight hashes;
- raw equality after the unchanged incumbent up projection, exact
  SiLU/multiply, incumbent down projection, shared+routed add, and simulated
  fixed-rank reduction; and
- unique fixture and output hashes rather than replay of one hot tensor.

The actual checkpoint-selected `ColumnParallelLinear.forward` must dispatch
exactly one native MM for marked M=8. Unmarked M=8 and marked M=1..7 must use
the incumbent BMM. A bad-layout marked M=8 call must raise. The screen must
also prove that shared up/down, dense MLP, draft, and prefill are unmarked.

One raw mismatch, nondeterministic repeat, mutated input, missing dispatch, or
missing rejection classifies the treatment
`stage0_exactness_failed_stop`. It forbids timing, other-card execution,
counters, endpoint work, model generation, payload creation, and submission.
There is no alternative seed or rescue corpus. The first valid tensor-bearing
stage-zero result is terminal. A pre-tensor identity or tooling failure may be
retried only in a fresh root after preserving the failed evidence, correcting
only the identified tooling defect, and independently reviewing and freezing
the corrected source in a new authorization packet.

## Four-card component gate

Only a complete stage-zero pass may authorize construction, source freezing,
CPU validation, and independent review of four-card component tooling. It
does not authorize component execution. Execution requires a later tracked
authorization packet that freezes the exact command, one new local-NVMe
campaign root, source/tool/fixture/runtime hashes, four physical mappings,
fixed arm order, and all downstream-false flags.

Each physical B70 then runs independently with one visible Level Zero device
and must repeat the 128 changing exactness epochs before timing plus a
32-epoch exact replay after timing.

Steady component timing measures only the isolated gate projection: literal
stride-zero BMM for control versus native M8 MM for candidate. Both arms use
identical preallocated inputs, 47 distinct 1.5-MiB gate weights, and distinct
preallocated output buffers. Fixture generation, fixture rotation, hashes,
allocations, copies, actual-forward dispatch proof, and every downstream
shared/routed operation remain outside the timed arms. The separate
actual-`ColumnParallelLinear.forward` proof is correctness/dispatch evidence,
not timing evidence. The timing protocol is:

- 20 untimed complete cycles per arm;
- 31 A-B-B-A blocks;
- 64 complete 47-layer cycles per arm in each block;
- a 128-MiB eviction touch before every arm; and
- synchronization only at arm boundaries.

On every card, the candidate must win at least 28/31 paired blocks and save at
least `0.15 ms` at the median 47-layer cycle. The four-card analyzer must
recompute every comparison, require four distinct UUIDs/BDFs, identical
fixture/output aggregates, frozen source and binary identities, one clean
boot, and all pre/post raw exactness. A cross-card mean cannot hide one
failing card.

Failure is `component_failed_stop_before_counters`. Hot component timing never
authorizes an endpoint.

The first valid four-card component campaign is terminal: exactly one valid
result per physical card, no performance-conditioned rerun, alternate corpus,
alternate arm order, alternate boot, fifth card leg, or rescue campaign. A
pre-tensor identity/tooling failure may be retried only in a fresh root after
preserving it and independently reviewing and hash-freezing a correction
limited to the identified tooling defect.

## Cold hardware-counter gate

Only a passing four-card component aggregate may authorize construction,
source freezing, and independent audit of dedicated counter tooling. Counter
execution requires a later hash-frozen authorization packet.

The frozen counter design has exactly four fresh arms per physical card in
the fixed order `A1, B1, B2, A2`: A is literal control and B is the sole
candidate. The two fixed matched comparisons are `B1 < A1` and `B2 < A2`;
no cross-pair rematching or extra arm is allowed. Each arm uses 128-MiB
eviction before each of 13 completion-bounded selected gate calls. Discard
selected query rows with zero-based indexes 0 and 1; analyze exactly rows
2 through 12.

Every card must satisfy all of:

- candidate GPU time lower in both matched pairs;
- aggregate candidate GPU time lower;
- GPU and load/store-cache read bytes regress by no more than 2%;
- XVE stall rises by no more than 0.5 percentage point;
- XVE active and thread occupancy each fall by no more than 0.5 point;
- result-validity, split, overrun, lost/inconsistent-report, spill, SLM,
  partial-write, and LSC-write proxies remain zero; and
- every control/candidate output remains raw exact.

The global four-card aggregate candidate GPU time must also be lower, but it
cannot override any pair or per-card failure. Counter capture is one-shot; a
tool parser defect may be repaired only against the sealed evidence under a
separate authorization, never by performance-conditioned recapture.

Failure is `counter_failed_stop_before_endpoint`.

## Endpoint and publication boundary

No stage in this note authorizes a service, model generation, an endpoint
preregistration, a payload, a record claim, or LocalMaxxing submission. A
passing counter gate would authorize only construction and independent audit
of a separate cold endpoint preregistration.

That later protocol must retain the canonical q=1 teacher, 13 fixed unique
prompts once per fresh service, complete returned-token bitwise equality,
`cached_tokens=0`, long-next and rollover canaries, no warmup/cache/history/
reuse, one active generation, fresh A-B-B-A services, fixed idle gaps, bounded
DFlash work drift, and the approved-record floor. At minimum, after A1/B1 it
must stop and forbid B2/A2 unless the candidate headline is strictly faster,
the candidate wins at least 9/13 paired prompt rows, the paired median is
positive, target-cycle time improves by at least `0.15 ms`, and absolute
acceptance-rate drift is at most `0.001`. There is no fifth or rescue leg.

All live models, caches, temporary files, build files, logs, and evidence must
remain under `/mnt/fast-ai` on internal NVMe/ext4. The external Corsair USB is
backup-only and must not be read or written. This experiment does not
authorize a reboot.
