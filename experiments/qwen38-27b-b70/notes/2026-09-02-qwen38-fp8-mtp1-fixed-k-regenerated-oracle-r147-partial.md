# Qwen3.8 FP8 TP2 fixed-K image with a regenerated same-image oracle, R147 (partial)

Date: 2026-09-02

Status: **three of five servers complete; identity gates G1 and G3(a) passed;
campaign stopped by a copy-engine fault on `0000:e3:00.0` during the fourth
server's weight staging. Nothing promoted. Remaining: mtp1-b, the 100-300-token
repeat probe, and the c1-c64 identity ladder, on a fresh boot.**

R147 re-ran the R139 row-invariant fixed-K W8A16 image on the 18:23 clean boot
under the CR1 rule: the c1 oracle is regenerated from the same image instead of
the natural-kernel R54a oracle that R140 used. Preregistration:
[`r147-prereg`](../data/2026-09-02-qwen38-fp8-mtp1-fixed-k-regenerated-oracle-r147-prereg.json);
structured partial result:
[`r147-result`](../data/2026-09-02-qwen38-fp8-mtp1-fixed-k-regenerated-oracle-r147-result.json).

| server | role | class-balanced decode | identity | workload |
| --- | --- | ---: | --- | --- |
| mtp0-a | same-image MTP0 control, empty cache | `33.336950 tok/s` | oracle | 12 rows, cache zero, canaries before/after |
| mtp0-b | second same-image MTP0 control, empty cache | `33.313729 tok/s` | **12/12 vs mtp0-a (G1)** | same |
| mtp1-a | R62 draft-INT4 treatment on R139, empty cache | `54.312987 tok/s` | **12/12 vs mtp0-a (G3)**; FP16-verifier marker on both ranks | same |
| mtp1-b | second MTP1 attempt | not reached | | GPU fault at weight staging |

Information only: mtp0-a and mtp1-a each match the frozen natural R54a oracle
on 8/12 arrays, diverging first at output tokens 160, 392, 400, and 479 of
512. That is the expected late near-tie behaviour of a changed reduction order
and is exactly why the oracle must be regenerated for an invariant kernel.

What this establishes so far:

- The invariant kernel is repeat-exact at c1 across two independently compiled
  servers (G1), which the natural kernel also is at these prompt lengths.
- MTP1 on the invariant kernel equals same-image MTP0 12/12 (G3 for attempt a),
  so speculative decoding remains lossless on this image.
- The R140 throughput rejection was noise: mtp1-a measured `54.312987 tok/s`,
  `0.205%` under the R119 center and above the `53.88` per-attempt floor. The
  same-image MTP0 controls sit `1.21%` under the natural-kernel R54 controls,
  so the kernel's real cost is about one percent at MTP0 and within noise at
  MTP1.

What it does not yet establish: c2 through c64 identity (G6) and 168-256-token
repeat determinism at the endpoint (G5). Those were the point of the campaign
and need the remaining two servers.

## Infrastructure event

At `19:18:55`, one minute fifty seconds after mtp1-b launched, `xe
0000:e3:00.0` logged 34 `Fault response: Unsuccessful -EINVAL` lines on the
`bcs` copy engine, engine-memory CAT errors, one `bcs` engine reset, and a
device coredump. Rank 1 spun at 100% CPU; the server never logged past the
mamba page-size step. `docker stop -t 180` timed out and the container was
killed. Afterwards both B70s reported `normal`, per-card compute and the
two-card XCCL all-reduce passed, and the journal stayed quiet. This is the
third copy-engine fault during weight staging in two days on this host
(R116 attempt 1 on `03:00.0`, R118 candidate2 and now R147 mtp1-b on
`e3:00.0`), all on the first minutes of a fresh container. Per the standing
rule, no further model launch on this boot until the Xe driver is reloaded or
the host rebooted. Evidence:
`/mnt/fast-ai/bench-results/qwen38-fp8-fixed-k-regenerated-oracle-20260902-r147/`
(`mtp1-b-kernel-journal.txt`, `mtp1-b/server.log`, `ABORTED`).

## Next

Resume on a fresh boot with the same runner from the mtp1-b stage (mtp1-b,
probe, ladder), keeping mtp0-a as the oracle; the runner refuses to reuse the
artifact root, so resume into a sibling root and compare against
`mtp0-a/strict` by path.
