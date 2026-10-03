# Packet 90c, timed arm: 117/117 exact, clean stop, and the sampler cards are idle more than half the time (2026-10-03)

First GPU campaign since 2026-09-21, and the first on this host with the
faulty memory fenced (memory blocks 53-57 offline, the remaining 99 GiB
tested clean; see the
[host review](2026-10-03-host-forensics-and-catch-up.md)).

## Identity

- Packet `prepared-encoder-busy-90c`, manifest
  `80559bde4971229ab0a2ce927ab412ae1a2ca5fde5494abdef5f1da801a22be7`
  (packet 90 sentries + per-card busy-window timers + decode vae/save split;
  [build note](2026-10-03-packet-90b-build.md)).
- Server `encoder-server-busy-90c`, launched 20:25:17 UTC, boot 6ddb73fa,
  kernel 7.0.0-34, GuC 70.44.1, cpuidle state2 disabled, MemTotal 115.6 GiB.
- Runner `scripts/run-campaign-90c.sh timed`: warm 3 @206989, endure 120
  @207089, arm `pipe-samp2-tsh`. Receipts in `data/busy-90c/`.

## Result

| Measure | Value |
| --- | --- |
| Distinct clips verified | **117 of 117 bitwise exact** (120 prompts, 3 pipeline fills), `all_exact: true` |
| Wrong or non-finite clips | 0; all sentries passed |
| Faults | none: no `xe` fault, no lockup, no FAULT latch |
| Stop | quiescence proven by queue + done markers, one SIGINT, server exited in 10 s (first run of the new stop path) |
| Interval per distinct clip | median 1.776 s, mean 1.880, p95 2.898, min 1.301, max 3.691 (n=116) |
| Effective rate | 13.3 fps by the mean interval |

The interval is slower than f90's median 1.597 s (mean 1.684). The cause is
not separated: candidates are the new timers and done-marker writes, and a
host with 10 GiB less memory (17 GiB free during the run). The timers-off
control arm on the same packet decides it.

Eleven intervals exceeded 2.5 s (3.15, 2.56, 3.69, 3.21, 2.89, 3.06, 2.90,
3.04, 2.96, 2.88, 2.59), the same every-7-to-10-clips spike pattern seen
since packet 74.

## Busy windows: the measurement packet 90 was built for

`scripts/analyze-phases.py <run> f90c-endure`, 116 steady receipts:

| Card | Busy (union) | Span | Occupancy | Co-run overlap |
| --- | ---: | ---: | ---: | ---: |
| xpu:0 | 88.6 s | 216.6 s | **40.9 %** | 1.2 % |
| xpu:1 | 96.9 s | 216.4 s | **44.8 %** | 4.8 % |

Per-route windows are 3.2-3.6 ms each. Per clip that is about 0.76 s of
sampler work on xpu:0 and 0.84 s on xpu:1.

Sampler job wall (one clip): median 2.780 s; stage A 1.760, stage B 0.918,
upsample 0.043. With two clips in flight that is about 1.39 s per clip of
sampler capacity.

Decode job: median **1.778 s** (VAE decode + audio 1.630, MP4 preview save
0.145, 8.2 % of the job).

## Reading

1. This is the design note's **"GPU-ms much less than wall"** branch. The two
   sampler cards are idle 55-59 % of the time and the two clips almost never
   overlap on a card, so the sampler is limited by how fast the host issues
   work (two Python threads sharing one interpreter lock), not by the cards.
   Card contention between the two clips, the previous leading hypothesis for
   the 0.7 s/pair packing loss, is refuted by the 1-5 % overlap.
2. The stream was paced by **decode**, not the sampler: the decode job median
   (1.778 s) equals the stream interval median (1.776 s), while the sampler
   could deliver a clip every 1.39 s. Decode runs alone at about 0.71 s (f84)
   and is 2.3x slower here because xpu:3 also carries the text-encoder shard.
3. The MP4 save is only 0.145 s of the decode job. Moving it off the worker
   is worth doing but small.

Caveat: this is the first run of the busy-window timers on real hardware.
The occupancy figure rests on XPU event timestamps taken around each graph
replay; it is consistent with the per-route window times and the block count,
but nothing independent has cross-checked it yet.

## Next

1. Control arm (same packet, `LTX_BUSY_WINDOWS=0`): timer cost, a second
   117-clip exactness sample, and a second launch/stop cycle on fenced memory.
2. Packet 91: move decode capacity onto the idle sampler cards. xpu:1 holds
   19.3 GB of shard and is 55 % idle; the two VAEs are 1.84 GB. A VAE replica
   on xpu:1 (and a second decode worker) needs one probe first: cross-card
   VAE decode must be byte-identical to the xpu:3 references.
3. Then the sampler's host-side issuance: a 24 fps sampler needs about
   1.04 s per clip, and the cards already do a clip's work in 0.76-0.84 s
   each, so the headroom is in the dispatch path (one process per card, or
   fewer, larger graph replays), not in the kernels.

Placement at the time (from the sampler receipt): xpu:0 LTXAV 22.7 GB +
upsampler 1.0 GB; xpu:1 transformer shard 19.3 GB; xpu:2 text encoder
15.3 GB; xpu:3 text shard 10.9 GB + video VAE 1.47 GB + audio VAE 0.36 GB.

## Control arm (timers off), 20:42-20:53 UTC

Server `encoder-server-busy-90c-ctl`, same packet, `LTX_BUSY_WINDOWS=0`
(sentries and done markers on), launched five minutes after the timed
server's stop; runner `run-campaign-90c.sh control`, warm 3 @207389, endure
120 @207489; receipts in `data/busy-90c-ctl/`.

| Measure | Timed arm | Control arm |
| --- | ---: | ---: |
| Distinct clips exact | 117/117 | 117/117 |
| Interval median | 1.776 s | **1.581 s** |
| Interval mean | 1.880 s | 1.663 s |
| Interval p95 | 2.898 s | 2.483 s |
| Intervals over 2.5 s | 11 | 6 |
| Sampler job median | 2.780 s | 2.556 s |
| Stage A / stage B median | 1.760 / 0.918 s | 1.631 / 0.822 s |
| Decode job median | 1.778 s | 1.590 s |
| VAE decode + audio / MP4 save | 1.630 / 0.145 s | 1.445 / 0.136 s |

- The control matches f90 (median 1.597, mean 1.684), so fencing 10 GiB of
  host memory cost nothing and **the busy-window timers cost about 0.2 s per
  clip (12 %)**. They stay a diagnostic, off by default in any speed arm.
  Occupancy was therefore measured in a perturbed run; the same GPU work in
  the control's shorter wall would be roughly 48 % and 53 %, still about
  half idle.
- Decode paces the control too: decode job median 1.590 s against a stream
  median of 1.581 s.
- Second clean launch, run and proven-quiescence stop on this boot; no `xe`
  fault, no lockup.
- 234 of 234 clips exact across the two servers. The wrong-clip rate before
  was about one per 100-120 clips, and packet 90 also ran 101 clean with the
  bad memory in use, so this does not yet show that the wrong-clip bug was
  the memory fault.
