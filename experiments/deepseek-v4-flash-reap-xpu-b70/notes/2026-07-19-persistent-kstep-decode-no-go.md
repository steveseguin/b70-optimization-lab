# Persistent K-step nonspec decode: exact NO-GO

## Result

**NO-GO for the fixed-geometry decoder build.** K=8 and K=16 are bitwise
exact but recover only `0.159355` and `0.195881 ms/token`, respectively,
versus the established `22.881408 ms/token` baseline. The same-prompt K=0
control is `22.676825 ms/token`; K=16 is effectively identical at
`22.685527 ms/token`.

| K | Exact IDs | Median ms/token | Implied tok/s | Recovered vs 22.881408 |
|---:|---:|---:|---:|---:|
| 1 | 804/804 | 23.761811 | 42.0843 | -0.880403 ms |
| 2 | 804/804 | 23.123389 | 43.2463 | -0.241981 ms |
| 4 | 804/804 | 23.002078 | 43.4743 | -0.120670 ms |
| 8 | 804/804 | 22.722053 | 44.0101 | +0.159355 ms |
| 16 | 804/804 | 22.685527 | 44.0810 | +0.195881 ms |

The observed asymptote is about `22.69 ms/token` (`44.08 tok/s`). Against
the same-suite K=0 control, K=16 is `0.008702 ms/token` slower. This is below
the `<0.5 ms` NO-GO threshold by either comparison.

## Identity

- model: `/mnt/fast-ai/llm-models/deepseek-v4-flash-xpu/current-k160`,
  revision `7c360e1cd4a5168099dbc54d16d929bf6df04990`;
- canonical oracle: vLLM `a681dbb2b4b19c2c5a964817095b5f8c1f27ff48`;
- timed candidate: vLLM `e9fbf7b2fca4d913f9ff6fbd20c2b6160d2d03ff`,
  based on the oracle commit;
- final guarded branch head:
  `5a180e5be8306c09dc92890b4e7907a081c26ebc`. The final commit only removes
  an unused rejected argmax method and does not change the timed path;
- XPU kernels: `6522849b02894273b1e779b3c115527b5cdf3756`;
- oneCCL: `48fda4f0e074db005596d6899d5227d3f0316c12`, wide-epoch runtime at
  `/mnt/fast-ai/runtime/oneccl-2021.17.2-b70-wideepoch-48fda4f/lib`;
- exact nonspec M=1 flags from the roofline baseline, including PIECEWISE
  graph, native MHC, router norm, direct routed MoE, qnorm/RoPE/KV insert,
  W8A16, TP4/EP4, FP8 KV, prefix caching off, and all rejected DSpark/M8
  flags pinned to zero;
- `CCL_ENABLE_SYCL_KERNELS` remained at the baseline default;
- no speculation and no LocalMaxxing action.

## Exactness gate

For each K in `{1,2,4,8,16}`:

- 10/10 unique cold prompts matched the K=0 oracle;
- 804/804 returned token IDs matched bitwise;
- all requests reported `cached_tokens=0`;
- the five timing prompts each returned 128/128 matching IDs, for 640/640;
- the separate exactness suite contributed 164/164 matching IDs and included
  short EOS cases, exact copy, JSON, arithmetic, and a designated 128-token
  rollover list;
- token positions 28 and 58 matched in every 128-token request;
- EOS inside a chain was safely host-trimmed to the canonical first EOS;
- no successful run showed a oneCCL epoch rollover mismatch or hang.

The original six exact canaries also matched 28/28 at K=1 after the KV fix.

## Timing method

The final timing suite has five unique prompts which each force a 128-token
response. Each prompt ran once per service, with prefix caching disabled and
`cached_tokens=0`. Per-row steady time is:

```text
1000 * post_ttft_s / (completion_tokens - 1)
```

The table reports the median across the five rows. This endpoint wall metric
is used because a K-step response can stream several token IDs at one host
timestamp, making individual stream-chunk timestamps unsuitable as device
token timings. The K=0 control and every K candidate used the same prompts,
seed, model, runtime flags, and 128-token bound.

## What was implemented

`VLLM_XPU_PERSISTENT_KSTEP_DECODE` is default-off and accepts only
`0,1,2,4,8,16`. The scheduler fails closed unless it sees one eligible greedy
nonspec request with no penalties, logprobs, grammar, LoRA, encoder input,
sampling constraints, or speculative tokens. It reserves K-1 lookahead KV
slots and advances the logical request by K.

Within one EngineCore/worker turn, the runner replays the canonical fixed-M=1
decode graph K times. Token selection reuses the existing exact TP-sharded
LM-head top-1 path; the chosen device token feeds the next fixed input buffer.
Device position, sequence length, computed-token count, slot mapping, and
attention metadata advance between inner steps. Only the K selected IDs return
to EngineCore. The canonical graph remains the owner of KV writes.

Important boundary: this is one framework transaction, not one literal Level
Zero submission. `BreakableCUDAGraphCapture.replay()` still loops over graph
and eager segments in Python for every inner token, while compact TP argmax
still invokes a host-scheduled oneCCL pair all-gather. The current breakable
graph implementation cannot nest another capture, and its sparse-attention
breaks prevent wrapping the whole K loop in a single recorded graph.

## Where the residual gap remains

Moving K tokens inside one EngineCore/worker turn did not materially change
steady decode time. Therefore the `3.435 ms/token` profile interval is not a
removable EngineCore/API scheduler turn of that size. Most of it remains in
worker-side per-token work between device compute regions:

1. Python iteration over breakable graph and eager segments;
2. separate Level Zero graph/eager submissions and their synchronization;
3. attention/KV metadata producers which remain eager per token;
4. the compact sharded-argmax oneCCL collective and dispatch.

The removable outer EngineCore portion is at most about `0.2 ms/token` in this
experiment and is indistinguishable from same-suite run variance. The profile
bucket should be renamed from an EngineCore scheduler gap to a worker replay /
submission / synchronization gap until a device-event trace separates those
components.

## Failed paths preserved

- `persistent-kstep-k1-20260719` and
  `persistent-kstep-k1-sycl-20260719`: graph recording rejected compact
  oneCCL all-gather, including forced SYCL/topo mode;
- `persistent-kstep-k1-reduce-20260719`: eligibility gate initially rejected
  inactive built-in logits processors;
- `persistent-kstep-k1-firstdecode-20260719`: confirmed that built-in gate;
- `persistent-kstep-k1-live-20260719`: MAX/MIN reduction experiment returned
  invalid `-4` IDs under graph replay;
- `persistent-kstep-k1-exactidentity-20260719`: a second raw-model graph
  captured dummy KV slot metadata and produced premature EOS. The fix was to
  retain canonical graph ownership of attention metadata and KV writes;
- `persistent-kstep-k16-timing-20260719`: one startup-only Level Zero
  `UR_RESULT_ERROR_DEVICE_LOST` after five consecutive model reloads. No
  request ran. GPUs were idle and discoverable; the clean retry succeeded and
  passed 640/640 IDs with all five timing rows valid.

Git history on the candidate branch and the listed raw artifact directories
preserve the rejected implementations and logs.

## Evidence

- structured summary:
  `experiments/deepseek-v4-flash-reap-xpu-b70/data/persistent-kstep-go-no-go-20260719.json`;
- exactness suite:
  `experiments/deepseek-v4-flash-reap-xpu-b70/quality/persistent-kstep-exactness-v1.json`;
- timing suite:
  `experiments/deepseek-v4-flash-reap-xpu-b70/quality/persistent-kstep-timing-v1.json`;
- launcher:
  `experiments/deepseek-v4-flash-reap-xpu-b70/scripts/serve-k160-persistent-kstep.sh`;
- final vLLM patch snapshot:
  `experiments/deepseek-v4-flash-reap-xpu-b70/patches/deepseek-v4-persistent-kstep-a681-to-5a180e5.patch`;
- K=0 timing oracle:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/persistent-kstep-k0-timing-20260719/timing.json`;
- K=1/2/4/8 timing:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/persistent-kstep-k{1,2,4,8}-timing-20260719/timing.json`;
- K=16 timing retry:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/persistent-kstep-k16-timing-retry-20260719/timing.json`;
- exactness matrix:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/persistent-kstep-k{1,2,4,8,16}-final-20260719/persistent-exactness-final.json`;
- established profile:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/nospec-m1-roofline-profile-20260719T140812Z`.

## Recommendation

Do not greenlight the full fixed-geometry decoder build. The only defensible
next Option 4 increment is a bounded native K=2 proof which demonstrates, with
Level Zero submit counters and device events, one command-list submission for
the entire two-token chain and a graph-capable sharded argmax/metadata path.
If that cannot remove at least `0.5 ms/token`, close Option 4 and return effort
to the measured device execute buckets rather than the EngineCore loop.
