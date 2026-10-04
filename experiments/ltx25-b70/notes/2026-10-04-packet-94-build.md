# Packet 94: spread the transformer over more cards (build, 2026-10-04)

Built offline. **Not launched.** R = `/mnt/fast-ai/bench-results/ltx25-baseline-20260913`.
No GPU was used to build or test it. Baseline and references: the short-window
encoder plus lean conditioning, `stability-01-w93c-*`
([milestone](2026-10-04-milestone-window-baseline.md)).

## In plain words

The two sampler cards (xpu:0, xpu:1) are full and xpu:2 is mostly idle. This
packet lets the 48 transformer blocks sit on three or four cards instead of
two. Each block still runs whole, in the same order, with the same weights; only
the card that holds it changes, so the clips must stay byte-identical to the
references, and the run checks that before it times anything.

The card layout is fixed when a server first loads the model, so **each layout
gets its own server launch** (three launches: control, then two candidates).
Switching layouts inside one running server would mean moving loaded weights
between cards under the model manager; that is not safe here.

## The split, from the 93c numbers

Inputs (`data/window-93c/summary.json`, receipts of `encoder-server-window-93c`
and `encoder-server-decode-91c`):

- One transformer block costs **0.0403 compute-seconds per clip**: xpu:1 holds
  25 blocks and nothing else in the 91c control arm and measured 1.008 s/clip.
- Fixed work per card besides blocks, in the 93c window+lean arm:
  xpu:0 0.31 s (1.24 minus 23 blocks: upsampler, connectors, glue);
  xpu:1 0.32 s (1.33 minus 25 blocks: the decode replica's half of the clips);
  xpu:2 0.40 s (first half of the text encoder);
  xpu:3 0.85 s (second half of the text encoder, the other half of the decodes).
- Memory per block: 0.72 GiB of bf16 weights (19.33 GB over 25 blocks) plus up
  to 0.25 GiB of graph buffers and pool share for the two sampler workers
  (90c: 24.24 GiB reserved against 18.0 GiB of weights). Planned at
  **0.97 GiB per block**.

Free memory today (device 31.89 GiB, peak reserved in 93c, about 0.5 GiB for
the driver) and after each layout:

| Card | Peak reserved 93c | Free now | Free, shard3-c (20/20/8/0) | Free, shard4-a (18/18/8/4) |
| --- | ---: | ---: | ---: | ---: |
| xpu:0 | 28.50 GiB | 2.9 | 5.8 | 7.7 |
| xpu:1 | 27.51 GiB | 3.9 | 8.7 | 10.7 |
| xpu:2 | 21.34 GiB (incl. window graphs) | 10.1 | **2.3** | **2.3** |
| xpu:3 | 17.35 GiB | 14.0 | 14.0 | 10.2 |

Memory caps xpu:2 at **8 blocks** (2 GiB floor); without that cap the balance
would want about 13 there. Predicted compute-seconds per clip (the busiest card
sets the pace):

| Layout | xpu:0 | xpu:1 | xpu:2 | xpu:3 | Busiest |
| --- | ---: | ---: | ---: | ---: | ---: |
| control, two-way 23/25 (measured) | 1.24 | 1.33 | 0.40 | 0.85 | 1.33 |
| shard3-c, 20/20/8 on xpu:0/1/2 (conservative) | 1.12 | 1.13 | 0.72 | 0.85 | 1.13 (-15 %) |
| **shard4-a, 18/18/8/4 on xpu:0/1/2/3 (predicted best)** | 1.04 | 1.05 | 0.72 | 1.01 | **1.05 (-21 %)** |

The best split under the memory cap was found by minimising the busiest card
over whole-block counts. The goal of about 0.95 per card is not reachable with
the memory left on xpu:2. Every extra boundary also adds one staged
host-memory move of the hidden state per forward, plus one staging of the text
context to each new card, about 0.3 GB more copy traffic per clip; that is
not in the prediction.

**Decode replica: stays on xpu:1.** Dropping it puts its 0.32 s back on xpu:3
(1.17 s), which then cannot take any blocks. Moving it to xpu:2 predicts a
busiest card of about 1.00 s instead of 1.05, which is inside the error of
these estimates. It would also take about 3.7 GiB of xpu:2 (copy plus decode
working set) that the blocks need, and it would mean changing the replica's
placement allowlist. Not worth it in this packet.

## What was built

- `scripts/ltx_layer_shard.py`: named placements (`PLACEMENTS`: `two-way`,
  `shard3-c`, `shard4-a`), `segment_plan` (validates contiguous, ordered,
  covering, one device per segment), `memory_plan`, and a multi-segment
  install: one shard ModelPatcher per extra segment and the same per-block
  route as today (move to the block's card, run, last block moves back).
  `verify_placement` walks every shard patcher. `install()`, `_BlockRoute`,
  `_move` and the transfer helpers are unchanged (test-checked against 93c),
  and the graph adapter's pin of this file was re-audited and repinned.
- `scripts/host_embedding_resident_node.py`: the placement comes from the
  launch environment `LTX_SAMPLER_PLACEMENT` (default `two-way`, the unchanged
  23/25 install); unknown names refuse to load.
- `scripts/graph_capture_node.py`: admits a multi-segment placement only from
  the allowlist.
- `scripts/ltx_graph_capture.py`: `CAPTURES_FROZEN` and `refuse_if_frozen`. After
  warm, a sampler block with no graph for a signature is refused before any
  capture (the 93b discipline for timed arms). Graph pools and capture streams
  stay per (device, worker thread), so a block on xpu:2 gets its own pool there.
- `scripts/pipeline_sampler_node.py`: drains the worker's streams on the extra
  cards at the end of each clip (none for two-way). New node
  `LTXSamplerCaptureFreeze` (graph `graphs/sampler-capture-freeze.json`):
  pipeline idle and **every card at least 2 GiB free**, else it refuses and the
  timed arm is skipped (recorded, no latch).
- `scripts/run-campaign-94.sh <control|shard3-c|shard4-a>`,
  `scripts/run-capture-freeze-94.py`, `scripts/decide-94.py`.
- Tests: `scripts/test-packet94-shard4-cpu.py`.

**Placement probe.** Before any timed arm on a layout, 13 prompts of the window
arm on the xpu:3 decode placement must reproduce all ten fixtures byte for byte
against the w93c references. This is the full pipelined path, not the serial
sampler-only run first proposed: it needs no stored conditioning and it tests
exactly what the timed arm runs. It also serves as that layout's warm, so every
capture happens there. Anything but 10/10 refuses the timed arms (exit 15).

**Restore.** There is no in-process restore to two-way: a layout cannot change
after the model loads. A failed candidate never blocks the control because the
control has its own server. The runner then stops that server gracefully.

## Runner, per server

warm 3 → text-window probe → placement probe (13 prompts, all ten fixtures
exact) → decode probe → capture freeze and memory floor → timed
`pipe-samp2-tsh-rep-wlean` against the w93c references (control 40, candidates
80) → candidates only: if this is the fastest exact arm so far and faster than
the control (`decide-94.py`), 160 more → summary with the context-sentry gate
(placement probe against timed arm) and engine busy per card → graceful stop on
proven quiescence. The SIGINT check, traps, submitted-job tracking and exit
codes follow 93c. Run order: control, shard3-c, shard4-a. If shard3-c beats the
control it gets its 160 when it runs; shard4-a gets them only if it beats both.

| Server | Warm | Placement probe | Timed | Extra |
| --- | ---: | ---: | ---: | ---: |
| control (two-way) | 220000 | 220300 | 220600 (40) | - |
| shard3-c | 220900 | 221200 | 221500 (80) | 221800 (160) |
| shard4-a | 222100 | 222400 | 222700 (80) | 223000 (160) |

## Packet and gate

- `R/prepared-encoder-shard4-94`, **manifest sha256
  `8fd0183b71a792f03f5061002921a6c1ca8c2b94a8977d1b3bf80d7f171bdcd2`**. The
  launcher requires `prepared-encoder-*` packet names and `encoder-server-*`
  run names; run names are `encoder-server-shard4-94-<mode>`.
- Gate (`--check-only`, 2026-10-04 13:20 UTC): **passes for all three run
  names without a receipt** (rc 0). With
  `four-card-health-20261004T0413Z.json` it refuses `Health receipt is older
  than 6 hours` (it expired at 10:13 UTC). The operator needs a fresh receipt
  from `scripts/check-four-card-health.py`.

- CPU tests: `test-packet94-shard4-cpu.py` 7/7, `test-ltx-layer-shard.py`
  OK, packets 90c-93b tests pass. Full lane sweep: 62 pass, 46 fail, the same
  46 that already failed before packet 93 (no change from the previous sweep).

## Launch (one server per layout, control first)

```
R=/mnt/fast-ai/bench-results/ltx25-baseline-20260913
P=$R/prepared-encoder-shard4-94
M=8fd0183b71a792f03f5061002921a6c1ca8c2b94a8977d1b3bf80d7f171bdcd2
H=<fresh health receipt>
# MODE=control -> PLACEMENT=two-way;  MODE=shard3-c -> shard3-c;  MODE=shard4-a -> shard4-a
nohup env --default-signal=INT LTX_BUSY_WINDOWS=0 LTX_SAMPLER_PLACEMENT=$PLACEMENT /home/steve/.venvs/ltx25-baseline/bin/python -B $P/launch/serve-encoder.py --packet $P --manifest-sha256 $M --run-name encoder-server-shard4-94-$MODE --health-receipt $H > $R/encoder-server-shard4-94-$MODE.log 2>&1 &
nohup bash /home/steve/llm-optimizations/experiments/ltx25-b70/scripts/run-campaign-94.sh $MODE > $R/campaign-94-$MODE.log 2>&1 &
```

Wait for each runner to stop its server before launching the next layout.

## Unverified offline

- That a block computes the same bytes on xpu:2 and xpu:3 as on xpu:0/1. Same
  card model and kernels, so expected; the placement probe decides.
- Memory: xpu:2 is predicted at 2.3 GiB free against the 2 GiB floor. The
  freeze step measures it, and shard3-c and shard4-a both depend on it.
- The busy-seconds prediction assumes per-block cost is the same on every card
  and ignores the extra boundary copies. ComfyUI's model manager loading
  transformer shards onto the text-encoder cards is untested; the receipts
  record loaded models.
- Whether two sampler threads pipeline well over four cards with the text
  encoder and decode sharing xpu:2/xpu:3 (one compute engine per card).
