# Qwen3.8 Q8 concurrency three/four: fast but not quality-qualified

Status: **diagnostic only; exact-token gate failed**.

The accepted, unchanged Qwen3.8 Q8 TP2 binary was tested with three and four
simultaneous cache-cold requests. This was a service scheduling experiment,
not a source or arithmetic change. Each request generated 256 tokens and was
compared with its own fixed-slot sequential oracle.

## Throughput

| Server / active requests | Aggregate conventional | Aggregate wall | Per request | Exact |
| --- | ---: | ---: | --- | ---: |
| true p3 / c3 | `77.211862` | `75.667707` | `25.7610`, `25.7390`, `25.7404` | 0/3 |
| p4 / c3 | `77.209323` | `75.752015` | `25.7375`, `25.7377`, `25.7380` | 0/3 |
| true p4 / c4 | `91.894621` | `91.035465` | `23.7651`, `23.7653`, `23.1514`, `23.7655` | 2/4 |

All cache counters were zero and there was no MTP, DFlash, speculation, prompt
reuse, or response reuse. The high aggregate rates are real diagnostics, but
they are not repository records because simultaneous execution changed greedy
token IDs. A true three-slot server produced the same divergent hash family as
three active requests in a four-slot server, so this is not merely unused-slot
state.

The c2 setting remains the highest locally qualified Q8 service lane at
`57.398122 tok/s` aggregate, with its deliberately narrow two-prompt evidence
boundary. Do not generalize that c2 result to arbitrary prompts until the
multi-column reduction/scheduling difference is resolved.

The generalized harness now accepts `--concurrency 1..4` and fails closed on
any token mismatch. Compact measurements are in
[`2026-08-16-q8-c3-c4-quality-rejected.json`](../data/2026-08-16-q8-c3-c4-quality-rejected.json).
