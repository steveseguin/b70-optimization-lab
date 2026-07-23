# Laguna shared-elementwise + QKNorm/RoPE endpoint-stack preregistration

Date registered: 2026-07-23 America/Toronto

Status at registration: treatment, order, quality gates, performance gates,
stopping rules, runner, and analyzer frozen after the shared-elementwise
four-card component pass and before A1 service startup or any endpoint
generation under this stack.

## Question

The exact shared-elementwise bundle passed every physical B70, won all
31/31 paired component blocks on each card, removed exactly 94 launches per
47-layer target cycle, and saved `0.699138-0.722866 ms/cycle`. The separately
proven exact Q/K RMSNorm + RoPE fusion reduced 144 launches to 48 and saved
`1.134039 ms/cycle` in its isolated component gate. Its previous endpoint
crossover beat both adjacent controls in headline throughput, normalized
cycle time, and 11-12/13 rows, but large run variance and a lower candidate
below the public record prevented promotion.

This experiment asks whether enabling both exact launch-reduction bundles
together produces a repeatable cold endpoint win large enough to survive the
observed 1-3% run variance. Their savings are not assumed to add. The stack is
measured as one predeclared treatment.

## Frozen source and treatment

Source and rebuilt shared native library are fixed to:

- vLLM:
  `8936aac144929190c1e53f8b8624ca397ce16f5b`;
- XPU kernels:
  `b6076ce1249ffee0e30bee528f4cd15c3bffb234`; and
- `_C.abi3.so` SHA256:
  `126da37b23e5eff6840dd256c90164e3a282469e5fafa27830530e63ff36bce2`.

Both sources include the previously component-proven QKNorm/RoPE path.
All other native binary hashes, model manifests, runtime packages, driver
identity, and compiler/loader environment must be captured and frozen by the
runner before A1.

Every leg uses the approved eager depth-7 exact stack:

```text
VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE=1
VLLM_XPU_LAGUNA_M8_FUSED_W1_ROUTE_W2=1
VLLM_XPU_LAGUNA_M8_ROUTE_INTERLEAVE=1
VLLM_XPU_EXACT_SPEC_ATTN=1
VLLM_XPU_LAGUNA_M8_FUSED_TRANSACTION=0
VLLM_XPU_LAGUNA_M8_BF16_ATTN_MM=0
VLLM_XPU_LAGUNA_DETERMINISTIC_GRAPH=0
VLLM_XPU_ENABLE_XPU_GRAPH=0
VLLM_USE_AOT_COMPILE=0
XPU_GRAPH=0
LAGUNA_DFLASH_NUM_SPECULATIVE_TOKENS=7
```

The treatment is exactly:

```text
A control:
  VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE=0
  VLLM_XPU_LAGUNA_M8_QKNORM_ROPE=0
  VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK=0

B candidate:
  VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE=1
  VLLM_XPU_LAGUNA_M8_QKNORM_ROPE=1
  VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK=0
```

The BF16 router specialization remains off in both arms. No result from its
failed endpoint trial is attributed to this stack, and no additional
candidate may be enabled after seeing A1 or B1.

## Frozen benchmark identity

- target: Poolside Laguna S 2.1 INT4;
- target revision:
  `4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb`;
- draft: quantization-matched Laguna S 2.1 DFlash INT4;
- draft revision:
  `5e07c246915c86dc6920fead03d019989224f2ba`;
- hardware: four Intel Arc Pro B70;
- topology: TP4, EP4, DP1, PP1;
- concurrency: one active sequence and one request at a time;
- execution: eager exact target, BF16 KV cache, async scheduling disabled;
- speculative depth: seven;
- fixed 13-prompt suite SHA256:
  `9fdaacfdc4de59407a73cbe0d8130fa0f6abe91fed782e399a58adbc035ea638`;
- canonical q=1 teacher:
  `/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/bulletproof-q1-canonical-cb616c6-6fc06b0-20260722T142908Z/bench.json`;
- request: seed 1, greedy target policy, `enable_thinking=false`,
  `max_tokens=512`, returned token IDs; and
- primary metric: median generated-token throughput for output tokens 1-100
  after TTFT over the 13 fixed unique prompts.

The runner must pin and record the exact target and draft revisions,
tokenizer, chat template, model index/code, all LFS file counts/byte counts and
SHA256s, runtime commits, native binaries, oneCCL/libfabric identity, driver
tooling, and all benchmark-sensitive environment variables. Any mismatch is a
hard stop before service startup.

## Frozen sequential order

Run at most four fresh starts, strictly in this order:

1. A1: both shared-elementwise and QKNorm/RoPE off;
2. B1: both shared-elementwise and QKNorm/RoPE on;
3. B2: both on, only if every phase-1 gate passes; and
4. A2: both off.

Each leg uses a new service process and new uniquely named artifact directory.
Capture metrics before the suite, send every fixed prompt exactly once,
capture metrics after the suite, run the teacher comparison and canaries, then
stop the service and prove all four devices are idle. Keep the devices free
for 60 seconds between adjacent legs.

There is no generation warm-up, repeated prompt, response reuse, prompt/KV
cache reuse, prefix/history/ngram acceleration, concurrent request, retained
service, or fifth rescue run. A failed preflight before service startup is a
zero-generation invalid block: preserve it, fix only the tooling defect, and
use a newly named root. A failure after a measured leg begins is classified
and not silently replaced under the same leg identity.

## Quality and honesty gates

Every executed leg must pass all of:

- realistic-suite final gate;
- 13/13 prompt identities equal to the frozen suite;
- 13/13 complete returned token-ID arrays bitwise equal to the canonical q=1
  teacher;
- 13/13 `cached_tokens=0`;
- exactly one cold request for each unique suite prompt;
- 512-token long-then-next exactness 2/2;
- 863-input/512-output rollover exactness 1/1;
- exact token equality 13/13 across every executed leg;
- source, native binary, model-manifest, runtime, and environment identity;
- metrics-delta consistency with the request logs; and
- successful bounded shutdown plus four-device idle proof.

Record every per-row timing, token array and hash, prompt hash, DFlash cycle
count, drafted and accepted totals, accepted-position histogram, aggregate
request decode seconds, and target-cycle-normalized decode time. One
exactness, cache, freshness, identity, accounting, or cleanup failure rejects
the experiment regardless of speed.

The earlier QKNorm-only crossover's stricter identical-position-histogram
criterion remains failed and is not retroactively reclassified. This new
experiment preregisters the router protocol's bounded work-drift criterion:
the absolute pairwise DFlash acceptance-rate difference must be no more than
`0.10` percentage point. Target output exactness remains bitwise and
non-negotiable.

## Phase-1 early stop

After A1 and B1, stop without B2 or A2 unless all of these are true:

1. A1 and B1 pass every quality, honesty, identity, and cleanup gate.
2. B1 primary headline throughput is strictly greater than A1.
3. B1 wins at least 9 of 13 paired prompt rows.
4. The median paired per-prompt throughput change is positive.
5. Aggregate request decode seconds divided by DFlash target cycles is at
   least `0.15 ms/cycle` lower for B1.
6. The absolute A1/B1 acceptance-rate difference is at most `0.10`
   percentage point.

Failure of any phase-1 condition classifies the experiment
`phase1_failed_stop`. Preserve A1/B1, do not run B2/A2, do not stage a payload,
and do not submit.

## Full promotion and record gates

If the full A-B-B-A block runs, call the stack a reproducible endpoint win
only if both adjacent comparisons independently pass:

- B1 headline throughput is greater than A1, and B2 is greater than A2;
- each candidate wins at least 9/13 paired prompt rows;
- each median paired per-prompt throughput change is positive;
- each candidate saves at least `0.15 ms` per target cycle in aggregate
  request decode time; and
- each pair's absolute acceptance-rate difference is at most `0.10`
  percentage point.

The lower of B1 and B2 must also be strictly greater than the lower of A1 and
A2. If exactness passes but any causal or reproducibility gate fails, preserve
the result as an exact negative or inconclusive stack and leave both
selectors default-off.

The existing approved LocalMaxxing record is
`33.438926675602126 tok/s` (`cmrwot89400gqnz014oodtlbp`). A LocalMaxxing
submission additionally requires the lower of B1 and B2 to exceed that value.
Only the lower candidate is eligible, and only after the complete evidence,
payload, and benchmark-identity audit. There is no fifth run to rescue a
miss.

## Frozen endpoint tooling

The endpoint tools were implemented, audited, and hashed before A1:

```text
runner:
  experiments/laguna-s-2.1-xpu-b70/tools/run_shared_elementwise_qknorm_stack_crossover_leg.sh
  SHA256: 2eb8f37b0a7916b2e72d9a51f393034df722b8408ebd9f02dabe54a7fe5280a2

phase-1/full analyzer:
  experiments/laguna-s-2.1-xpu-b70/tools/analyze_shared_elementwise_qknorm_stack_crossover.py
  SHA256: 408cd6948f8e7708b12302b6061011ae2b32c812481574676dfd8f239f0a0714
```

The runner rejects ambient benchmark-sensitive vLLM, Laguna, graph, Level
Zero, SYCL, Unified Runtime, oneCCL/libfabric, CPU-threading, compiler, and
loader variables before setting the exact arm environment. The analyzer pins
the runner hash and rejects duplicate/missing leg identity, hash or manifest
mismatch, stale/reused artifacts, cache/freshness failures, accounting
mismatch, wrong treatment, source-commit drift between legs, wrong order, and
an impermissible B2/A2 after a failed phase 1.

Static and offline validation before A1 included shell syntax, Python
compilation, Ruff, whitespace checks, historical full-ABBA parsing with
synthetic frozen identities, phase-only parsing, partial-argument rejection,
and explicit rejection of router-selector and repository-commit drift. No
service or endpoint generation was started during tooling validation.
