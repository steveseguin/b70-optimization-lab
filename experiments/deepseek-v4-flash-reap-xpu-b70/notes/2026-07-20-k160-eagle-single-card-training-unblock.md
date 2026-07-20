# K160 EAGLE single-card training unblock: kernels work, throughput rejects local training

Date: 2026-07-20

Verdict: **NOT-VIABLE**

Recommendation: **go off-host to H100/A100-class training on the preserved corpus**

## Numbers first

- Original four-rank hang host site: commit `f9fbce594`,
  `train-k160-eagle-signal-head.py:587`, at
  `POSITION_WEIGHTS.to(state.device)` immediately after the initial P1
  `model.decode(...)`, before the seven-position loss loop. No P2-P7 recursive
  step, backward, or gradient collective had started.
- One-card BF16 trace: PASS, 1/1 complete optimizer update. Every synchronized
  initial P1 subregion, recursive P2-P7 region, conditional loss, backward,
  gradient clip, and optimizer step completed.
- Runtime topology: physical B70 card 1 (card 0 had desktop processes), logical
  `xpu:0`, world size 1, `torch.distributed.is_initialized() == false`, no DDP
  wrapper, no oneCCL preload, eager execution, recursive activation
  checkpointing, 60-second step watchdog.
- Batch-1 audited traced update: `2.32373261 s`, `0.43034211 steps/s`;
  `169/169` synchronized trace regions ended and the event log contains 341
  records.
- Batch-8 steady update time after first-step warm-up: mean
  `0.16311002 s`, median `0.16342258 s`; mean `6.13083129 steps/s`, median
  `6.11910528 steps/s`; mean `49.04665029 anchors/s`, median
  `48.95284225 anchors/s`.
- One pass over the `986,368` eligible train anchors projects to
  `5.59 h` by the steady mean (`5.60 h` by median).
- The original 500-update recipe presents `4,096,000` anchors. At the measured
  batch-8 rate it projects to `23.20 h` by the steady mean (`23.24 h` by
  median), not less than the approximately two-hour viability limit.
- Milestone training: not run. DEV P1-P7 conditional acceptance and overall:
  not evaluated. Gate: **NOT EVALUABLE**, with no fabricated acceptance
  values.

## What the old hang was and was not

The original session reported that the repeated four-rank py-spy samples all
stopped at the same host call in the first `teacher_forced_loss`: the small
position-weight tensor transfer immediately after the initial P1 decode. That
is the exact observable host stall site. The samples were not separately saved
as an artifact, and the old run had no explicit XPU synchronizations, so it is
not possible to honestly name one underlying queued P1 kernel from those
samples. It was not a P2-P7 recursive step and it was not a gradient all-reduce
because the loss loop and backward had not begun. The source observation is in
the local session at
`/home/steve/.codex/sessions/2026/07/19/rollout-2026-07-19T16-44-07-019f7c1f-3381-73e3-ad1b-9fa8bde6198e.jsonl`.

The new synchronized one-card trace completed, in order, all three feature
norms, feature fusion, token embedding/projection, input fusion, attention
norm, Q/K/V projections, RoPE, KV repeat, SDPA, output projection, SwiGLU MLP,
feature adapter, output norm, full-vocabulary LM-head projection, CE and
feature regularizer for P1, and the same recursive path for P2-P7. Backward,
gradient clipping, and AdamW also completed. The local kernel stack is
therefore functional without the old four-rank DDP/XCCL configuration; the
blocker changes from a hard hang to insufficient single-card data throughput.

The direct single-process invocation scrubbed all torchrun rank and master
variables and asserted world size 1, no initialized process group, and no DDP
wrapper. The trainer contains no `torch.compile` or graph-capture path, so this
was eager execution. oneCCL was neither preloaded nor configured.

## Config and evidence

Both probes used the committed one-layer dense GQA head unchanged: width 2048,
16 query heads, 4 KV heads, head dimension 128, SwiGLU width 5504, context 128,
recursive M=7, and 94,654,464 trainable parameters. Training used BF16 XPU
autocast with FP32 parameters/AdamW state, microbatch 1 then 8, gradient
accumulation 1, recursive non-reentrant activation checkpointing, a
60-second per-step hard watchdog, and an outer process kill guard. FP32 was
not attempted because BF16 did not stall; the measured throughput had already
failed the time gate.

Artifact root:

`/media/steve/CorsairExternal/llm-optimization-artifacts/deepseek-v4-eagle-signal-20260719T210100Z/training/single-card-unblock-20260720T132945Z`

The audited batch-1 trace checkpoint is diagnostic-only:

- path: `bf16-trace-b1-audited/head-final.pt`;
- SHA-256: `32ef4d7459b74739ceaeee7266380c619280e9d33af95ecdf53f907f6c31c06f`;
- raw event log: `bf16-trace-b1-audited/events.jsonl`;
- event-log SHA-256:
  `887100a8c26e4ce63bddbab5aa0bf1175645f00a375b439689bd4a63eb20b898`.

The batch-8 five-step throughput checkpoint is also diagnostic-only and must
not be evaluated or promoted as a trained head:

- path: `bf16-throughput-b8-audited/head-final.pt`;
- SHA-256: `7dac3d51fbc61e6df47b816324ee18f3024a4ee2e61629b91a973101ba569661`;
- metrics: `bf16-throughput-b8-audited/training-metrics.jsonl`;
- metrics SHA-256:
  `99c22f2320f892a9cc73819bfd4f419d63e3b175e80a41d22579eedbede792ad`;
- raw event log: `bf16-throughput-b8-audited/events.jsonl`;
- event-log SHA-256:
  `b567b815c470ee14720a31beaff32f934670f10c8ac9a54625027bf5a1a0de58`.

Structured summary:
`data/deepseek-v4-flash-k160-eagle-single-card-training-unblock-20260720/summary.json`.
The tested trainer SHA-256 is
`cd5629aef89940a3c85ef57160e4840249db4bbe11da334254bb1f5f02b7cc6a`.

## Decision

Stop local training. Off-host H100/A100-class training using the preserved,
checksummed train and disjoint DEV corpus is the required path. Do not recapture
features and do not load K160 for this handoff. A milestone-trained checkpoint
must exist before running the DEV conditional P1-P7 and overall acceptance
gate.

No K160 model or vLLM service was loaded, no frozen held-out pack was opened or
modified, no LocalMaxxing submission was made, and card 1 was free again after
the probes. Total measured optimizer-step wall time across the initial and
audited probes was about 10.50 seconds; total probe process wall stayed below
five minutes, well inside the 25-minute GPU-work cap.
