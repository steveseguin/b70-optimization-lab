# Laguna M8 Breakable graph formal crossover preregistration

Date registered: 2026-07-24 America/Toronto

Status at registration: campaign source, exact ABBA order, phase-stop rule,
performance gates, quality gates, analyzer, and one-shot root frozen before
A1 service startup and before any generation in this campaign.

## Question and claim boundary

Does the raw-byte- and endpoint-exact Breakable M8 runtime produce a
reproducible cold single-generation decode improvement over the approved eager
stack when graph execution is the only treatment difference?

The earlier endpoint-qualification root and all its timings are explicitly
ineligible inputs. The one permitted campaign root is:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-formal-graph-crossover-d0960da7e-0ce373a31-20260724T215010Z
```

No rescue root, fifth leg, repeated leg, warmed service, or hand-selected leg
is permitted.

## Frozen source and common stack

- main tooling:
  `d0960da7eb115d6aa59c73e3975df6d5406d3f34`;
- vLLM:
  `0ce373a3115fb4498c5e7a041d4fc9212fd6b5ca`;
- XPU kernels:
  `4772f727590c51b72add79350b913d098cf67872`;
- target:
  `/mnt/fast-ai/llm-models/laguna-s-2.1/int4`,
  revision `4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb`;
- DFlash:
  `/mnt/fast-ai/llm-models/laguna-s-2.1/dflash-int4`,
  revision `5e07c246915c86dc6920fead03d019989224f2ba`;
- hardware: four Intel Arc Pro B70;
- topology: TP4/EP4/PP1/DP1;
- concurrency: one active sequence, one request at a time;
- target and KV dtype: BF16;
- DFlash depth: seven, greedy draft, standard rejection;
- async scheduling and prefix caching: disabled; and
- active models, cache, RPC, temporary state, and artifacts: internal NVMe
  only.

Every arm retains exact speculative attention, batched exact MoE, fused
W1-route-W2, route interleave, shared-elementwise, QKNorm/RoPE, and W1 N64.
Every other experimental Laguna selector is explicitly zero. Evidence,
tracing, deterministic-graph, AOT, forced-collective, history, ngram,
response-reuse, and cache shortcuts are absent.

## Frozen treatment

```text
A eager:
  --enforce-eager
  no compilation-config argument
  VLLM_XPU_LAGUNA_M8_BREAKABLE_GRAPH=0
  VLLM_USE_BREAKABLE_CUDAGRAPH=0
  XPU_GRAPH=0
  VLLM_XPU_ENABLE_XPU_GRAPH=0

B graph:
  no --enforce-eager
  mode=NONE
  cudagraph_mode=PIECEWISE
  cudagraph_capture_sizes=[8]
  max_cudagraph_capture_size=8
  VLLM_XPU_LAGUNA_M8_BREAKABLE_GRAPH=1
  VLLM_USE_BREAKABLE_CUDAGRAPH=1
  XPU_GRAPH=1
  VLLM_XPU_ENABLE_XPU_GRAPH=1
```

The first legitimate B capture occurs inside the first measured cold request.
It must not be pre-captured, warmed, removed, or adjusted from timing.

## Frozen order and stopping rule

The one-shot controller runs:

1. A1 eager;
2. B1 graph;
3. phase-1 analysis;
4. B2 graph only if every phase-1 gate passes;
5. A2 eager only after B2.

If phase 1 fails, B2 and A2 are forbidden and the campaign stops permanently.
The analyzer requires canonical sibling paths beneath the single campaign
root, validates the controller source hashes and order policy, and rejects
cross-root or selected-leg analysis.

Each leg receives a new service process, private cache, short private RPC
path, and fresh artifact directory. The fixed 13 unique prompts run exactly
once in suite order, sequentially, with no generation warm-up or retry.
Every leg proves 13 strict idle snapshots spanning at least 60 observed
seconds before service startup and again after shutdown. All 26 snapshot
payloads, device IDs, observer identity, names, timestamps, and monotonic
ordering are analyzer-validated.

## Quality and honesty gates

Every executed leg must pass:

- canonical q1 full token arrays 13/13;
- `cached_tokens=0` 13/13;
- one request per unique prompt, no history/prefix/ngram/response reuse;
- long-then-next exact 2/2;
- one 863-token rollover row exact 1/1;
- fixed request identity: seed 1, greedy, `enable_thinking=false`,
  `max_tokens=512`, returned token IDs;
- fixed source/model/binary/tool/service-environment identity;
- zero pre-suite speculative and request-decode counters;
- exactly 13 request-decode metric deltas;
- bounded shutdown, no worker/listener, and four-device idle proof.

Each B leg must additionally log exactly one audited capture and one replay on
each distinct TP/EP rank 0 through 3, with 146 graph segments and 145 eager
breaks. Each A leg must log no graph capture or replay.

## Frozen metric and causal gates

The primary metric is the median across the 13 prompts of streamed generated
token throughput for output tokens 1-100 after TTFT:

```text
bench.summary.tok_s_1_100_after_ttft.median
```

It is not wall throughput, mean throughput, best-row throughput, qualification
timing, or a selected run.

For both adjacent comparisons B1-A1 and B2-A2, require:

1. B headline strictly greater than A;
2. B strictly wins at least 9 of 13 paired prompt rows;
3. median paired percentage change is positive;
4. B saves at least `0.15 ms` per DFlash target cycle, where
   `aggregate_cycle_ms = 1000 * request_decode_seconds / draft_cycles`; and
5. absolute DFlash acceptance-rate drift is at most `0.001`
   (0.10 percentage point).

Full reproducibility additionally requires:

- all four legs pass every quality gate;
- all four match the canonical teacher and one another bitwise;
- both adjacent comparisons pass; and
- `min(B1, B2) > min(A1, A2)`.

The approved record floor is `33.89498511171744 tok/s`,
LocalMaxxing ID `cmrx6p5dv001bo4017hb7sixz`. Record eligibility requires
`min(B1, B2)` to be strictly greater. Only the lower B start may be submitted;
the better start is never selected.

## Frozen tooling

```text
run_laguna_m8_formal_graph_crossover.sh
  a28b9e06d8ec516e7565ab947cb7f7772b6ffb4b150796f1cf38dff76b7240a9
run_laguna_m8_formal_graph_crossover_leg.sh
  c957a74dc86423c6db4882288679b86672ddad8b38c653f3cc1dc7a79c654e5d
serve_laguna_m8_eager_nvme.sh
  833a748b6475ce01df322bd732a7f4dd79182c7b70e9b8b21160b4641e9e4aae
serve_laguna_m8_breakable_graph_nvme.sh
  c6729ae222e8f5b75fd9c2e22f965f6544418222d5d0da09dc053223bef92256
analyze_laguna_m8_graph_crossover.py
  e74ca0d77d269cd496f9acd001956da5c13622c587806817a3e3c47b28a85478
test_analyze_laguna_m8_graph_crossover.py
  bb3f49bede3b008fdf8e6c6edf5a1eea7ef9afbf669dc958cf26f75771f43e8f
compare_exact_runs.py
  87ad4d57907a15afba221be42ea00e3a1975308d421e0edc13881dafe38e3db3
capture_laguna_m8_idle_snapshot.py
  1f491cd89a8659c05c9d5668c2c978ade3b2e98fc61d299977f196130522cf01
bench-openai-realistic-suite.py
  40a483d9127a42c6e9f4a3651a429d39d25336d39eee0c782ba2c7712988aa2a
```

Static validation before registration:

- shell syntax passed for all three shell tools;
- Ruff check and formatting passed;
- analyzer tests: 8 passed;
- two independent read-only audits completed and both reported their blockers
  resolved;
- all source worktrees clean; and
- no service or generation was run while building the formal tooling.

Only a full analyzer `record_candidate` disposition can authorize payload
construction and an independent final submission audit.
