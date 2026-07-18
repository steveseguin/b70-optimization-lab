# Fixed M=8 Target Builder Closure

Date: **2026-07-18**

Status: **bitwise exact; graph performance rejected before model load**

## Outcome

A guarded fixed-geometry Triton transaction now builds the one-request target
M=8 inputs in one command. It writes positions, sequence length, query start,
bonus plus seven draft token IDs, logits indices, gathered per-group block
tables, and per-group slot mappings into the same persistent buffers used by
the target graph.

All four B70s pass **16 changing eager schedules and 70 fixed-address graph
replays** bit-for-bit against the production four-kernel sequence. The corpus
changes token IDs and positions, explicitly including 28, 58, 127, 255, 511,
and 1023.

The eager command boundary improves substantially:

- production control: 194.3145 us at the slowest rank;
- fixed builder: 85.4355 us;
- eager saving: **108.879 us/cycle**.

That is submission removal, not decoder work removal. Once both paths are
captured, the control is already 33.974 us and the candidate is 33.718 us. The
surviving saving is only **0.256 us/cycle**, far below the 2 ms architectural
gate and even the 0.50 ms portfolio gate.

## Evidence and identity

- vLLM experiment commit:
  `ec7d27e0c61141494f1f57e90bb9ff7b64930ed2`;
- flag: `VLLM_XPU_DSPARK_FIXED_M8_TARGET_BUILDER=1`;
- gate: `../scripts/bench-fixed-m8-target-builder.py`;
- four-card result:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/fixed-m8-target-builder-gate-20260718TpoststopZ/summary.json`.

The candidate is fail-closed behind fixed M7 target inputs, one active request,
eight logits, seven drafts, and CP1. It remains default-off. No model was
loaded, no strict suite was run, and no LocalMaxxing submission was made.

## Decision

Do not integrate the builder by itself. It confirms that the measured
approximately 4.19 ms inter-cycle preparation span is not the sum of these
device kernels: the ordinary target command graph has already amortized them.
The remaining opportunity is architectural—keep accept/commit and next-cycle
state device-resident and bypass the scheduler/framework turn—or delete the
Markov full-vocabulary collective/device work with a native sharded M7
transaction. Proceed to the ordinary Level Zero IPC-event transport gate; do
not attempt another submission-only target-input fusion.

