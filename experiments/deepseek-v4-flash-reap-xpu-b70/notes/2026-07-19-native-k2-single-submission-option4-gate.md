# Native K=2 single-submission Option 4 gate

Date: 2026-07-19

## Result first

**CONTINUE Option 4, but only as a warm-captured fixed-geometry design.** The
bounded native K=2 proof measured `21.751225 ms/token` (`45.9744 tok/s`) on the
same five-prompt timing metric used by the prior K-step gate. That recovers
`0.925600 ms/token` from the same-suite K=0 control at `22.676825 ms/token`, or
`1.130183 ms/token` from the established `22.881408 ms/token` baseline. It
clears the required `0.5 ms/token` kill gate. No full decoder was built.

The built-in tokens-1-100 metric was `47.101562 tok/s` median. The gate number
above remains the prior experiment's comparable metric: median across five
unique 128-token requests of `1000 * post_ttft_s / (completion_tokens - 1)`.
All five timing outputs were bitwise exact (`640/640` token IDs) and cache-zero.

## Submission counts and the 3.435 ms residual

The current nonspec path has one literal
`zeCommandListImmediateAppendCommandListsExp` call per rank/token, but that is
not one device transaction. Each rank/token also performs 69 direct immediate
appends (45 kernel launches, 16 copies, and 8 signals), giving **70 effective
submission boundaries and 10 host synchronizations per rank/token**. Across
TP4 that is 4 literal submits, 280 effective boundaries, and 40 host syncs per
generated token.

The bounded K=2 graph replay reduces this to **0.5 literal submits, 33 effective
boundaries, and 4 host syncs per rank/token**. Across TP4 that is 2 literal
submits, 132 effective boundaries, and 16 syncs per token: reductions of 52.9%
and 60.0%, respectively. It did not reach one effective boundary because host
input/output bookkeeping remains outside the K=2 graph.

The valid graph-on PTI trace supports this bounded four-way attribution of the
established `3.435 ms/token` residual:

| Component | ms/token | Interpretation |
|---|---:|---|
| Worker segment iteration + unresolved host metadata | `2.549344` | conservative upper bound / reconciled residual; includes profiler-invisible scheduler and metadata host work |
| Level Zero submit/sync active time, excluding argmax | `0.516502` | directly measured host API active time; long device-completion waits excluded |
| Attention/KV metadata + device bookkeeping | `0.111741` | directly measured device-event lower bound |
| Host-scheduled compact argmax gather | `0.257413` | directly measured inclusive host scope |
| **Total** | **`3.435000`** | reconciles by construction |

This is deliberately not presented as four independently exact additive event
sums. The graph body is opaque, and PTI strongly distorts device waits. The
first three directly separable values are the Level Zero API active time, the
device bookkeeping events, and the argmax host scope; the `2.549344 ms` bucket
is the remaining upper bound and cannot distinguish Python iteration from
host-side metadata and scheduler time without destroying the valid graph-on
execution mode.

Instrumentation and full per-rank counters are in
`/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/native-k2-submit-proof-final-20260719T175000Z/submit-trace-summary.json`.
Profiler throughput is rejected; only its counts, host API active durations,
and device-event bookkeeping durations are used.

## Bounded implementation

The guarded patch is commit `50e6a21116a24853ccae065caeefc843435ded05`
in `/home/steve/src/deepseek-v4-vllm-native-submit-proof-20260719`.
`VLLM_XPU_NATIVE_K2_SINGLE_SUBMISSION=1` is default-off and requires fixed
`VLLM_XPU_PERSISTENT_KSTEP_DECODE=2`, nonspec greedy decoding, M=1, and the
existing graph path.

The first eligible live transaction captures two raw model steps using the
request's real fixed-address attention/KV buffers. Position, sequence length,
slot mapping, and attention metadata advancement for step two are captured on
device. The prior host-scheduled compact pair all-gather is replaced only under
the guard by a fixed TP pair bank plus graph-recordable SUM all-reduce and
device argmax. Rank-order tie behavior matches the canonical full-vocabulary
argmax.

## Exactness and mandatory warmup

The final independent oracle/candidate suite passed:

- 5/5 fresh prompts;
- 165/165 token IDs;
- all five `cached_tokens=0`;
- prime-list rollover `128/128`, crossing K=2 transactions 28 and 58;
- timing suite `640/640` token IDs.

There is an important preserved negative result. The very first live capture
compiled `_compute_slot_mapping_kernel`, `_xpu_qnorm_rope_kernel`,
`quantize_and_insert_k_kernel`, and `_bf16_mla_sparse_kernel` during capture.
That sacrificial arithmetic request matched its first two tokens, then emitted
token 0 instead of canonical EOS and continued. The next four requests were
exact, including the 128-token rollover. The final gate therefore used one
out-of-suite capture warmup before any exactness or timing prompt. A future
design must make that warmup explicit and must never serve or score the capture
request.

Artifacts:

- canonical fresh-suite oracle:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/native-k2-oracle-20260719T174500Z/exactness-oracle.json`;
- final fresh-suite candidate:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/native-k2-submit-proof-final-20260719T175000Z/exactness-candidate.json`;
- primary unprofiled timing:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/native-k2-submit-proof-20260719T173926Z/timing.json`;
- cold-capture negative result:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/native-k2-submit-proof-20260719T173926Z/exactness.json`;
- structured repository result:
  `experiments/deepseek-v4-flash-reap-xpu-b70/data/native-k2-single-submission-gate-20260719.json`.

## Ceiling and recommendation

Straight K=2 fixed-overhead amortization projects an empirical full-decoder
ceiling of `20.825625 ms/token`, or `48.0178 tok/s`. Removing the entire
established `3.435 ms/token` bucket would be the more optimistic theoretical
ceiling: `19.446408 ms/token`, or `51.4234 tok/s`. Neither is a measured result.

Recommendation: retain Option 4 as technically de-risked, but do not build the
full decoder until it is compared with the higher-value draft-acceptance lane.
If resumed, require pre-capture kernel warmup, move the remaining per-turn host
bookkeeping into the transaction, and target a literal one-replay-per-token
interface. Keep the guard default-off until cold-capture behavior and service
lifecycle are production-safe.

No LocalMaxxing submission was made and no record is claimed.
