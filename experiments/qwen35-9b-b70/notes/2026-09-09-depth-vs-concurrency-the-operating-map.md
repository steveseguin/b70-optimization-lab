# Depth against concurrency: the operating map, and why it is not row count (2026-09-09)

Qwen3.5-9B W4A16, TP1, one B70 on `steve-b70s`. Three depth arms (`d1`, `d2`, plus `p0`'s depth-3
strict pair), each measuring its own MTP0 oracle and its own ladders on the same server pair,
`--require-output-identity`, two passes per rung, 128-token completions.

## Single-stream: the depth curve flattens at 2

| depth | pair (tok/s) | pair median | vs previous | gates |
| ---: | --- | ---: | ---: | --- |
| 0 | 64.152 / 64.158 / 64.158 / 64.155 / 64.164 / 64.159 | 64.157 | - | G1 12/12 x3 |
| 1 | 93.075 / 93.110 | 93.092 | +45.1% | G2, G3, G3 12/12 |
| 2 | 110.026 / 110.150 | 110.088 | +18.3% | G2, G3, G3 12/12 |
| 3 | 110.704 / 110.629 | 110.666 | **+0.53%** | G2, G3, G3 12/12 |

All four depths are lossless here. Depth 3 buys half a percent over depth 2 for an extra verify row
per sequence; on this host the published depth-3 default is not obviously the right operating point.

## Aggregate: depth is monotonically harmful once the batch is full

Warm-pass aggregate tok/s, and exact-vs-sequential-oracle counts:

| users | MTP0 | MTP1 | MTP2 |
| ---: | --- | --- | --- |
| 1 | 63.9 (1/1) | 95.6 (1/1) | 112.6 (1/1) |
| 8 | 431.5 (8/8) | 554.9 (8/8) | 595.8 (8/8) |
| 16 | 725.3 (16/16) | 905.0 (16/16) | 667.1 (16/16) |
| 32 | **1147.6 (32/32)** | 988.4 (31/32) | 877.6 (32/32, other pass 31/32) |
| 64 | **1206.0 (64/64)** | 1034.5 (61/64) | 909.4 (62/64) |

At 64 users, no speculation is **+16.6%** over depth 1 and **+32.6%** over depth 2, and it is the
only column that stays exact. Speculation is a latency lever, not a throughput lever: it wins ~72%
at one user and loses a third of aggregate throughput at 64.

## The operating map

- **One or a few sessions:** depth 2 (110.1 tok/s, lossless). Depth 3 adds 0.5% and a row.
- **Many sessions:** speculation **off** (1206 tok/s aggregate at 64 users, 64/64 exact).
- The crossover is between 8 and 16 users.

## Correction: this is not row count

An earlier reading of the `d1` ladder attributed the exactness break to total decode rows
(`users x (depth+1)`), on the grounds that 32 users at MTP1 is 64 rows. Three depths of data refute
it:

- MTP0 at 64 users is **64 rows and exact 64/64**; MTP1 at 32 users is also **64 rows and not
  exact**. Same row count, opposite outcome.
- MTP2 at 64 users is **192 rows** and diverges *less* (62/64) than MTP1 at **128 rows** (60-61/64).
  More rows, fewer divergences - the wrong direction for a row-count mechanism.

What survives is narrower and still useful: **speculation, not batch width, is what costs exactness
here.** Every no-speculation rung measured on this host is exact; every speculative rung at 32 users
and above is not. A plausible remaining mechanism is that divergence opportunities scale with the
number of verify steps rather than with rows, which would also explain why deeper drafts - fewer
verify steps for the same output length - diverge slightly less. That is a hypothesis, not a result.

`b1sn256` remains the discriminating experiment: if serialising the row-count-dependent norm changes
nothing on a speculative ladder, the norm is not the mechanism and the search moves to the verify
path itself.

## Caveats

First-pass aggregate figures are still warming (2 users: 104.5 then 217.6; 16 users: 598.0 then
667.1); the table uses pass 2. Aggregate throughput is scoped capacity evidence and is never a
single-user headline. The 16-user MTP2 rung is anomalously low against its own 8-user rung and wants
a repeat before it is quoted.
