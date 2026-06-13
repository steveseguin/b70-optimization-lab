# Qwen3.6 Spec Trace Replay

- trace: `data/qwen36-quark-int8-tp4-oracle1-nobonus-cachefilter-keepcomputed-nograph-20260612d-spec-trace.jsonl`
- rows: `4`
- malformed rows: `0`
- requests: `2`
- suppressed follow-up mismatches: `2`
- suppressed schedule mismatches: `0`
- suppressed accept mismatches: `2`
- accounting mismatches: `2`

| request | rows | drafts | accepted | rejected | suppressed rows | joined token case | generated mismatches | schedule mismatches | accept mismatches | accounting mismatches |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| `cmpl-957211a127b2ee63-0-b5740812` | 2 | 2 | 1 | 1 | 1 | `` | 1 | 0 | 1 | 1 |
| `cmpl-b596fa8e2bd3b7c1-0-a8ba98ed` | 2 | 2 | 1 | 1 | 1 | `` | 1 | 0 | 1 | 1 |

## Suppressed Follow-Up Mismatches

- request `cmpl-957211a127b2ee63-0-b5740812` line `1` -> `2`:
  suppressed `27044` `None`, next scheduled `27044` `None`, next verifier token was `47193` `None`, next emitted `47193` `None`.
- request `cmpl-b596fa8e2bd3b7c1-0-a8ba98ed` line `3` -> `4`:
  suppressed `13` `None`, next scheduled `13` `None`, next verifier token was `78503` `None`, next emitted `78503` `None`.

## Accounting Mismatches

- request `cmpl-957211a127b2ee63-0-b5740812` line `1`: expected computed delta `-1` from rejected `0` plus suppressed `1`, observed `0`.
- request `cmpl-b596fa8e2bd3b7c1-0-a8ba98ed` line `3`: expected computed delta `-1` from rejected `0` plus suppressed `1`, observed `0`.

## Request Counter Transitions

| request | line | scheduled | accepted | rejected | computed delta | output-token delta | token delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `cmpl-957211a127b2ee63-0-b5740812` | 1 | 2 | 1 | 0 | 0 | 1 | 1 |
| `cmpl-957211a127b2ee63-0-b5740812` | 2 | 1 | 0 | 1 | -1 | 1 | 1 |
| `cmpl-b596fa8e2bd3b7c1-0-a8ba98ed` | 3 | 2 | 1 | 0 | 0 | 1 | 1 |
| `cmpl-b596fa8e2bd3b7c1-0-a8ba98ed` | 4 | 1 | 0 | 1 | -1 | 1 | 1 |

Post-output `computed_minus_tokens` is included in the JSON rows.
Values below zero usually mean the next pass may recompute an already
emitted token; values above zero after suppressing a bonus can mean stale
unemitted KV stayed live.
