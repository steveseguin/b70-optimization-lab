# Experiment Ledger

Record every attempt here. Keep failed runs because they define the next patch.

| Date | Label | Status | Shape | Config | Output tok/s | Total tok/s | Artifacts | Decision |
| --- | --- | --- | --- | --- | ---: | ---: | --- | --- |
| 2026-05-31 | metadata-capture | complete | n/a | HF API/config/card | n/a | n/a | `notes/2026-05-31-initial-brief.md` | Use as initial target |
| 2026-05-31 | deployment-fit-check | rejected | n/a | HF file metadata, 4x B70 VRAM budget | n/a | n/a | `notes/2026-05-31-deployment-decision.md` | Do not download/deploy; 142.44 GiB weights exceed 4x32GB full-resident budget and card says vLLM/SGLang not currently supported |

## Entry Template

```md
## YYYY-MM-DD label

- Status: `smoke_failed|smoke_passed|quality_failed|quality_passed|submitted|rejected`
- Model revision:
- vLLM git commit and diff snapshot:
- Command:
- Env:
- Shape:
- Result JSON:
- Log:
- Quality artifacts:
- LocalMaxxing payload:
- LocalMaxxing response:
- Notes:
- Decision:
```

## Submission Threshold

Do not submit a record to LocalMaxxing until:

- at least one quality gate passes;
- output tokens/s is a meaningful improvement or a useful first public baseline;
- the payload includes XPU/Level Zero details in `engineFlags.extraFlags`;
- a response is archived under `localmaxxing/` or repo `data/`;
- the row is added to `localmaxxing-submissions.md` or an equivalent local ledger.
