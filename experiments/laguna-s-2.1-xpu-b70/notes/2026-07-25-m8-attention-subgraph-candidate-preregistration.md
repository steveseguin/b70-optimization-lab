# Laguna M8 attention-subgraph candidate preregistration

Date: 2026-07-25 America/Toronto

Status: **preregistered; implementation not yet tested**.

## Measurement and hypothesis

The passed in-process replay telemetry at
`laguna-m8-inprocess-replay-17769a57d-8cf58ed0f-20260725T002351Z`
measured 48 attention eager-boundary host calls at 8.118 ms median per M8
replay, or 48.5% of replay host time. Each boundary currently re-enters the
full Python/Torch/Triton attention body and submits its internal XPU work
eagerly.

The candidate captures each of those 48 already-isolated attention bodies as
its own XPU subgraph during the existing lazy outer capture. Normal replay
then submits one bound subgraph replay per attention boundary rather than
re-running its Python submission path.

## Frozen implementation contract

- new selector:
  `VLLM_XPU_LAGUNA_M8_CAPTURE_ATTENTION_GRAPHS`, false by default;
- valid only with the existing guarded Laguna M8 Breakable-graph transaction;
- the preceding outer graph segment is ended and materialized exactly as in
  the incumbent;
- only `kind="attention"` eager bodies are captured; all 97 collectives remain
  eager and causally ordered;
- the attention subgraph uses the existing graph pool and static buffers;
- after subgraph capture, it is replayed once immediately so the following
  outer segment consumes materialized attention output;
- subsequent outer capture resumes only after that materialization;
- topology labels and order remain 146 outer graph calls, 97 collective
  boundaries, and 48 attention boundaries;
- no attention kernel, tensor expression, datatype, reduction, collective,
  stream/event sequence, model weight, sampler, or speculative-verification
  rule is intentionally changed;
- any unsupported capture, topology drift, address drift, output mismatch, or
  process/device hygiene failure aborts. There is no silent fallback while
  the selector is enabled.

## Validation ladder

1. Add focused unit tests for default-off behavior, capture/materialize/replay
   ordering, and nested decorated operations remaining inline.
2. Run existing Breakable-graph unit tests and static checks.
3. Run a new fresh q1/eager/candidate-graph 272-token telemetry campaign with
   one uncached generation per process. Require bitwise identical token IDs,
   text, and finish reason; four complete rank profiles; and the unchanged
   146/145 topology.
4. Compare diagnostic attention-boundary host time with the frozen
   8.118 ms median only if step 3 passes.
5. If the candidate is exact and materially reduces host time, run the formal
   cold benchmark crossover against the approved 92.164 tok/s identity. Only
   an independently reproducible, exact, policy-compliant formal win may be
   promoted or submitted.

Diagnostic generation wall time and instrumented replay time are never record
or LocalMaxxing evidence.
