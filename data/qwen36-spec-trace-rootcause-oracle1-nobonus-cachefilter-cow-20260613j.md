# Qwen3.6 Spec Trace Replay

- trace: `data/qwen36-quark-int8-tp4-oracle1-nobonus-cachefilter-cow-20260613j-spec-trace.jsonl`
- rows: `6`
- malformed rows: `0`
- requests: `2`
- suppressed follow-up mismatches: `2`
- suppressed schedule mismatches: `0`
- suppressed accept mismatches: `2`
- accounting mismatches: `0`

| request | rows | drafts | accepted | rejected | suppressed rows | joined token case | generated mismatches | schedule mismatches | accept mismatches | accounting mismatches |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| `cmpl-98526fea36905b9e-0-94b89b12` | 3 | 3 | 2 | 1 | 2 | `` | 1 | 0 | 1 | 0 |
| `cmpl-80ff2925311dc22c-0-98059a90` | 3 | 3 | 2 | 1 | 2 | `` | 1 | 0 | 1 | 0 |

## Suppressed Follow-Up Mismatches

- request `cmpl-98526fea36905b9e-0-94b89b12` line `2` -> `3`:
  suppressed `47193` `None`, next scheduled `47193` `None`, next verifier token was `27044` `None`, next emitted `27044` `None`.
- request `cmpl-80ff2925311dc22c-0-98059a90` line `5` -> `6`:
  suppressed `78503` `None`, next scheduled `78503` `None`, next verifier token was `271` `None`, next emitted `271` `None`.

## Request Counter Transitions

| request | line | scheduled | accepted | rejected | computed delta | output-token delta | token delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `cmpl-98526fea36905b9e-0-94b89b12` | 1 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-98526fea36905b9e-0-94b89b12` | 2 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-98526fea36905b9e-0-94b89b12` | 3 | 2 | 0 | 1 | -1 | 1 | 1 |
| `cmpl-80ff2925311dc22c-0-98059a90` | 4 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-80ff2925311dc22c-0-98059a90` | 5 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-80ff2925311dc22c-0-98059a90` | 6 | 2 | 0 | 1 | -1 | 1 | 1 |

Post-output `computed_minus_tokens` is included in the JSON rows.
Values below zero usually mean the next pass may recompute an already
emitted token; values above zero after suppressing a bonus can mean stale
unemitted KV stayed live.
