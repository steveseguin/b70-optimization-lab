# Packet 95: more sampler clips in flight (build, 2026-10-04)

Built offline. **Not launched.** R = `/mnt/fast-ai/bench-results/ltx25-baseline-20260913`.
No GPU was used. References: `stability-01-w93c-*`
([milestone](2026-10-04-milestone-window-baseline.md)). Background:
[94f results](2026-10-04-packet-94f-results.md). Spreading blocks over more cards
did not help with two clips in flight, because one clip's sampler work is a serial
chain. Throughput is clips in flight divided by chain time.

## In plain words

This packet lets a server run three or four clips through the sampler at once
instead of two. The number is chosen at launch (`LTX_SAMPLER_WORKERS` = 2, 3 or
4; 2 is today's setup). Each extra worker gets its own copy of every graph and
buffer on every card, exactly like the two existing workers. Nothing about the
arithmetic changes. Every clip is still checked byte for byte against the
references.

## Design

- **Worker count:** read once at import by the sampler node, allowlist 2/3/4.
  With 3 or 4 it raises the sampler stage's worker count. With 2 nothing
  changes. Recorded in sampler, freeze, pin and coverage receipts.
- **Sampler depth:** with N workers the timed arm keeps N clips in flight
  (prompt i submits clip i and emits clip i-N). New arm graphs
  `pipe-samp2-tsh-rep-wlean-s3` and `-s4` differ from `pipe-samp2-tsh-rep-wlean`
  only in the sampler node's depth (3, 4); the gate checks that. The fill is N
  sampler prompts plus 2 decode prompts.
- **Encode lookahead** stays at 2 with two encode workers: a window encode takes
  about 0.56 s against a stream interval of at least 0.7 s, so it keeps ahead.
- **Reaching every worker in the capture pass:** jobs can now be pinned to a
  named worker (`ltx_pipeline.submit(..., target=)`; workers take only their own
  or unpinned jobs). A new node `LTXSamplerPin` (graph `graphs/sampler-pin.json`)
  pins the next sampler job to worker k. It is allowed only before the freeze
  with the pipeline idle, and the sampler node uses the pin once. The capture
  pass sends one pinned prompt per worker, then coverage must hold for all N
  workers (`capture_coverage(..., expected=N)`).
- **Unchanged and per thread already:** graph groups keyed by (card, thread)
  for the sampler and the text encoder, capture streams and static buffers per
  thread, the noise lock, the patcher pin, ordered emission (`run_behind`
  collects by clip index), done markers, sentries, the lean memo (per thread and
  clip), the context sentry, the freeze, the self-check, and the post-freeze
  load rule.
- **Decode capacity:** two decode workers (xpu:3 native and the xpu:1 replica),
  about 1.74-2.0 s per job, so about 0.9-1.0 s per clip at best. Today's
  1.41 s is above that. If three or four sampler workers bring the sampler near
  1.0 s, decode becomes the limit. **A third decode worker is not in this
  packet:** the replica code is built around exactly two slots (native and
  xpu:1, alternating by clip index) and its own probe and allowlist. The only
  candidate card, xpu:2, is short of memory under the spread layouts. It is a
  separate change if 95 shows decode setting the pace.

## Memory: what one more sampler worker costs

Measured in 94f: when the second worker captured, xpu:0 grew by 2.1-2.7 GiB for
18-23 blocks. That is about **0.12 GiB per block per worker** for graph buffers
and pool share. Starting from the 94f freeze (two workers, free device memory
per card):

| Layout | Card | Blocks | Free, 2 workers | Per extra worker | Free, 3 workers | Free, 4 workers |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| two-way | xpu:0 | 23 | 2.82 | 2.76 | **0.06** | - |
| two-way | xpu:1 | 25 | 4.93 | 3.00 | **1.93** | - |
| two-way | xpu:2 / xpu:3 | 0 | 12.0 / 14.7 | 0 | 12.0 / 14.7 | |
| shard3-c | xpu:0 | 20 | 5.72 | 2.40 | 3.32 | **0.92** |
| shard3-c | xpu:1 | 20 | 9.79 | 2.40 | 7.39 | 4.99 |
| shard3-c | xpu:2 | 8 | 4.04 | 0.96 | 3.08 | 2.12 |
| shard3-c | xpu:3 | 0 | 14.9 | 0 | 14.9 | 14.9 |
| shard4-a | xpu:0 | 18 | 7.68 | 2.16 | 5.52 | 3.36 |
| shard4-a | xpu:1 | 18 | 11.73 | 2.16 | 9.57 | 7.41 |
| shard4-a | xpu:2 | 8 | 4.04 | 0.96 | 3.08 | 2.12 |
| shard4-a | xpu:3 | 4 | 10.69 | 0.48 | 10.21 | 9.73 |

Expected to fit the 2 GiB floor: **shard4-a with 3 and with 4 workers** (4 is
tight on xpu:2 at 2.1 GiB) and **shard3-c with 3**. Expected not to fit:
**two-way with 3** (xpu:0 and xpu:1 run out), and shard3-c with 4.

**Floor not met is a clean skip.** Before worker 2 or 3 captures, the runner
reads free memory per card from the coverage node. `worker-headroom-95.py`
requires the 2 GiB floor plus that worker's estimate, and also the room the
xpu:1 replica (1.8 GiB) and the VAEs' load onto xpu:3 (1.9 GiB) will still
take, because the capture pass runs before the decode probe. If any card is
short, the run stops before capturing anything for that worker, records it
(exit 18) and stops the server gracefully. The freeze still enforces the floor
at run time as well (exit 16). In the operator's order, two-way with 3 is
expected to end this way.

## Runner, per server: `scripts/run-campaign-95.sh <layout> <workers>`

text-window probe → serial capture pass (headroom check, pin worker k, one
prompt alone, wait; for k = 0..N-1) → coverage for N workers → decode probe →
freeze → post-freeze self-check (N+4 prompts of the timed arm, two clips
emitted) → placement probe (13 prompts, ten fixtures) → timed arm, 120 prompts,
against the w93c references → summary → graceful stop. The summary reports per
arm: clips verified and exact, interval median and mean (stalled intervals
excluded), encode/sampler/decode job medians, **sampler clips in flight
observed** (time-weighted mean and maximum, from each job's own span), and
compute-engine busy seconds per clip per card. The traps, submitted-job
tracking, stall tolerance and idle-state stop are the same as 94f.

Index bases: 244000 + 1000 x combination (capture pass base + 10k, self-check
+200, probe +400, timed +600):

| Combination | Base |
| --- | ---: |
| two-way w2 (control) | 244000 |
| two-way w3 | 245000 |
| shard4-a w3 | 246000 |
| shard4-a w4 | 247000 |
| shard3-c w3 | 248000 |
| two-way w4 / shard3-c w2 / shard3-c w4 / shard4-a w2 | 249000 / 250000 / 251000 / 252000 |

## Packet and gate

- `R/prepared-encoder-workers-95`, manifest
  `97c1b4172f66d009af7c88b0b3f0241d24df937ce56a43c27cee6b226b81a32d`. Run
  names `encoder-server-workers-95-<layout>-w<N>`.
- Gate (`--check-only`, 2026-10-04 17:57 UTC): rc 0 for the five planned run
  names without a receipt, and with `four-card-health-20261004T1730Z.json`.
- CPU tests: `test-packet95-workers-cpu.py` 6/6. It covers pinned jobs on 2/3/4
  workers, ordered emission with three and four workers finishing out of order,
  coverage for N workers, the env allowlist, the memory skip on the 94f figures,
  and agreement between generator, gate and runner. All packet 90c-94 tests, the
  dry run and the stall tests pass. Full lane sweep: 65 pass, the same 46 old
  failures.

## Launch (one server per combination, in this order)

```
R=/mnt/fast-ai/bench-results/ltx25-baseline-20260913
P=$R/prepared-encoder-workers-95
M=97c1b4172f66d009af7c88b0b3f0241d24df937ce56a43c27cee6b226b81a32d
# (L,N) in: (two-way,2) (two-way,3) (shard4-a,3) (shard4-a,4) (shard3-c,3)
nohup env --default-signal=INT LTX_BUSY_WINDOWS=0 LTX_SAMPLER_PLACEMENT=$L LTX_SAMPLER_WORKERS=$N /home/steve/.venvs/ltx25-baseline/bin/python -B $P/launch/serve-encoder.py --packet $P --manifest-sha256 $M --run-name encoder-server-workers-95-$L-w$N --health-receipt <fresh receipt> > $R/encoder-server-workers-95-$L-w$N.log 2>&1 &
nohup bash /home/steve/llm-optimizations/experiments/ltx25-b70/scripts/run-campaign-95.sh $L $N > $R/campaign-95-$L-w$N.log 2>&1 &
```

Wait for each runner to stop its server before the next launch.

## Unverified offline

- The per-worker memory cost is an estimate from one measurement per layout.
  The headroom check and the freeze decide at run time.
- Whether three or four clips actually overlap on the cards. Each card has one
  compute engine; more clips help only where cards were idle. The summary's
  clips-in-flight and per-card busy figures will show it.
- Decode capacity (about 0.9-1.0 s per clip) may cap the stream before the
  sampler does.
- Pinning reaches every worker by construction, but it is tested on CPU with
  stand-in jobs only.
