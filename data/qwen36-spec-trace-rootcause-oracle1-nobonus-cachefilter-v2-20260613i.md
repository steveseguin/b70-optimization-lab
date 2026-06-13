# Qwen3.6 Spec Trace Replay

- trace: `data/qwen36-quark-int8-tp4-oracle1-nobonus-cachefilter-nograph-20260612c-spec-trace.jsonl`
- rows: `6`
- malformed rows: `0`
- requests: `2`
- suppressed follow-up mismatches: `2`
- suppressed schedule mismatches: `0`
- suppressed accept mismatches: `2`
- accounting mismatches: `0`

| request | rows | drafts | accepted | rejected | suppressed rows | joined token case | generated mismatches | schedule mismatches | accept mismatches | accounting mismatches |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| `cmpl-ba8c478f4f2900cd-0-b3ac4dd6` | 3 | 3 | 2 | 1 | 2 | `` | 1 | 0 | 1 | 0 |
| `cmpl-934a595531882a8f-0-bc7342d5` | 3 | 3 | 2 | 1 | 2 | `` | 1 | 0 | 1 | 0 |

## Suppressed Follow-Up Mismatches

- request `cmpl-ba8c478f4f2900cd-0-b3ac4dd6` line `2` -> `3`:
  suppressed `47193` `None`, next scheduled `47193` `None`, next verifier token was `27044` `None`, next emitted `27044` `None`.
- request `cmpl-934a595531882a8f-0-bc7342d5` line `5` -> `6`:
  suppressed `78503` `None`, next scheduled `78503` `None`, next verifier token was `271` `None`, next emitted `271` `None`.

## Request Counter Transitions

| request | line | scheduled | accepted | rejected | computed delta | output-token delta | token delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `cmpl-ba8c478f4f2900cd-0-b3ac4dd6` | 1 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-ba8c478f4f2900cd-0-b3ac4dd6` | 2 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-ba8c478f4f2900cd-0-b3ac4dd6` | 3 | 2 | 0 | 1 | -1 | 1 | 1 |
| `cmpl-934a595531882a8f-0-bc7342d5` | 4 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-934a595531882a8f-0-bc7342d5` | 5 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-934a595531882a8f-0-bc7342d5` | 6 | 2 | 0 | 1 | -1 | 1 | 1 |

Post-output `computed_minus_tokens` is included in the JSON rows.
Values below zero usually mean the next pass may recompute an already
emitted token; values above zero after suppressing a bonus can mean stale
unemitted KV stayed live.
