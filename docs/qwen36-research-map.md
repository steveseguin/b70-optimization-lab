# Qwen3.6 Research Map

Use this page as the first stop for the Qwen3.6-35B-A3B / Arc Pro B70 research
lane. It is a navigation map, not a benchmark claim.

## Current Status

As of 2026-06-22, this lane is a reference/archive lane rather than the primary
optimization target. The best strict-valid TP4 result is the PIECEWISE
forced-comm graph baseline at about `93.55 tok/s`; no attempted speculative
decode path produced a valid `>150 tok/s` result. Move new optimization effort
to another model unless doing a controlled upstream/runtime bakeoff or a deep
graph-compatible speculative-state engineering project.

The organized result packet is:

- [../results/qwen36-35b-quark-int8-b70/README.md](../results/qwen36-35b-quark-int8-b70/README.md)

It contains best valid 4x and 2x results, reproduction commands, validity
rules, invalid fast lanes, DFlash/ReplaySSM findings, and carryover notes for
other models.

## Baseline Identity

Known baseline identity to keep separate from graph-none results:

- Model: `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8`.
- Hardware: 4x Intel Arc Pro B70.
- Mode: TP4, PIECEWISE forced-comm graph lane.
- Reference speed: about `93.55 tok/s` when the full benchmark identity is
  present.

Never compare this lane to a run that is missing
`COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE"}'` or any of the graph/GDN
identity fields listed in [../AGENTS.md](../AGENTS.md).

## Read Order

1. [../results/qwen36-35b-quark-int8-b70/README.md](../results/qwen36-35b-quark-int8-b70/README.md)
   for the final organized result packet.
2. [../results/qwen36-35b-quark-int8-b70/validity-gates.md](../results/qwen36-35b-quark-int8-b70/validity-gates.md)
   before comparing or promoting any result.
3. [../notes/2026-06-20-master-plan.md](../notes/2026-06-20-master-plan.md)
   for the baseline-first plan that guided the late lane.
4. [../notes/2026-06-16-qwen36-current-handoff.md](../notes/2026-06-16-qwen36-current-handoff.md)
   for detailed run history and the latest full-layerlet gate interpretation.
5. [../notes/2026-06-21-qwen36-phase3-copy-skip.md](../notes/2026-06-21-qwen36-phase3-copy-skip.md)
   before trying metadata-copy or `num_computed_tokens` shortcuts again.
6. [../suggestions/findings/README.md](../suggestions/findings/README.md)
   for sourced upstream/fork/runtime leads.
7. [../notes/2026-06-20-research-plan-replayssm-and-speed.md](../notes/2026-06-20-research-plan-replayssm-and-speed.md)
   before touching ReplaySSM, DFlash, MTP, or EAGLE verifier state.

## Current Decisions

- This model should not receive more ad hoc flag/probe runs. The local flag
  space is exhausted; future work needs a crisp upstream/runtime or
  graph-compatible verifier hypothesis.
- Baseline-first work is the highest-value lane: compare local kernels against
  upstream `vllm-xpu-kernels` and targeted PRs before restarting speculative
  decode integration.
- The routed GEMM1 B-layout issue was a real correctness bug and is preserved
  in [../patches/vllm-xpu-kernels-qwen36-routegemm1-blayoutfix-20260620.patch](../patches/vllm-xpu-kernels-qwen36-routegemm1-blayoutfix-20260620.patch).
- Endpoint full-layerlet speed tests are not valid until the C++ op is actually
  entered. PIECEWISE gate traces showed missing scratch/workspace state; the
  graph-none mixed-workspace trace reached the rows=1 full-layerlet gate.
- Metadata copy skipping is rejected for now. Broad skipping hung; safer
  variants failed quality on the known-good lane.
- GPU-side `num_computed_tokens` update is rejected for now. It did not improve
  speed and failed the quick JSON gate.
- ReplaySSM remains the right correctness direction for GDN speculative verify,
  but this model's graph+spec lane remained correctness-racy. The next attempt
  should port proven upstream logic or make rollback/commit graph-compatible,
  not invent another slot-copy scheme.

## Artifact Locations

- [../notes/README.md](../notes/README.md): how to write and find lab notes.
- [../data/README.md](../data/README.md): what to track from run outputs.
- [../patches/README.md](../patches/README.md): how to preserve patches and
  outcomes.
- [../suggestions/findings/](../suggestions/findings/): sourced idea backlog.
- [../scripts/](../scripts/): launchers, canaries, and summarizers.
- [../results/qwen36-35b-quark-int8-b70/](../results/qwen36-35b-quark-int8-b70/):
  organized final result packet for this model/GPU lane.

## Next Safe Work If This Lane Is Reopened

1. Run an upstream kernel-package delta bakeoff on a clean branch, with the same
   canaries and full benchmark identity.
2. Run a TP2 vs TP4 single-request A/B only after identity capture is explicit.
3. Make speculative rollback/commit graph-compatible before chasing another
   `>150 tok/s` result.
4. For driver/runtime changes, read [local-ops.md](local-ops.md) first so sudo
   usage and credential hygiene stay consistent.
5. Revisit ReplaySSM or DFlash only with endpoint canaries, not synthetic-only
   validation.
