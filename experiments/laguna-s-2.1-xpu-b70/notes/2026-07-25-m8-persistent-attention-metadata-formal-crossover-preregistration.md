# Laguna M8 persistent-attention metadata formal crossover preregistration

Date registered: 2026-07-25 America/Toronto

## Claim

This is one uninstrumented, cold, graph-versus-graph A-B-B-A crossover for the
default-off persistent exact-attention metadata candidate. It may establish a
new four-B70 LocalMaxxing record only if the complete preregistered analyzer
emits `record_candidate`.

The diagnostic that authorizes this formal campaign is sealed at:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-persistent-attn-metadata-dd1619dca-ef334233d-20260725T013440Z
```

It was bitwise exact and cache-zero and reduced median whole M8 replay time by
`1.8844%`; its full 272-token diagnostic graph call improved by `0.4525%`.
None of those diagnostic timings is benchmark or submission evidence.

## Frozen treatment and order

All four legs use the exact approved Breakable PIECEWISE graph runtime. The
only treatment difference is:

```text
A control: VLLM_XPU_LAGUNA_M8_PREBUILT_EXACT_ATTN_METADATA=0
B candidate: VLLM_XPU_LAGUNA_M8_PREBUILT_EXACT_ATTN_METADATA=1
```

Every leg must set:

```text
VLLM_XPU_LAGUNA_M8_BREAKABLE_GRAPH=1
VLLM_USE_BREAKABLE_CUDAGRAPH=1
XPU_GRAPH=1
VLLM_XPU_ENABLE_XPU_GRAPH=1
VLLM_XPU_LAGUNA_M8_CAPTURE_ATTENTION_GRAPHS=0
```

The fixed order is:

```text
A1 graph metadata off
B1 graph metadata on
B2 graph metadata on
A2 graph metadata off
```

After A1 and B1, the phase-1 analyzer runs once. Failure permanently stops the
campaign. Only a phase-1 pass authorizes B2 and A2. Once B2 runs, A2 must run
regardless of B2 performance. No rescue, replacement, fifth leg, repeated leg,
or result-conditioned retry is permitted.

## Frozen source

- vLLM candidate:
  `ef334233deabeaeedb607056a2db1c90edb3887c`;
- XPU kernels:
  `4772f727590c51b72add79350b913d098cf67872`;
- target and draft revisions remain
  `4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb` and
  `5e07c246915c86dc6920fead03d019989224f2ba`;
- target and draft models remain on internal ext4 NVMe under `/mnt/fast-ai`.

The formal controller, leg runner, graph serve wrapper, analyzer, and tests
must be adapted and committed after this preregistration. Their exact committed
hashes become part of the controller/leg identities before A1 starts.

## Cold benchmark contract

Each leg receives:

- one fresh service process and private RPC/cache/temp roots;
- a verified 60-second four-device idle interval before startup and after
  shutdown;
- no warm-up request or generation;
- exactly one invocation of the fixed 13-prompt realistic suite;
- each prompt once in fixed order with seed 1 and `max_tokens=512`;
- `tok_s_1_100_after_ttft` as the headline metric;
- prefix caching disabled and cached tokens zero for every request;
- first lazy graph capture inside the first measured cold request;
- exactly four rank-local 146-graph/145-eager-boundary capture and replay log
  records;
- exact canonical-q1 token IDs for 13/13 prompts, including long-next and
  rollover checks.

Qualification, profiler, diagnostic, old-root, cached-history, or aggregated
replica timings are forbidden inputs.

## Paired causal gates

For both `B1-A1` and `B2-A2`, all of these must pass:

- both legs pass every identity, exactness, cache, freshness, metrics,
  topology, cleanup, and idle gate;
- candidate headline throughput improves by at least `0.25%`;
- candidate wins at least `10/13` paired prompt rows;
- median paired prompt improvement is at least `0.25%`;
- aggregate DFlash target-cycle time improves by at least `0.15 ms`;
- absolute acceptance-rate delta is at most `0.001`.

Both A controls must lie within `±2%` of the approved
`92.16352215694299 tok/s` graph record. A control outside that health band
makes the campaign inconclusive; it cannot make promotion easier.

## Promotion and submission floor

Full promotion additionally requires:

- all four starts and both combined exactness bundles pass;
- `min(B1, B2) > min(A1, A2)`;
- both B starts strictly exceed the practical floor:

```text
92.393930962335 tok/s
```

This is the approved `92.16352215694299 tok/s` record multiplied by `1.0025`.
A bare numerical record exceedance below the practical floor is classified as
exact but noise-sized and is not submittable.

If and only if the full analyzer emits `record_candidate`, construct a payload
and independently audit it. Submit only `min(B1, B2)`, never the faster start,
with all four run paths, the complete matching identity, 52/52 exact
cache-zero evidence, paired gates, and both selector values. No other result
from this campaign may be submitted.
