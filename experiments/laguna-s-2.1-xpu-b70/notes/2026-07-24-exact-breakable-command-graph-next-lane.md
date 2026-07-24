# Laguna exact runtime command-graph lane

Date: 2026-07-24 America/Toronto

## Status

This is a source-only research finding and proposed next lane. No accelerator,
model, endpoint, network, or LocalMaxxing action was performed. It does not
authorize a run and does not alter the active M=8 gather-sharded component
preregistration.

The current approved record remains:

- `33.89498511171744 tok/s`;
- LocalMaxxing `cmrx6p5dv001bo4017hb7sixz`;
- vLLM `8936aac144929190c1e53f8b8624ca397ce16f5b`;
- XPU kernels `b6076ce1249ffee0e30bee528f4cd15c3bffb234`; and
- exact eager target verification with DFlash depth 7.

## Finding

The record vLLM tree already contains a runtime-only command-graph mechanism
that has not been evaluated for Laguna:

- `vllm/compilation/breakable_cudagraph.py`;
- `VLLM_USE_BREAKABLE_CUDAGRAPH=1`; and
- the XPU runner maps the CUDA-shaped wrapper API directly to
  `torch.xpu.XPUGraph`.

Unlike the rejected Laguna PIECEWISE attempt, breakable graph mode explicitly
sets `CompilationMode.NONE`. It records the warmed eager kernel submissions
with PyTorch's native XPU command graph instead of lowering the model through
Inductor. That distinction directly addresses the known exactness failure:
the prior target graph changed BF16 materialization/reduction boundaries
during compiler lowering and matched the canonical teacher on only 1/13
prompts.

The local `option4-decoder/` work independently proves the underlying
substrate on this software stack:

- mixed oneDNN and Triton submissions can be captured and replayed bitwise
  exactly;
- the finalized Level Zero list can be replayed as one submission boundary;
- raw replay can avoid host synchronization; and
- fixed tensor addresses and current-queue identity can be checked before
  every replay.

That prior DeepSeek endpoint result does not close this Laguna lane. DeepSeek
was already running PIECEWISE graphs, so replacing one already-amortized
attention island was neutral-to-negative. Laguna's approved exact target is
fully eager because its compiler-generated graphs were inexact. Its steady
M=8 target cycle historically contains roughly 1,945 XPU kernel launches and
98 causally required collectives, leaving a material host/submission residual.
Runtime recording therefore attacks a cost that the DeepSeek experiment had
already removed.

## Exactness boundary

The only acceptable treatment records and replays the incumbent eager target
kernels. It must not:

- invoke `torch.compile`, Inductor, AOT compilation, or compiler fusion;
- enable `VLLM_XPU_LAGUNA_DETERMINISTIC_GRAPH` arithmetic substitutes;
- change any target kernel, weight, layout, BF16 materialization, fixed-rank
  rank-0/1/2/3 sum, attention implementation, KV update, or sampler;
- capture or otherwise change the DFlash draft in the first experiment;
- reuse request history, prefix state, prompt results, or generated tokens; or
- treat draft equality as a substitute for target greedy equality.

The first treatment is target-only, width M=8 only. M=1..7, prefill, request
boundaries, and any unsupported shape remain on the approved eager path.
Final generated tokens must still match the canonical q=1 greedy teacher
bitwise.

## Proposed fail-closed sequence

1. Create a default-off Laguna target-only selector from the approved record
   vLLM commit. Keep the DFlash model outside the breakable wrapper.
2. Use `VLLM_USE_BREAKABLE_CUDAGRAPH=1`,
   `CompilationMode.NONE`, XPU graph enabled, AOT disabled, and PIECEWISE
   runtime dispatch only as the shape/segment dispatcher. Prove from logs and
   runtime state that no compiler backend ran.
3. Capture only the fixed M=8 target verifier entry. Require stable addresses
   for every input, output, KV binding, collective input/output, and graph-pool
   allocation before replay.
4. First test whether the incumbent oneCCL all-gathers record directly. If
   they do not, end graph segments at each collective and run the unchanged
   collective eagerly into caller-owned persistent output buffers. Resume
   capture only after the fixed-rank BF16 sum boundary. Do not replace or
   coalesce a collective.
5. On the frozen changing-input component corpus, compare eager and replayed
   bytes at every exposed layer boundary before timing, after timing, and
   after graph reuse. Require all cards and all epochs to pass.
6. Trace eager and replay paths with PTI/unitrace. Count graph submissions,
   eager collective calls, direct kernel submissions, and host
   synchronization. Reject stale outputs, missing launches, hidden
   recompilation, capture-time constants, pointer drift, or a replay that
   silently falls back to eager.
7. Only after the component and trace gates pass, run a fresh cold q=1
   target-only service against the canonical teacher. A DFlash endpoint
   crossover remains separately preregistered and requires new services,
   cache-zero prompts, long-next and rollover checks, and conservative
   lower-start reporting.

## Stop rules

Stop before an endpoint on any raw-byte mismatch, capture/replay nondeterminism,
mutable-state reuse, unsupported collective behavior, graph fallback, or
failure to reduce measured host/submission cost. A speed number from an
inexact or cache-bearing graph is invalid regardless of magnitude.

No result is LocalMaxxing-eligible unless the final fresh-cold endpoint exceeds
the matching approved four-B70 record under the complete benchmark identity
and every target output is canonical-teacher exact.
