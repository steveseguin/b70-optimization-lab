# Packet 39 integration contract

This packet is a standalone candidate, not a modification to packet29 or the
coordinator's merged runtime. The unchanged packet29 registry will reject these
new fusion keys. A later integration must extend its closed registry and bind the
actual plan allocations; copying the JSON alone is insufficient.

Use `packet26.dispatch.v1` with `classes`, `gemv`, and `fusions` string maps.
G4 writes proposed keys below; the wrapper retains the native proposal separately
and removes keys rejected by offline assembly. An absent key leaves its full
unfused chain intact. Nothing in this packet changes a live default.

| Fusion key | Candidate value | Plan sites replaced | Required arithmetic |
| --- | --- | --- | --- |
| `expert-act-iq2`, `expert-act-iq3` | `p39.epilogue` | `expsgate.check`, `expsup.check`, `expsact` | Paired p28 WG32, IQ2/IQ3, K2560; two BF16 projections before activation |
| `expert-checks-iq2`, `expert-checks-iq3` | `p39.epilogue` | `expsgate.check`, `expsup.check` only; retain `expsact` | Same paired p28 WG32; fallback mutually exclusive with the activation fusion of that format |
| `down-status` | `p39.epilogue` | `expsdown.check` | p33 down.select IQ4_NL K640; no expert mixture in this kernel |
| `hc-low-act` | `p39.epilogue` | `hc.a.act`, `hc.f.act`, `final.act` | p28 dense.rows4 Q8 K10240 split4; tail follows the existing in-kernel finish |
| `shared-up-act-q6`, `shared-up-act-q8` | `p39.epilogue` | `shexpact` | p28 dense.rows4 K2560; Q6 split4, Q8 split1; gate already available |
| `attention-combine` | `p39.epilogue` | `attn.combine` | p28 Q6 K6144 split4; existing finish owns four stream stores |
| `shared-down-combine` | `p39.epilogue` | second `moe` launch and `ffn.combine` | p28 Q8 K640; expert mixture and scalar shared gate available first |
| `gdn-qkv-conv-q6`, `gdn-qkv-conv-q8` | `p39.epilogue` | `gdn.conv` | p33 segment K2560; one independent convolution/history update per QKV row |

## Ordering and observable allocations

Preserve gate/up/down/projection raw BF16 outputs and expert statuses. They are
kept for tracing and byte gates even where the ordinary next consumer disappears.
Do not alias an output with GEMV inputs, weights, another output, routes, controls,
or history. `validate()` checks address-range overlap, strides and alignment;
the allocation owner must also prove actual extents and lifetimes. In-place
residual streams and convolution history are explicit exceptions: one row owns
each affected element and no GEMV reads those allocations.

Move `shared_gate` before `shexpdown`. Move the existing ten-expert mixture
launch after the down status check and before `shexpdown`. It remains the original
parallel mixture operation, including its BF16 output. Then shared down's row
uses the original `0 + mixture * 1`, BF16 round, separately BF16-rounded shared
contribution, BF16 blended sum, and four residual combines. This avoids both a
new reduction and a cross-workgroup producer/consumer dependency. Preserve
scratch and the mixture output allocation until this consumer completes.

QKV convolution may run immediately after QKV inside the same kernel. Its alpha,
beta and z sibling projections use the same immutable layer input, not the
convolution history. Recurrence continues to depend on the convolution output.
Each history row shifts only after its four-tap sum has read the old history.

HC gate->mix, routed down->ten-expert mixture, GDN z->gated norm, norms, and QSA
preparation retain their current reductions. No norm is merged or serialized.
HC low and shared up retain the measured four-row work-group, its original local
partial array and barrier. Attention retains its separate finish launch.
The existing split4 GEMV finish uses `(p0+p1)+(p2+p3)` before the original BF16
store; a split1 result is not interchangeable.

## Control and identity gates

GEMV raw outputs/statuses remain unconditional as in packet29. Tails obey active
and existing sticky error. Routed fusion evaluates all ten routes uniformly;
any invalid route suppresses every activation store. The checks-only fallback sets failure from each invalid slot's row zero and keeps activation as a later launch; it needs no global vote. A device atomic compare/
exchange changes sticky zero to one only. It cannot erase a previous nonzero
error and avoids competing ordinary same-address stores. No floating reduction
is added; the route test is a subgroup vote.

The original ng activation, mixture and convolution kernels also validate signed
position against context capacity. Their fused tails perform that same check.
The original status and simple residual-combine kernels do not have a position
check, so those tails do not invent one. Pass the live capacity and position.

The CPU real-model overlay tests scalar epilogues at the actual plan sites using
packet29's host GEMV backend; it does not execute the device lane bodies. Native
lane/finish instantiations need K0 then G4, and any later full-model device run
needs the unchanged v2 layer/token oracle. Nonfinite GEMV arithmetic remains
unqualified under packet29's policy; exact diagnostic failures are retained,
never treated as NaN equality. The native test additionally requires byte equality
for its nonfinite fixture and will fail if the device results differ.

## Rebuilding without device contact

Run every preparation command with `nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2`
and use `python -B`. From this directory, generate_baseline.py reproduces the
unchanged source-extracted baseline bodies; cpu_gates.py builds/runs only host
fixtures; build_native.py compiles timing.cpp and k0.cpp without running either;
offline.py compiles their extracted SPIR-V with ocloc; analyze.py reads the final
GEN/ELF text. host_gate.py builds/executes only an ELF checked to have no accelerator
library dependency. All writes and generated artifacts stay in this packet.

Keep compile and link precision flags from the build receipts. Do not use fast
math, reassociation, contracted multiply/add, compressed KV, or another reduction
tree to improve a result. Honor the two-compiler/four-CPU-process budget and the
inherited CPU affinity. Source imports from packets28/29/33 stay read-only.

From the repository root, native preparation is reproducible without running a
device binary (run sequentially):

```sh
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet39-epilogues/generate_baseline.py
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet39-epilogues/build_native.py --source timing.cpp --output p39-timing
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet39-epilogues/build_native.py --source k0.cpp --output p39-k0
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet39-epilogues/offline.py
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet39-epilogues/analyze.py
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python -B experiments/own-xpu-runtime/stage2/packet39-epilogues/assembly_gate.py
```

A fresh preparation also runs `cpu_gates.py`, `math_gate.py`, `test_window.py`,
`host_gate.py --build-only` then `host_gate.py` (host CPU only; about 34 minutes
here), `retain_assembly.py`, independent source/assembly review, then `seal.py`.
The host build needs packet29's read-only host objects and original local model
inputs, whose paths/hashes are in `host-build-receipt.json` and `real-eight.json`.
Those local dependencies are intentionally not advertised as a public recipe.
Do not merely reseal after changing sources: rerun the affected gates and reviews.
