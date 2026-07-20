# K160 EAGLE bounded single-card signal run

Date: 2026-07-20

Verdict: **MARGINAL -- not a GO for full off-host training from this run**

## Numbers first

- Training completed normally at the preregistered bound: **73,977 optimizer
  steps**, **591,816 anchors**, **59.9995% of one 986,368-anchor epoch**, and
  **11,910.65 seconds / 3:18:30.65** optimizer-loop wall. This excludes
  initial model/data-identity loading and final checkpoint/config persistence.
- The best checkpoint is the final checkpoint. Complete-DEV conditional
  acceptance is P1-P7 = **56.8963%, 52.7396%, 59.3313%, 68.8536%, 72.9250%,
  74.2317%, 73.6891%**.
- Best mean conditional P2-P7 is **66.9617%**. This is **3.0383 percentage
  points below** the approximately 70% Markov ceiling and **8.0383 points
  below** the strict 75% signal gate.
- Best overall draft-token acceptance is **19.6329%** and the corresponding
  emitted-token estimate is **2.3743 tokens/cycle**. P1 is 56.8963%. The hard
  milestone gates of P1 >=76%, mean P2-P7 >75%, and overall >=40% all fail.
- The late mean-P2-P7 curve is directionally strong, although its slope slows
  in the final short interval:
  **53.7573% -> 62.2274% -> 66.6147% -> 66.9617%** at 432K, 504K, 576K,
  and 591.816K anchors. It does not cross the existing ceiling, and the final
  15.816K anchors add only 0.3470 point.
- Loss is noisy at effective batch 8 but trends down. Mean loss is **4.5228**
  in steps 1-9K, **2.5622** in steps 54,001-63K, **2.8579** in steps
  63,001-72K, and **2.5907** in the final 1,977 steps. The first-1K mean is
  **8.3078**, the last-1K mean is **2.4563**, and the final-step loss is
  **3.8400**.
- Best checkpoint:
  `/media/steve/CorsairExternal/llm-optimization-artifacts/deepseek-v4-eagle-signal-20260719T210100Z/training/single-card-signal-20260720T181607Z/train-bf16-b8-ga1/head-best-mean-p2-p7.pt`
- Best-checkpoint SHA-256:
  `ef74bdbf55aa5bdc49f801a0b88be865f15860c8d7a6927c99be70c8f61f2dec`.

## Acceptance versus progress

Every row is a recursive greedy rollout over the full disjoint non-frozen DEV
capture: 49,142 eligible anchors, `--max-anchors 0`, fixed eval batch 64. The
step-0 deterministic initialization is included as a true baseline.

| Step | Anchors seen | Optimizer-loop wall | P1 conditional | Mean conditional P2-P7 | Overall acceptance |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 0 | 0:00:00 | 0.0000% | 0.0000% | 0.0000% |
| 9,000 | 72,000 | 0:24:10.72 | 23.3588% | 30.9550% | 4.6126% |
| 18,000 | 144,000 | 0:48:21.98 | 23.8940% | 55.0269% | 6.8751% |
| 27,000 | 216,000 | 1:12:31.35 | 31.7346% | 34.0699% | 6.7359% |
| 36,000 | 288,000 | 1:36:42.20 | 38.0204% | 49.3493% | 9.4731% |
| 45,000 | 360,000 | 2:00:51.69 | 43.1606% | 51.5630% | 10.7159% |
| 54,000 | 432,000 | 2:24:58.82 | 46.4369% | 53.7573% | 12.2764% |
| 63,000 | 504,000 | 2:49:06.79 | 51.7500% | 62.2274% | 16.3125% |
| 72,000 | 576,000 | 3:13:13.24 | 56.4751% | 66.6147% | 19.5899% |
| 73,977 | 591,816 | 3:18:30.65 | **56.8963%** | **66.9617%** | **19.6329%** |

The curve is not monotonic early: mean P2-P7 rises to 55.0269% at 144K
anchors, falls to 34.0699% at 216K, and then rises at every remaining
checkpoint. P1 rises at every checkpoint after 144K. Overall has one small
early reversal and then rises through the final checkpoint.

## Signal interpretation

This is not the flat/declining curve that would justify a **STRUGGLES** label.
The architecture learns conditional depth, and four later conditional
positions finish near or above 69%; P5-P7 finish at 72.9250%, 74.2317%, and
73.6891%. However, the requested headline is the unweighted mean of P2-P7,
and it reaches only 66.9617%. P2/P3 remain weak at 52.7396%/59.3313%, P1 is
only 56.8963%, and overall is only 19.6329%.

The deciding evidence for **MARGINAL** is therefore:

1. positive: mean P2-P7 improves from 0% at initialization to 66.9617%, with
   a clear 53.7573% -> 62.2274% -> 66.6147% late rise;
2. negative: it never exceeds the approximately 70% Markov ceiling or reaches
   the 75% gate;
3. negative: the last short interval improves mean P2-P7 by only 0.3470 point,
   while all three hard milestone metrics still fail by large margins.

This bounded local run alone is **not a GO signal for a full off-host training
run**. It is useful evidence that the head is not entirely failing, but more
training would be a follow-up experiment rather than execution of a passed
investment gate.

## Config and runtime

- physical B70 1, exposed by `ZE_AFFINITY_MASK=1` as logical `xpu:0`;
- direct single process, world size 1, no initialized process group, no DDP,
  no torchrun, no oneCCL preload, and no `CCL_*` environment;
- eager execution; BF16 XPU autocast with FP32 trainable parameters and AdamW
  state; recursive non-reentrant activation checkpointing;
- microbatch 8, gradient accumulation 1, effective batch 8 anchors/update;
- AdamW `(0.9, 0.95)`, LR `2e-4`, 3% warmup, cosine decay to 10%, weight decay
  0.05, global gradient clip 1.0, seed 160719;
- 60-second per-step watchdog plus an operator-set 12,600-second outer process
  guard;
- checkpoints every 9,000 steps, observed about 24.18 minutes apart;
- unchanged 94,654,464-parameter head: width 2048, 16Q/4KV GQA, head dimension
  128, SwiGLU 5504, context 128, recursive M=7, feature boundaries `[4,22,43]`;
- committed trainer SHA-256:
  `cd5629aef89940a3c85ef57160e4840249db4bbe11da334254bb1f5f02b7cc6a`.

The run deliberately used the literally confirmed batch-8/accumulation-1
single-card configuration. This differs from the design document's aspirational
8,192 anchors/update and makes individual optimizer-step losses noisy. It does
not change the exact anchors-seen accounting or full-DEV acceptance results.

## Artifacts and safety

Artifact root:

`/media/steve/CorsairExternal/llm-optimization-artifacts/deepseek-v4-eagle-signal-20260719T210100Z/training/single-card-signal-20260720T181607Z`

Important files:

- `train-bf16-b8-ga1/training-metrics.jsonl`, SHA-256
  `952288ebe4486b4f30c04b8fe67efeb7989242b6e99c427dc133c2a613443f63`;
- `train-bf16-b8-ga1/events.jsonl`, SHA-256
  `9ed202044f02e193a870d9f6bf522f6b2a1b1ff28d77b8c3309ef5d3b26bb7d6`;
- `evaluations/eval-step-000000.json` through
  `evaluations/eval-step-073977.json`;
- structured repository summary:
  `data/deepseek-v4-flash-k160-eagle-single-card-signal-20260720/summary.json`.

No K160 transformer or vLLM service was loaded. The committed trainer read
only the frozen K160 embedding and LM-head tensors required by the head. No
feature recapture occurred. No frozen held-out pack was opened, listed,
modified, hashed, or evaluated. No serving integration or LocalMaxxing action
was performed. Operational checks observed one active GPU process at a time,
and physical B70 1 was free again after evaluation.
