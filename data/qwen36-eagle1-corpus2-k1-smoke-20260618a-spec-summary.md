# Qwen3.6 Spec Trace Summary

## Trace: `/home/steve/llm-optimizations/data/qwen36-eagle1-corpus2-k1-smoke-20260618a-spec.jsonl`

- rows `206`, requests `3`, drafts `206`, accepted `80`, rejected `126`, accept rate `38.83%`
- full accept rows `80` (`38.83%`), full reject rows `126` (`61.17%`)
- suppressed bonus rows `0` (`0.00%`)
- max full-accept streak `12`
- repeated scheduled rows `0`

| top request | drafts | accepted | rejected | accept rate | max full-accept streak |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cmpl-b077c6c21a0d6fb9-0-a5a991a5` | 91 | 36 | 55 | 39.56% | 12 |
| `cmpl-9e326337755ff4b6-0-8531e270` | 91 | 36 | 55 | 39.56% | 12 |
| `cmpl-9ef7c69ccfcda712-0-8eac87f0` | 24 | 8 | 16 | 33.33% | 5 |

## Metric Artifacts

| label | preset | corrected tok/s | output tokens | request IDs | timestamps |
| --- | --- | ---: | --- | --- | --- |
| `qwen36-ablation-eagle1-corpus2-fastpath-piecewise-tp2-k1-smoke-20260618a-p512o512-20260618104300` | `natural-chat` | 46.28 | [128, 128] | True | True |

## Joinability

- exact request-id join possible: `True`
- exact request-id matches: `0`
- prefix request-id matches: `2`
- timestamp-window join possible: `True`
- note: Trace rows can be joined to artifacts by request-id prefix; scheduler ids append an internal suffix.
