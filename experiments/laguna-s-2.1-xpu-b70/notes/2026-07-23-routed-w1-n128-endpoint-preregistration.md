# Laguna routed-W1 N128 endpoint preregistration

Date registered: 2026-07-23 America/Toronto

Status at registration: treatment, order, quality gates, performance gates,
stopping rules, and endpoint tooling boundary frozen after the complete
four-card component/counter pass and before any service startup or endpoint
generation under N128.

## Question and prior evidence

The single preregistered component treatment changes only the exact M=8 routed
W1 workgroup tile from N64 to N128. It passed 64 changing raw-exact epochs
before and after timing on every physical B70, won all 31/31 A-B-B-A timing
blocks on every card, and saved `0.561977-0.602729 ms` per 47 target-layer W1
calls. Four-card mean isolated W1 improvement was 8.7271%.

Matched ComputeBasic counters independently measured a 7.7158% mean
counter-time improvement, +2.4579 points EU activity, -1.2442 points stall,
and +0.1585 points occupancy. Both policies retain 5,120 output-owning
subgroups; all compiler and runtime spill proxies were zero. Separate
full-path traces proved identical N64 W2 and gather names and 13/13 call counts
on every card.

This experiment asks whether that exact occupancy win survives fresh cold
four-card serving variance and improves the currently approved strict record.
No component saving is assumed to translate directly into endpoint speed.

## Frozen source and treatment

- vLLM:
  `8936aac144929190c1e53f8b8624ca397ce16f5b`;
- XPU kernels:
  `c59aaadbbfd350c2b5f4ad663e247c2811ae3181`;
- `_xpu_C.abi3.so` SHA-256:
  `f5f672130cc1b1d550646f732a6d576952c49514eba7a10db60fc1c361938fd8`;
- `libgrouped_gemm_xe_2.so` SHA-256:
  `fc74a6452b95643768889e2598df77bc4f4aa2b0925257a4c0eff371b1cf6c96`;
- shared `_C.abi3.so` SHA-256:
  `126da37b23e5eff6840dd256c90164e3a282469e5fafa27830530e63ff36bce2`;
- target revision:
  `4bbfc285f2f8b3b6b526274c133b7b17aae6c8cb`;
- draft revision:
  `5e07c246915c86dc6920fead03d019989224f2ba`; and
- current approved LocalMaxxing record:
  `33.89498511171744 tok/s`, `cmrx6p5dv001bo4017hb7sixz`.

Every leg retains the complete approved exact stack:

```text
VLLM_XPU_LAGUNA_BATCHED_EXACT_MOE=1
VLLM_XPU_LAGUNA_M8_FUSED_W1_ROUTE_W2=1
VLLM_XPU_LAGUNA_M8_ROUTE_INTERLEAVE=1
VLLM_XPU_LAGUNA_M8_SHARED_ELEMENTWISE=1
VLLM_XPU_LAGUNA_M8_QKNORM_ROPE=1
VLLM_XPU_LAGUNA_M8_BF16_ROUTER_TOPK=0
VLLM_XPU_EXACT_SPEC_ATTN=1
VLLM_XPU_LAGUNA_M8_FUSED_TRANSACTION=0
VLLM_XPU_LAGUNA_M8_BF16_ATTN_MM=0
VLLM_XPU_LAGUNA_DETERMINISTIC_GRAPH=0
VLLM_XPU_ENABLE_XPU_GRAPH=0
VLLM_USE_AOT_COMPILE=0
XPU_GRAPH=0
LAGUNA_DFLASH_NUM_SPECULATIVE_TOKENS=7
```

The sole A/B difference is:

```text
A control:
  VLLM_XPU_LAGUNA_M8_W1_N_TILE=64

B candidate:
  VLLM_XPU_LAGUNA_M8_W1_N_TILE=128
```

Literal 64, rather than an unset variable, is required for the control
identity. N32 and every other tile are forbidden. No graph, fusion, router,
attention, DFlash, allocator, collective, service, or benchmark flag may be
changed after A1.

## Frozen benchmark identity

- target: Poolside Laguna S 2.1 INT4;
- draft: quantization-matched Laguna S 2.1 DFlash INT4;
- hardware: four Intel Arc Pro B70;
- topology: TP4, EP4, DP1, PP1;
- concurrency: one active sequence and one request at a time;
- execution: eager exact target, BF16 KV cache, async scheduling disabled;
- speculative depth: seven;
- fixed 13-prompt suite SHA-256:
  `9fdaacfdc4de59407a73cbe0d8130fa0f6abe91fed782e399a58adbc035ea638`;
- canonical q=1 teacher:
  `/media/steve/CorsairExternal/llm-optimization-artifacts/laguna-s-2.1/runs/bulletproof-q1-canonical-cb616c6-6fc06b0-20260722T142908Z/bench.json`;
- request: seed 1, greedy target policy, `enable_thinking=false`,
  `max_tokens=512`, returned token IDs; and
- primary metric: median generated-token throughput for output tokens 1
  through 100 after TTFT over the 13 fixed unique prompts.

The runner must pin and record target/draft revisions, tokenizer, chat
template, model index/code, all LFS file counts/byte counts/SHA-256 values,
runtime commits, native binaries, oneCCL/libfabric identity, driver tooling,
and every benchmark-sensitive environment variable. Any mismatch is a hard
stop before service startup.

## Frozen sequential order and freshness

Run at most four fresh starts, strictly:

1. A1: literal W1 N64;
2. B1: literal W1 N128;
3. B2: literal W1 N128, only if every phase-1 gate passes; and
4. A2: literal W1 N64.

Each leg uses a new service process and uniquely named artifact directory.
Capture metrics before the suite, send every fixed prompt exactly once,
capture metrics after the suite, run teacher comparison and canaries, stop the
service, and prove all four devices idle. Keep the devices free for at least
60 seconds between adjacent legs.

There is no generation warmup, repeated prompt, response reuse, prompt/KV
cache reuse, prefix/history/ngram acceleration, concurrent request, retained
service, or fifth rescue run. A failed preflight before service startup is a
zero-generation invalid block: preserve it, fix only the tooling defect, and
use a new root. A failure after a measured leg begins is classified and not
silently replaced.

## Quality and honesty gates

Every executed leg must pass all of:

- realistic-suite final gate;
- 13/13 prompt identities equal to the frozen suite;
- 13/13 complete returned token-ID arrays bitwise equal to the canonical q=1
  greedy teacher;
- 13/13 `cached_tokens=0`;
- exactly one cold request for each unique suite prompt;
- 512-token long-then-next exactness 2/2;
- 863-input/512-output rollover exactness 1/1;
- exact token equality 13/13 across every executed leg;
- source, native binary, model-manifest, runtime, and environment identity;
- metrics-delta consistency with request logs; and
- bounded shutdown plus four-device idle proof.

Record every row timing, token array and hash, prompt hash, DFlash cycle count,
drafted and accepted totals, accepted-position histogram, aggregate request
decode seconds, and target-cycle-normalized decode time. One exactness, cache,
freshness, identity, accounting, or cleanup failure rejects the lane
regardless of speed.

Output quality is bitwise, not statistical. The only bounded work-drift
allowance is an absolute pairwise DFlash acceptance-rate difference no greater
than `0.001` (0.10 percentage point).

## Phase-1 early stop

After A1 and B1, stop without B2 or A2 unless:

1. both legs pass every quality, honesty, identity, and cleanup gate;
2. B1 headline throughput is strictly greater than A1;
3. B1 wins at least 9/13 paired prompt rows;
4. median paired per-prompt throughput change is positive;
5. B1 saves at least `0.15 ms` per target cycle in aggregate request decode
   time; and
6. absolute A1/B1 acceptance-rate difference is at most `0.001`.

Failure classifies the lane `phase1_failed_stop`; preserve both legs and do
not run B2/A2, stage a payload, or submit.

## Full reproducibility and record gates

If the full A-B-B-A block runs, both adjacent comparisons must independently
pass:

- B1 > A1 and B2 > A2 in headline throughput;
- each candidate wins at least 9/13 paired prompt rows;
- each median paired per-prompt change is positive;
- each candidate saves at least `0.15 ms` per target cycle; and
- each pair's absolute acceptance-rate difference is at most `0.001`.

The lower of B1/B2 must be strictly greater than the lower of A1/A2. For a
record, that lower candidate must also be strictly greater than
`33.89498511171744 tok/s`. Only the lower candidate is eligible. Exactness
without every causal/reproducibility gate is preserved as a negative or
inconclusive result. There is no fifth run.

## Frozen endpoint-tooling boundary

Before A1, create a dedicated runner and fail-closed analyzer derived from the
approved shared-elementwise/QKNorm stack tools. They must:

- keep shared-elementwise and QKNorm/RoPE on in both arms;
- keep the BF16 router specialization off in both arms;
- set and record literal W1 tile 64 or 128 as the sole treatment;
- reject an ambient W1-tile variable and all other benchmark-sensitive
  inherited variables;
- pin the source commits and all three native binary identities above;
- pin the runner hash in the analyzer;
- reject missing/duplicate/reordered legs, identity drift, stale artifacts,
  bad phase-1 continuation, cache/freshness/accounting failures, and any
  treatment difference beyond W1 tile; and
- pass shell syntax, Python compilation, Ruff, whitespace, historical/synthetic
  full-ABBA, phase-only, and intentional drift-rejection tests.

Commit the audited tools and their hashes before A1. The main repository must
then remain clean and at one commit for every leg. Tool validation may parse
retained endpoint artifacts but may not start a service or generate a prompt.

No service was started and no LocalMaxxing request was made while registering
this protocol.
