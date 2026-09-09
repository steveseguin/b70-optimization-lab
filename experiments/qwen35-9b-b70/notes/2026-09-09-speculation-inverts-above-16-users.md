# Speculation inverts above ~16 concurrent users, and costs exactness there too (2026-09-09)

Campaign `d1`, Qwen3.5-9B W4A16, TP1, one B70 on `steve-b70s`, MTP depth 1, both ladders measured on
the same server pair with `--require-output-identity`, two passes per rung, 128-token completions.

| users | rows (u x (d+1)) | MTP0 aggregate tok/s | MTP0 exact | MTP1 aggregate tok/s | MTP1 exact |
| ---: | ---: | ---: | --- | ---: | --- |
| 1 | 2 | 63.9 / 63.9 | 1/1 | 95.6 / 95.6 | 1/1 |
| 2 | 4 | 121.8 / 123.1 | 2/2 | 99.1 / 184.8 | 2/2 |
| 4 | 8 | 233.9 / 234.2 | 4/4 | 322.6 / 322.7 | 4/4 |
| 8 | 16 | 431.9 / 431.5 | 8/8 | 395.5 / 554.9 | 8/8 |
| 16 | 32 | 727.3 / 725.3 | 16/16 | 833.9 / 905.0 | 16/16 |
| 32 | 64 | 1149.8 / 1147.6 | **32/32** | 987.0 / 988.4 | **30/32, 31/32** |
| 64 | 128 | 1206.7 / 1206.0 | **64/64** | 1036.3 / 1034.5 | **60/64, 61/64** |

Harness exit codes carry the verdict: the MTP0 ladder returned 0 (`output-identity-qualified`), the
MTP1 ladder returned 4 (`output-isolation-qualified-shape-variant`) - identity was required and not
met.

## Two findings, and they point the same way

**1. Speculation inverts as a throughput lever.** Warm-pass deltas, MTP1 against MTP0:

```
 1 user  +49.6%    16 users  +24.8%
 2 users +50.1%    32 users  -13.9%
 4 users +37.8%    64 users  -14.2%
 8 users +28.6%
```

The crossover is between 16 and 32 users. Speculation buys single-stream latency and *loses*
aggregate throughput once the batch is full, because a verify step spends compute on drafts the
scheduler could have filled with real work. **For many concurrent sessions the right setting is
speculation off**; for one or a few sessions it is worth ~50%. This is not a tuning subtlety - it is
a 14% throughput penalty for leaving MTP on at scale.

**2. Speculation lowers the exactness ceiling from >=64 users to 16.** The published W4A16 ladder is
exact through 64 users, but it was measured *without speculation*; this is the missing half of that
table. The arithmetic fits the known mechanism: a verify step at depth `d` presents `d+1` rows per
sequence, so 32 users at MTP1 is 64 rows and 64 users is 128. The RMSNorm on this route is
row-count dependent and perturbs about 2-3% of rows once a batch reaches 16 - and 2-3% of 64 rows is
exactly the one-to-two requests per pass being lost here. **Users and depth are the same knob**,
which is why depth 4+ broke identity on the FP8 route for the same reason concurrency does.

## What this makes urgent

`b1sn256` moves to the front of the lever queue. If the mechanism is the norm's row-count
dependence, serialising that reduction with a threshold above 128 rows should restore exactness at
these rungs, and it was measured to cost nothing end to end (-0.2% to +0.6% at every rung, including
64 rows where the isolated reduction costs ~33x). Note the threshold matters: at its previous value
of 64 the knob is inert above 64 rows, which is precisely where this breaks.

The serialised norm's recorded negative does not apply here. That verdict was measured on **two
cards** against the collective (0.7031% -> 0.5469%, n.s. over 1280 requests per arm). This is TP1,
where there is no collective and the residue is the norm itself.

## Caveat

Pass-to-pass aggregate variance is large at low concurrency on the first pass (2 users: 99.1 then
184.8; 8 users: 395.5 then 554.9) - the first pass is still warming. The deltas above use pass 2.
Aggregate figures are scoped capacity evidence and are never a single-user headline.
