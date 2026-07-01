# Qwen3.6 Spec Trace Summary

## Trace: `/home/steve/llm-optimizations/data/qwen36-eagle1-corpus-trained-oracleflags-nopreemptdraft-tp2-20260618a-spec-trace.jsonl`

- rows `94`, requests `2`, drafts `94`, accepted `8`, rejected `86`, accept rate `8.51%`
- full accept rows `8` (`8.51%`), full reject rows `86` (`91.49%`)
- suppressed bonus rows `0` (`0.00%`)
- max full-accept streak `1`
- repeated scheduled rows `0`

| top request | drafts | accepted | rejected | accept rate | max full-accept streak |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cmpl-a6ca671bbcd19b99-0-a1c7a87b` | 63 | 4 | 59 | 6.35% | 1 |
| `cmpl-9a8dd5158da33837-0-a8bf1364` | 31 | 4 | 27 | 12.90% | 1 |

## Metric Artifacts

| label | preset | corrected tok/s | output tokens | request IDs | timestamps |
| --- | --- | ---: | --- | --- | --- |
| `qwen36-eagle1-corpus-trained-oracleflags-nopreemptdraft-naturalchat-tp2-20260618a-measure` | `natural-chat` | 0.69 | [64] | True | True |

## Joinability

- exact request-id join possible: `True`
- exact request-id matches: `0`
- prefix request-id matches: `1`
- timestamp-window join possible: `True`
- note: Trace rows can be joined to artifacts by request-id prefix; scheduler ids append an internal suffix.
