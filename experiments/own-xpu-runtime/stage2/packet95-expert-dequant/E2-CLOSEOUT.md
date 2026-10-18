# E2 effective-scale cache — arithmetic closeout

<!-- campaign-closeout -->

## Question and identity

Can sixteen exact FP32 IQ2 effective scales per 256-weight block fit the
packet90 expert layout's existing 30 GiB arenas? Gate/up only, IQ3 layer 2
and draft excluded; no model or GPU execution.

## Outcome

Full E2 is closed for no fit on both ranks, under the brief's explicit option.
Each eligible layer contains 6,553,600 blocks. Replacing E1's four-byte decoded
half with sixteen four-byte scales adds 60 bytes/block.

| Bytes/count | Rank 0 | Rank 1 |
| --- | ---: | ---: |
| IQ2 target layers | 23 | 24 |
| IQ2 blocks | 150,732,800 | 157,286,400 |
| Actual E1 arena headroom | 4,225,394,604 | 630,519,094 |
| E2 growth over E1 | 9,043,968,000 | 9,437,184,000 |
| Full E2 arena bytes | 37,030,828,116 | 41,018,919,626 |
| Excess over 30 GiB | 4,818,573,396 | 8,806,664,906 |
| Growth over production FP16 half | 9,345,433,600 | 9,751,756,800 |
| Maximum layers, E1 elsewhere | 10 | 1 |
| Maximum layers, production elsewhere | 11 | 2 |

Removing all eight redundant scale-nibble bytes/block still adds
7,838,105,600 / 8,178,892,800 bytes over E1: neither full rank fits.

## What worked

The exact calculation uses actual packet90 post-load censuses, not an estimated
weights total. [Machine-readable proof](evidence/e2-memory.json) pins both
censuses and [the calculation](e2_memory.py).

## What failed or remains uncertain

A bounded variant cannot honestly pin the hottest K layers: existing packet77
attribution samples only rank1 layers 24 and 27, not a complete layer ranking.
One or two layers cover only 1/24 or 2/24 of IQ2 gate/up on the critical rank.
No speed is inferred; the down-dequantization bound does not belong to this
IQ2-only design. Spending the time box on that narrow path is not justified.
No E2 code, seal or runnable queue row claims otherwise.

## Evidence and patches

`evidence/e2-memory.json`, packet90's `exp-halfcache-{0,1}-census.json.gz`, and
its production/E1 memory admissions. No rejected runtime patch was needed.

## When to revisit

A layout with substantially more critical-rank headroom, a smaller exact cache,
or a complete per-layer cost census showing a material bounded opportunity.
