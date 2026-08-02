# Laguna q8/depth-7 FP8 drafter preregistration

Date registered: 2026-08-02 America/Toronto

Status at registration: source and tooling are unmodified for this candidate;
no q8 FP8 service has started. The q8/BF16 4K-prefill screen is complete and
rejected at 32.691 tok/s. This note freezes the next source hypothesis and
gates before creating its worktree.

## Hypothesis and claim boundary

The 32,640-token middle row shows that q8 and q12 both accepted eight tokens
over 118 draft cycles. q8's smaller exact verifier did not help because the
historically proven q8 lane uses the BF16 eager DFlash model, while q12 uses
the FP8 W8A16 DFlash path and a segmented drafter graph. q8 measured
`32.69134655844784 tok/s`; q12 measured `40.38107993869617 tok/s`.

This experiment asks whether the already implemented FP8 DFlash projections
and row-keyed workspaces can safely serve q8/depth-7 while the drafter remains
eager. It deliberately does not generalize or enable the q12 segmented
drafter graph, whose attention capture is sequence-length specialized.

This is a default-off experimental source lane. It cannot alter the protected
q12 record or support a LocalMaxxing submission. A short exactness pass and a
32K performance pass are both required before any broader campaign.

## Frozen source scope

Start a new vLLM worktree from
`1a7f61feffbc61b21b73f812d231c7426386ccdc`. XPU kernels remain unchanged at
`99886d783372e621941228250091dc8ebdc1595d`.

The source change must:

- add a distinct default-off q8 FP8 authorization selector;
- leave the existing q12 FP8/context-workspace contract unchanged when that
  selector is off;
- admit only DFlash q8/depth-7, exact max M8, TP4/EP4/PP1/DP1, BF16 target and
  KV cache, one sequence, synchronous scheduling, greedy draft sampling,
  standard rejection sampling, and no local argmax or LoRA;
- require the existing DFlash context-KV workspace and FP8 W8A16 selector;
- require the proven target q8 Breakable graph plus prebuilt exact-attention
  metadata, M8 shared-elementwise, fused W1-route-W2, route interleave, and
  QKNorm/RoPE stack;
- require q12 BF16/M-wide target-router selectors, M12 shared-elementwise,
  GRF128, transposed target scales, DFlash segmented graph, DFlash attention
  graphs, and legacy drafter graph to remain zero; and
- use the existing row-keyed context-KV and auxiliary workspaces without a
  kernel or arithmetic change.

Any need to modify the FP8 kernel, enable segmented graph capture, relax model
shape checks, or share quantized draft weights with the target is outside this
candidate and closes it for redesign.

## Required source tests

Before a service launch:

- the existing q12 context-KV and FP8 contract tests remain unchanged and
  pass;
- new tests accept only the exact q8 authorization identity;
- selector-off q8, depth/width drift, q12-router leakage, missing context
  workspace, missing FP8, segmented/draft graph enablement, async scheduling,
  local argmax, and model-shape drift all fail closed;
- existing FP8 conversion-count, source-weight immutability, target LM-head
  non-aliasing, and auxiliary/context-workspace tests pass; and
- focused GPU-model-runner graph-contract tests pass.

The experimental source and main tooling must be committed and all worktrees
clean before generation.

## Short exactness gate

Run a fresh q8-FP8 service against the three fixed 256-token retrieval prompts
and the preserved q1 oracle used by the exact-prefill gate. All three returned
prompt arrays, output token arrays, text hashes, retrieval fields, cache-zero
checks, and response-shape checks must pass exactly. The target must log exactly
four `146/145` captures and four replays; the drafter must log no graph.

Any exactness, topology, service, cleanup, or device failure rejects the
candidate before 32K. Short timing is diagnostic only.

## 32K screen

If and only if the short gate passes, use the already validated strict-memory
identity:

- `max_model_len=32768`;
- `max_num_batched_tokens=4096`;
- GPU memory utilization 0.80;
- 12 GiB minimum available-RAM guard with 24 GiB total temporary swap;
- `laguna-lc-01024-early` warm-up, then
  `laguna-lc-32640-middle` and its automatic sentinel; and
- no oracle, retry, prefix cache, async scheduler, or retained service.

The 32K candidate passes only if all intrinsic and retrieval checks pass,
memory and cleanup gates pass, topology is exactly target-only q8, and the
long row reaches at least `41.59251233685705 tok/s`. This is 3% above the
matching q12 row and 27.23% above the rejected q8/BF16 row. Prefill and TTFT
must also be reported, but the headline question is sustained decode.

A pass authorizes a complete three-position 32K campaign and a matched q8 BF16
control under the same source commit. A failure is preserved and closes this
q8 FP8 eager-drafter candidate; there is no rescue run or threshold change.
