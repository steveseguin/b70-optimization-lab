# Qwen3.6 Spec Trace Replay

- trace: `data/qwen36-quark-int8-tp4-ngram5-nobonus-state-spec-jsonl-20260611.jsonl`
- rows: `4`
- malformed rows: `0`
- requests: `3`
- suppressed follow-up mismatches: `1`

| request | rows | drafts | accepted | rejected | suppressed rows | joined token case | follow-up mismatches |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| `chatcmpl-910ade65c5503c90-a467094e` | 2 | 10 | 5 | 5 | 1 | `` | 1 |
| `chatcmpl-ace7501683203c95-8b54df50` | 1 | 5 | 5 | 0 | 1 | `` | 0 |
| `chatcmpl-95cc14d95464d068-bca29e44` | 1 | 5 | 0 | 5 | 0 | `` | 0 |

## Suppressed Follow-Up Mismatches

- request `chatcmpl-910ade65c5503c90-a467094e` line `3` -> `4`:
  suppressed `83098` `_NEED` but next verifier token was `0` `!`

## Request Counter Transitions

| request | line | scheduled | accepted | rejected | computed delta | output-token delta | token delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `chatcmpl-910ade65c5503c90-a467094e` | 3 | 6 | 5 | 0 | 0 | 5 | 5 |
| `chatcmpl-910ade65c5503c90-a467094e` | 4 | 5 | 0 | 5 | -5 | 1 | 1 |
| `chatcmpl-ace7501683203c95-8b54df50` | 1 | 6 | 5 | 0 | 0 | 4 | 4 |
| `chatcmpl-95cc14d95464d068-bca29e44` | 2 | 6 | 0 | 5 | -5 | 1 | 1 |
