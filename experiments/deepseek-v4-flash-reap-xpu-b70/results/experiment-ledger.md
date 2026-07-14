# DeepSeek V4 REAP/XPU Experiment Ledger

Preserve every meaningful attempt, including failures.

| Date | Label | Status | Evidence | Decision |
| --- | --- | --- | --- | --- |
| 2026-07-13 | investment-red-team | complete | `../data/fit-audit-20260713.json`, `../../../plans/2026-07-13-deepseek-v4-flash-b70-investment-gated-plan.md` | Strategic go; reject direct K180 commitment. Run Stages 0-3.5 before download, build K160 first, and climb only after quality/warm-memory gates. |

## Entry Template

```md
## YYYY-MM-DD label

- Stage:
- Status: `failed|passed|rejected|promoted|inconclusive`
- Source/model/manifest revisions:
- vLLM/XPU-kernel commits and diffs:
- Command and environment:
- Hardware/topology:
- Result and profile paths:
- Correctness/quality artifacts:
- Memory/backend/graph trace:
- Decision and next gate:
```
