# Real MHC capture and graph-fence closure

Date: 2026-07-15

Status: correctness root cause resolved; performance and full-suite identity
rejected. The strict record remains 40.020972 tok/s.

## Faithful real-model oracle

A default-off eager diagnostic captured one complete M=1 decode token from the
promoted path on every TP rank:

- all 87 local BF16 `[1,4096]` inputs and reduced outputs per rank;
- all 85 MHC post/pre inputs, parameters, alias metadata, and canonical outputs
  per rank;
- the final post-only input, recurrent state, and output per rank.

The fail-closed validator passes 692 tensor files totaling 571,072,236 bytes.
Its aggregate SHA-256 is
`6f8b7b9e7a1c78cc7a2005e2d92d292a80811405725dc43e190526e1be5a59eb`.
All reduced values agree across ranks, every reduction-to-MHC link is bitwise
exact, all canonical MHC outputs agree across ranks, the final recurrent link
is exact, and the metadata contains exactly the expected 42 same-layer alias
boundaries.

Evidence:
`/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/real-mhc-boundary-capture-20260715T1200Z`.

The capture implementation and explicit reverts are preserved in the vLLM
history from `aebc1b186` through `6636a973f`, then `285e4ebbb` through
`bba83e018`. The reusable validator is
`scripts/validate-real-mhc-boundary-capture.py`.

## Real-value compact-ring replay

The new TP4 replay probe consumes the exact per-rank corpus, recreates all 85
recurrent boundaries, the 42 input/output alias pairs, the ordinary initial
all-reduce, and the final post-only operation. The compact 256-thread
ring/MHC-post-pre candidate is bitwise exact in eager mode and across eight
graph replays on every rank.

The patched oneCCL library must be `LD_PRELOAD`ed, not merely opened with
`ctypes` or placed first in `LD_LIBRARY_PATH`. Otherwise PyTorch's already
loaded oneCCL instance executes the ordinary all-reduce while the replay hook
in a second library instance has null communicator state and returns status 1.
The successful library SHA-256 remains
`d7160c2419bdffcb1ad14da86382f0d5962b92abc0ae7b38a61c94e58bc92e16`.

Evidence:
`real-mhc-boundary-capture-20260715T1200Z/compact-candidate-replay-preloaded.json`.
The probe is preserved in XPU-kernel commit `748a59f`.

## The missing dependency

Graph-recorded pre/post observer copies were then inserted around every real
full-model fused boundary. The formerly corrupt sequence became exact:
`1073 -> 437 -> 1073`, followed by three more exact alternating replays. For
request 0, all 85 observed input and output boundaries plus the final post are
bitwise identical to the promoted eager corpus on every rank.

Reducing the observers to a one-BF16 post-kernel copy retained six exact
alternating changed-input requests. This isolates the previous nondeterminism:
the fused arithmetic and real values are sound, but the direct oneCCL hook did
not establish a sufficient graph-visible completion/dependency edge before
the following model consumer. A single post-kernel read repairs the ordering;
the earlier producer-side barrier did not because it was on the wrong side of
the missing edge.

Evidence:
`/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/graph-candidate-mhc-capture-20260715T1230Z`.

## Performance closure

Correctness does not rescue the implementation:

- full pre/post observers: 33.849486 tok/s median;
- minimal one-BF16 post fence: 34.708355 tok/s median, 34.469926 p10;
- promoted control: 40.020972 tok/s median, 39.608039 p10.

The minimal fixed candidate is 13.28% slower than the record. All 12 strict
suite output hashes also differ from the record over long generation, despite
the exact first real decode token and exact arithmetic canaries. It therefore
fails both performance and full-suite identity gates.

Evidence:

- `graph-candidate-mhc-capture-20260715T1230Z/full-observer-realistic-suite.json`;
- `compact-mhc-scalar-fence-20260715T1245Z/realistic-suite-v1.json`.

## Decision

Close compact collective/MHC fusion. The former full-model corruption is now
explained and repairable, but the repaired boundary has a lower end-to-end
ceiling than the tuned production oneCCL ring plus standalone MHC kernel. Do
not spend more server loads reducing this fence or retuning its workgroup.

The next nonspeculative candidate must come from a different large boundary
and clear an exact projected 0.50 ms/token gate before TP4 integration. The
promoted source and binary contents were restored; no LocalMax submission is
warranted.
