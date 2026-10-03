# Packet 91b: the decode replica is exact and buys almost nothing; every stage slows when a worker is added (2026-10-03)

Server `encoder-server-decode-91b` (packet `prepared-encoder-decode-91b`,
manifest `c9ed69b73c641817983565dada5fc487bb38a9727fd623d064a721e014d0564e`,
`LTX_BUSY_WINDOWS=0`), launched 21:16 UTC on boot 6ddb73fa (kernel 7.0.0-34,
memory blocks 53-57 offline). Runner `scripts/run-campaign-91b.sh`: warm 3
@208489, probe, control 30 @208589, replica 120 @208689. Receipts in
`data/decode-91b/`. No fault, no lockup; proven-quiescence stop, server
exited in 10 s. Design and review history:
[build note](2026-10-03-packet-91-build.md).

## Result

| Measure | Control arm (decode on xpu:3) | Replica arm (xpu:3 + copy on xpu:1) |
| --- | ---: | ---: |
| Distinct clips exact | 27/27 | **116/116** |
| Interval median | 1.686 s | 1.637 s |
| Interval mean | 1.985 s (one 10.4 s gap) | **1.602 s** |
| Interval p95 | 2.933 s | 2.520 s |
| Sampler job median | 2.612 s | 2.956 s |
| Stage A / stage B median | 1.636 / 0.803 s | 1.923 / 0.857 s |
| Decode job median | 1.740 s (one worker) | 2.224 s per job, two in flight (native 2.210, replica 2.226) |
| Encode stage per job, median | 3.222 s | 3.130 s |

Probe: `replica-exact`, 10/10 fixtures byte-identical on xpu:1, on xpu:3 and
against the stored references; xpu:1 free memory 5.41 GiB after the copy and
3.41 GiB after the probe decodes (`mem_get_info`).

Against the timers-off 90c control earlier the same evening (median 1.581,
mean 1.663): the replica arm's mean is 3.7 % better and its median 3.5 %
worse. Within noise for one server; **no speed verdict**, and certainly no
step toward 1.042 s.

## Reading

1. **Cross-card VAE decode is bitwise exact**, and two decode workers with
   ordered emission stayed exact over 116 clips. That part is a clean result
   and the mechanism is reusable.
2. **Doubling decode capacity did not move the stream, because each stage got
   slower.** With a second decode worker the sampler job went from 2.61 to
   2.96 s (+13 %) and each decode from 1.74 to 2.22 s (+28 %). The replica
   decode on xpu:1 (a card the sampler uses about half the time) and the
   native decode on xpu:3 (shared with the text shard) slowed by the same
   amount. Different cards, different co-tenants, same slowdown: the shared
   resource is the host process, not a card.
3. Stage times alone versus pipelined, from this lane's own records: sampler
   about 1.98 s serial against 2.6-3.0 s pipelined; decode 0.71 s alone
   against 1.6-2.2 s; encode 1.59 s alone (one card, fp32) against 3.1-3.2 s
   per job with two workers. Every stage costs far more wall time when the
   others run in the same interpreter, while the 90c timers put the sampler
   cards at 41-45 % busy. The pipeline is bound by one Python process issuing
   work for seven threads, not by GPU time.
4. Encode now sets the pace in the replica arm: 3.13 s per job with two
   workers is 1.57 s per clip, against the stream's 1.60 s.

## What follows

The lever is no longer placement inside one process. It is giving each stage
its own interpreter: an encode process (xpu:2/xpu:3), a sampler process
(xpu:0/xpu:1) and a decode process, passing conditioning and latents between
them as bytes. If each stage ran at its stand-alone time, the stream would be
bounded by the two-clip sampler at roughly 1.0-1.1 s per clip, which is where
the September ceiling estimate (1.09 s) already pointed. That estimate is a
projection from stand-alone timings, not a measurement.

Not established: how much of the pipelined slowdown is interpreter-lock
contention and how much is card sharing (the encode workers share two cards);
whether two sampler threads in a process of their own reach their stand-alone
time; memory for three processes on a 115 GiB host.

Decoder graph capture, the other way to take decode's Python time off the
shared interpreter, stays ruled out for the reason recorded earlier
(`NADiffusionDecoder.forward` draws from a generator; a persistent axis cache
would be needed).
