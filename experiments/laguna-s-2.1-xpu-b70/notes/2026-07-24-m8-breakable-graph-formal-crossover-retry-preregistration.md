# Laguna M8 Breakable graph formal crossover retry preregistration

Date registered: 2026-07-24 America/Toronto

Status at registration: retry source, one-shot root, and tool hashes frozen
before A1 service startup and before any generation in this retry.

## Claim boundary and relationship to the stopped root

This recovery adopts every model, runtime, treatment, prompt, metric, quality
gate, causal gate, order rule, stopping rule, record floor, and submission rule
from:

```text
experiments/laguna-s-2.1-xpu-b70/notes/
  2026-07-24-m8-breakable-graph-formal-crossover-preregistration.md
```

The first root stopped after A1 because its idle-helper import created a Python
bytecode cache in the main worktree; B1 then rejected the dirty tree before
creating a run directory or starting a service. That root is sealed,
incomplete, and ineligible:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-formal-graph-crossover-d0960da7e-0ce373a31-20260724T215010Z
```

No output or timing from that root may be reused. This is a complete new
A1/B1/B2/A2 campaign, not a continuation, rescue leg, or
performance-conditioned repeat.

## One permitted retry root

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-formal-graph-crossover-4b4b5dd9c-0ce373a31-20260724T220518Z
```

No second retry root, fifth leg, repeated leg, warmed service, or selected leg
is permitted.

## Frozen source and only tooling delta

- main tooling and failure ledger:
  `4b4b5dd9c81d7b85819d3c93d65cb1a1f69e4363`;
- vLLM:
  `0ce373a3115fb4498c5e7a041d4fc9212fd6b5ca`;
- XPU kernels:
  `4772f727590c51b72add79350b913d098cf67872`.

The only executable delta from the original preregistered campaign is:

```text
run_laguna_m8_formal_graph_crossover.sh:
  export PYTHONDONTWRITEBYTECODE=1

run_laguna_m8_formal_graph_crossover_leg.sh:
  export PYTHONDONTWRITEBYTECODE=1
```

This suppresses harness bytecode files. It does not change model execution,
service arguments, graph or eager treatment, kernel selectors, prompt order,
measurement, exactness, performance gates, or phase-stop behavior. The model
service already used the same setting plus private cache roots in the original
campaign.

## Frozen tooling hashes

```text
run_laguna_m8_formal_graph_crossover.sh
  aace363f95bab89bf90e65926cb4b8b6002b01d7697cc1ef52abc3a55d39a4df
run_laguna_m8_formal_graph_crossover_leg.sh
  757bcb9c9f1455f9de2d011a9ae6d169d0faea61ae4877b359d2d6236a0590d1
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

- both shell tools pass `bash -n`;
- analyzer tests: 8 passed;
- JSON failure ledger validates;
- direct idle-helper import with bytecode suppression created no
  `__pycache__`;
- independent read-only runner audit confirmed every planned Python
  invocation is covered and found no other planned repository writer;
- all three source worktrees are clean; and
- no service or generation ran after the stopped root while building and
  registering this retry.

Only a full analyzer `record_candidate` disposition from this exact new root
can authorize payload construction and an independent final submission audit.
