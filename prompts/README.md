# Prompts And Canary Inputs

This folder stores prompts and prompt templates that are useful for quality
gates, reproducibility, and research orchestration.

## Existing Prompt Files

The current tracked prompt files are MiniMax raw canaries and long-context
quality smokes. They are intentionally simple and brittle: exact answers catch
runtime corruption that aggregate throughput cannot reveal.

Examples:

- `minimax-arithmetic-canary-raw.txt`
- `minimax-json-canary-raw.txt`
- `minimax-sort-canary-raw.txt`
- `minimax-long-context-quality-smoke.txt`

## Prompt Patterns That Worked

- Exact JSON canary: asks for one-line JSON with fixed keys and values.
- Deterministic sort/color canary: catches token order drift and speculative
  double-processing.
- Arithmetic exact-output canary: catches semantic drift hidden by fluent text.
- Long repeated context plus a specific final question: catches context and KV
  corruption.
- Identity-lock prompt for agents: forces comparison of run configs before
  interpreting performance.

The reusable agent prompts are documented in
[../docs/research-workflow-playbook.md](../docs/research-workflow-playbook.md).
