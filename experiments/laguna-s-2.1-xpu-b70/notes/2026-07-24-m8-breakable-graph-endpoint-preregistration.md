# Laguna M8 Breakable graph endpoint preregistration

Date registered: 2026-07-24 America/Toronto

Status at registration: source, launch contract, two-start order, exactness
gates, analyzer, and failure policy frozen before either endpoint service was
started and before any endpoint generation under the production graph lane.

## Purpose and claim boundary

This is a correctness qualification only. It cannot support a timing, speed,
record, or LocalMaxxing claim. Its sole question is whether the raw-byte-exact
V10 Breakable M8 graph stack remains bitwise canonical through the live OpenAI
endpoint over two independent fresh starts.

The one permitted root is:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-graph-endpoint-6fb4e8d10-0ce373a31-20260724T211707Z
```

The runner must fail closed rather than reuse this root or either short RPC
path. A pre-generation tooling failure may only be repaired under a new
preregistered root. Any failure after a service starts is a classified result,
not a replaceable trial.

## Frozen source and runtime identity

- main repo tooling commit:
  `6fb4e8d10a00134cff0d8f01bbea94d2c4bf3673`;
- vLLM:
  `0ce373a3115fb4498c5e7a041d4fc9212fd6b5ca`;
- XPU kernels:
  `4772f727590c51b72add79350b913d098cf67872`;
- target revision:
  `4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb`;
- DFlash revision:
  `5e07c246915c86dc6920fead03d019989224f2ba`;
- target and draft paths:
  `/mnt/fast-ai/llm-models/laguna-s-2.1/{int4,dflash-int4}`;
- all active cache, temporary, RPC, and result paths: internal NVMe only; and
- `/media/steve/CorsairExternal`: forbidden as an active path.

The vLLM commit is the V10 raw-parity-passing runtime plus one narrow policy
change: shared-elementwise is permitted without evidence variables only when
the complete validated Breakable M8 graph contract matches. The same guard
still admits the exact segmented-graph evidence pair and rejects partial or
wrong evidence identity and every graph-config drift. Focused Laguna,
Breakable capture/materialization, and model-runner tests passed before this
registration.

## Frozen graph and model stack

Every service must use exactly:

```text
compilation:
  mode=NONE
  cudagraph_mode=PIECEWISE
  cudagraph_capture_sizes=[8]
  max_cudagraph_capture_size=8

VLLM_XPU_LAGUNA_M8_BREAKABLE_GRAPH=1
VLLM_USE_BREAKABLE_CUDAGRAPH=1
XPU_GRAPH=1
VLLM_XPU_ENABLE_XPU_GRAPH=1
VLLM_USE_AOT_COMPILE=0
VLLM_XPU_LAGUNA_DETERMINISTIC_GRAPH=0

VLLM_XPU_EXACT_SPEC_ATTN=1
VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE=1
VLLM_XPU_LAGUNA_M8_FUSED_W1_ROUTE_W2=1
VLLM_XPU_LAGUNA_M8_ROUTE_INTERLEAVE=1
VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE=1
VLLM_XPU_LAGUNA_M8_QKNORM_ROPE=1
VLLM_XPU_LAGUNA_M8_W1_N_TILE=64
```

All other experimental Laguna selectors are explicitly zero. Diagnostic
evidence variables must be absent. The endpoint is DFlash depth 7 with greedy
draft sampling and standard rejection sampling, TP4/EP4/PP1/DP1, BF16 target
and KV cache, one maximum active sequence, no async scheduling, no LoRA, no
dual-batch overlap, no prefix caching, and no enforce-eager.

## Frozen request and order

Run exactly two independent service processes in this order:

1. `start-a`;
2. stop, prove no workers and four-device idleness;
3. `start-b`;
4. stop, prove no workers and four-device idleness.

Each service receives the fixed 13-prompt realistic suite once, sequentially,
with no generation warm-up, retry, repeated prompt, request concurrency,
history, response reuse, prefix/KV reuse, or retained service. Requests use
seed 1, greedy target policy, `enable_thinking=false`, `max_tokens=512`, and
returned token IDs.

Canonical assets remain unchanged:

- suite SHA256:
  `9fdaacfdc4de59407a73cbe0d8130fa0f6abe91fed782e399a58adbc035ea638`;
- q1 teacher SHA256:
  `d41d3d5e2471ee98f783e58407e44217ade67f7472147eeeb82780efa89879d1`;
- teacher:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/bulletproof-q1-canonical-cb616c6-6fc06b0-20260722T142908Z/bench.json`.

## Required PASS gates

Both starts independently must satisfy all of:

- 13/13 prompt identities and full returned token arrays exactly equal to the
  canonical q1 teacher;
- `cached_tokens=0` for all 13 requests;
- exactly one request for each unique prompt;
- row 0 completes 512 tokens and row 1 remains exact;
- exactly one `prompt_tokens >= 863` rollover row, exact;
- actual service environment, model/draft identity, graph contract, selectors,
  and request identity equal the frozen values;
- four distinct TP/EP ranks each log exactly one audited capture topology and
  one audited replay topology;
- every logged topology is exactly 146 graph segments and 145 eager breaks;
- clean bounded shutdown, zero residual workers, and strict device-idle proof.

The two starts must also match one another 13/13 bitwise and pass the same
cache-zero, long-then-next, and rollover checks. Any missing identity,
topology, output, freshness, cleanup, or idle proof is FAIL.

## Frozen tooling

```text
run_laguna_m8_graph_endpoint_gate.sh
  f5743c67e553941d7086c976ce8529ba4a30a48f5c768193dde86b1f526ea895
serve_laguna_m8_breakable_graph_nvme.sh
  c6729ae222e8f5b75fd9c2e22f965f6544418222d5d0da09dc053223bef92256
analyze_laguna_m8_graph_endpoint.py
  4a261ed419d7cb206ed63ce57c056d44dbb0ffa4ac152b44a961ba718bb38b37
test_analyze_laguna_m8_graph_endpoint.py
  6e251b80c92f3722cc0b24efc408c8a1417e96db424f4b771f0f5960a993a226
```

Static validation before registration:

- shell syntax passed for both shell tools;
- Ruff check and formatting passed;
- analyzer tests: 4 passed;
- independent read-only safety audit completed;
- all three source worktrees were clean; and
- no model endpoint or generation was run while developing or auditing the
  tools.

## Next decision

PASS authorizes a separately preregistered cold performance crossover against
the approved `33.89498511171744 tok/s` record. It does not itself authorize a
speed claim or submission. FAIL is preserved and root-caused before any
benchmark work.
