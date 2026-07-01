# Qwen3.6 Spec Trace Summary

## Trace: `/home/steve/llm-optimizations/data/qwen36-eagle2-tokenheavy-fusedbatch-nosafety-k1-smoke-20260618a-spec.jsonl`

- rows `191`, requests `3`, drafts `191`, accepted `95`, rejected `96`, accept rate `49.74%`
- full accept rows `95` (`49.74%`), full reject rows `96` (`50.26%`)
- suppressed bonus rows `0` (`0.00%`)
- max full-accept streak `14`
- repeated scheduled rows `0`

| top request | drafts | accepted | rejected | accept rate | max full-accept streak |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cmpl-ae2a370a5ba273d1-0-86650dc4` | 84 | 43 | 41 | 51.19% | 14 |
| `cmpl-a0da7f6bda63d2f0-0-a3b06ff6` | 84 | 43 | 41 | 51.19% | 14 |
| `cmpl-81bef4131bc95c5a-0-830cfde7` | 23 | 9 | 14 | 39.13% | 4 |

## Metric Artifacts

| label | preset | corrected tok/s | output tokens | request IDs | timestamps |
| --- | --- | ---: | --- | --- | --- |
| `qwen36-ablation-eagle2-tokenheavy-fusedbatch-nosafety-fastpath-piecewise-tp2-k1-smoke-20260618a-p512o512-20260618112916` | `natural-chat` | 57.92 | [128, 128] | True | True |

## Joinability

- exact request-id join possible: `True`
- exact request-id matches: `0`
- prefix request-id matches: `2`
- timestamp-window join possible: `True`
- note: Trace rows can be joined to artifacts by request-id prefix; scheduler ids append an internal suffix.
