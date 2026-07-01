# Qwen3.6 Spec Trace Summary

## Trace: `/home/steve/llm-optimizations/data/qwen36-eagle1-corpus-trained-normalgdn-tp2-20260618a-spec-trace.jsonl`

- rows `48`, requests `2`, drafts `48`, accepted `14`, rejected `34`, accept rate `29.17%`
- full accept rows `14` (`29.17%`), full reject rows `34` (`70.83%`)
- suppressed bonus rows `0` (`0.00%`)
- max full-accept streak `2`
- repeated scheduled rows `0`

| top request | drafts | accepted | rejected | accept rate | max full-accept streak |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cmpl-bb60f65127c4adb0-0-bb0c1660` | 24 | 7 | 17 | 29.17% | 2 |
| `cmpl-97f6c30cbbfdd3fd-0-87a85cc4` | 24 | 7 | 17 | 29.17% | 2 |

## Metric Artifacts

| label | preset | corrected tok/s | output tokens | request IDs | timestamps |
| --- | --- | ---: | --- | --- | --- |
| `qwen36-eagle1-corpus-trained-normalgdn-naturalchat32-tp2-20260618a-measure` | `natural-chat` | 0.96 | [32] | True | True |

## Joinability

- exact request-id join possible: `True`
- exact request-id matches: `0`
- prefix request-id matches: `1`
- timestamp-window join possible: `True`
- note: Trace rows can be joined to artifacts by request-id prefix; scheduler ids append an internal suffix.
