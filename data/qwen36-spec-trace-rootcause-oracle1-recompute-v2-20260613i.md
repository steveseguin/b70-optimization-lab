# Qwen3.6 Spec Trace Replay

- trace: `data/qwen36-quark-int8-tp4-oracle1-nobonus-recompute-nograph-20260612f-spec-trace.jsonl`
- rows: `20`
- malformed rows: `0`
- requests: `2`
- suppressed follow-up mismatches: `18`
- suppressed schedule mismatches: `18`
- suppressed accept mismatches: `18`
- accounting mismatches: `0`

| request | rows | drafts | accepted | rejected | suppressed rows | joined token case | generated mismatches | schedule mismatches | accept mismatches | accounting mismatches |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| `cmpl-8eb9a875b154b7f6-0-aedc5e55` | 13 | 13 | 12 | 1 | 12 | `` | 12 | 12 | 12 | 0 |
| `cmpl-afca347990bfd32e-0-996685b4` | 7 | 7 | 7 | 0 | 7 | `` | 6 | 6 | 6 | 0 |

## Suppressed Follow-Up Mismatches

- request `cmpl-8eb9a875b154b7f6-0-aedc5e55` line `1` -> `2`:
  suppressed `27044` `None`, next scheduled `47193` `None`, next verifier token was `47193` `None`, next emitted `47193` `None`.
- request `cmpl-8eb9a875b154b7f6-0-aedc5e55` line `2` -> `3`:
  suppressed `14246` `None`, next scheduled `8129` `None`, next verifier token was `8129` `None`, next emitted `8129` `None`.
- request `cmpl-8eb9a875b154b7f6-0-aedc5e55` line `3` -> `4`:
  suppressed `13` `None`, next scheduled `24985` `None`, next verifier token was `24985` `None`, next emitted `24985` `None`.
- request `cmpl-8eb9a875b154b7f6-0-aedc5e55` line `4` -> `5`:
  suppressed `383` `None`, next scheduled `3074` `None`, next verifier token was `3074` `None`, next emitted `3074` `None`.
- request `cmpl-8eb9a875b154b7f6-0-aedc5e55` line `5` -> `6`:
  suppressed `43318` `None`, next scheduled `16401` `None`, next verifier token was `16401` `None`, next emitted `16401` `None`.
- request `cmpl-8eb9a875b154b7f6-0-aedc5e55` line `6` -> `7`:
  suppressed `4478` `None`, next scheduled `11` `None`, next verifier token was `11` `None`, next emitted `11` `None`.
- request `cmpl-8eb9a875b154b7f6-0-aedc5e55` line `7` -> `8`:
  suppressed `29541` `None`, next scheduled `6044` `None`, next verifier token was `6044` `None`, next emitted `6044` `None`.
- request `cmpl-8eb9a875b154b7f6-0-aedc5e55` line `8` -> `9`:
  suppressed `11` `None`, next scheduled `321` `None`, next verifier token was `321` `None`, next emitted `321` `None`.
- request `cmpl-8eb9a875b154b7f6-0-aedc5e55` line `9` -> `10`:
  suppressed `874` `None`, next scheduled `4131` `None`, next verifier token was `4131` `None`, next emitted `4131` `None`.
- request `cmpl-8eb9a875b154b7f6-0-aedc5e55` line `10` -> `11`:
  suppressed `4557` `None`, next scheduled `13` `None`, next verifier token was `13` `None`, next emitted `13` `None`.
- request `cmpl-8eb9a875b154b7f6-0-aedc5e55` line `11` -> `12`:
  suppressed `198` `None`, next scheduled `22791` `None`, next verifier token was `22791` `None`, next emitted `22791` `None`.
- request `cmpl-8eb9a875b154b7f6-0-aedc5e55` line `12` -> `13`:
  suppressed `440` `None`, next scheduled `829` `None`, next verifier token was `4779` `None`, next emitted `4779` `None`.
- request `cmpl-afca347990bfd32e-0-996685b4` line `14` -> `15`:
  suppressed `13` `None`, next scheduled `78503` `None`, next verifier token was `78503` `None`, next emitted `78503` `None`.
- request `cmpl-afca347990bfd32e-0-996685b4` line `15` -> `16`:
  suppressed `4581` `None`, next scheduled `2468` `None`, next verifier token was `2468` `None`, next emitted `2468` `None`.
- request `cmpl-afca347990bfd32e-0-996685b4` line `16` -> `17`:
  suppressed `1345` `None`, next scheduled `28043` `None`, next verifier token was `28043` `None`, next emitted `28043` `None`.
- request `cmpl-afca347990bfd32e-0-996685b4` line `17` -> `18`:
  suppressed `7072` `None`, next scheduled `3817` `None`, next verifier token was `3817` `None`, next emitted `3817` `None`.
- request `cmpl-afca347990bfd32e-0-996685b4` line `18` -> `19`:
  suppressed `17856` `None`, next scheduled `13` `None`, next verifier token was `13` `None`, next emitted `13` `None`.
- request `cmpl-afca347990bfd32e-0-996685b4` line `19` -> `20`:
  suppressed `15153` `None`, next scheduled `1543` `None`, next verifier token was `1543` `None`, next emitted `1543` `None`.

## Request Counter Transitions

| request | line | scheduled | accepted | rejected | computed delta | output-token delta | token delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `cmpl-8eb9a875b154b7f6-0-aedc5e55` | 1 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-8eb9a875b154b7f6-0-aedc5e55` | 2 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-8eb9a875b154b7f6-0-aedc5e55` | 3 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-8eb9a875b154b7f6-0-aedc5e55` | 4 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-8eb9a875b154b7f6-0-aedc5e55` | 5 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-8eb9a875b154b7f6-0-aedc5e55` | 6 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-8eb9a875b154b7f6-0-aedc5e55` | 7 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-8eb9a875b154b7f6-0-aedc5e55` | 8 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-8eb9a875b154b7f6-0-aedc5e55` | 9 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-8eb9a875b154b7f6-0-aedc5e55` | 10 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-8eb9a875b154b7f6-0-aedc5e55` | 11 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-8eb9a875b154b7f6-0-aedc5e55` | 12 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-8eb9a875b154b7f6-0-aedc5e55` | 13 | 2 | 0 | 1 | -1 | 1 | 1 |
| `cmpl-afca347990bfd32e-0-996685b4` | 14 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-afca347990bfd32e-0-996685b4` | 15 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-afca347990bfd32e-0-996685b4` | 16 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-afca347990bfd32e-0-996685b4` | 17 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-afca347990bfd32e-0-996685b4` | 18 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-afca347990bfd32e-0-996685b4` | 19 | 2 | 1 | 0 | -1 | 1 | 1 |
| `cmpl-afca347990bfd32e-0-996685b4` | 20 | 2 | 1 | 0 | -1 | 1 | 1 |

Post-output `computed_minus_tokens` is included in the JSON rows.
Values below zero usually mean the next pass may recompute an already
emitted token; values above zero after suppressing a bonus can mean stale
unemitted KV stayed live.
