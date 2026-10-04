# Packets 94 / 94b / 94c / 94d: spread the transformer over more cards (build, 2026-10-04)

Built offline. **Not launched.** R = `/mnt/fast-ai/bench-results/ltx25-baseline-20260913`.
No GPU was used to build or test it. Baseline and references: the short-window
encoder plus lean conditioning, `stability-01-w93c-*`
([milestone](2026-10-04-milestone-window-baseline.md)).

**Launch 94d.** `prepared-encoder-shard4-94d`, manifest
`cf13cd11b22f9e36b39747ba46dd90ed80c94ab139b5732501cec47ef46fccf3`, run names
`encoder-server-shard4-94d-<mode>`, runner `scripts/run-campaign-94d.sh <mode>`.
94, 94b and 94c stay in place; their runners refuse.

### 94c runs, and what 94d fixes

**control (rc 9): the VAEs were not on their card.** The serial capture pass
worked (coverage complete after two prompts), but every capture prompt is a
pipeline fill, so no clip is decoded. The 94c receipts show it: every decode
receipt is an upstream fill, and the loaded models after the pass contain no
VAE. ComfyUI therefore still held both VAEs on their offload device, and the
replica builder rightly refused to copy them ("not wholly on its device"). In
93c the pipelined warm's third prompt emitted a real clip and its native decode
(ComfyUI `VAE.decode` through model management) loaded the VAEs fully as a side
effect. 94d makes this explicit: the decode probe first runs one full load of
both VAEs through ComfyUI's loader, onto xpu:3. That step is allowed only with
the pipeline idle and before the freeze. It then checks that every VAE tensor is
on xpu:3 and records before/after counts in the probe receipt
(`vae_residency`). The replica builder's refusal is unchanged.

**shard3-c (rc 11): the known host stall latched FAULT.** At 14:32:51 UTC the
kernel logged a hard lockup on CPU 21 with `g2h_read`/`xe_guc_irq_handler` in its
trace, then a soft lockup on CPU 20 26 s later. That second line matched the
fault pattern. No GPU fault line occurred.

**A tolerance for one identified host stall.** On this host the xe driver's GuC
interrupt handler (card 0000:43:00.0) stalls a CPU every 15-30 minutes of GPU
load. With panic-on-lockup off the machine carries on, and runs through it have
stayed byte-exact. But it ended every campaign longer than about 15 minutes. It
is a driver bug still to be fixed, and this is a workaround, not a fix. The
launcher now:

- treats a journal window as the known stall only if a `hard LOCKUP on cpu` line
  has `xe_guc_irq_handler` or `g2h_read` in its trace within the same second;
- counts as part of that event only soft-lockup, RCU-stall, `blocked for more
  than` and `clocksource: Long readout` lines within 180 s after it;
- writes each event once to `host-stalls.jsonl` in the run directory, with
  timestamps and the matched lines;
- still latches immediately on any GPU fault line (`Fault response`, CAT error,
  engine reset, GPU HANG, GuC reset, coredump, Timedout job, wedged), inside a
  stall window too, and on any soft lockup, RCU stall or blocked task without
  that preceding xe hard lockup.

The same classification is used by the start check, the admission since the
health receipt, the preflight check and the in-run watcher; journals are read
with `-o short-unix` for timestamps. Sampler receipts that overlap a stall
carry `host_stall`. The summary drops intervals that overlap a stall from the
speed statistics and prints how many and the stall durations, while exactness
is still checked for every clip.

Tests (`test-packet94d-stall-cpu.py`, real excerpts from
`data/2026-10-03-xe-guc-hard-lockup/` and 94c's `journal-fault.txt`):
- the known stall is recorded and not latched;
- a soft lockup without the xe signature, or later than 180 s, latches;
- the 02:46 excerpt (lockups followed by `Fault response`) latches.

The dry run now also models the decode probe's precondition: the VAEs that the
capture pass leaves off their card (checked against the real 94c receipts) are
refused by the replica builder, then loaded by the explicit step (stand-in load
to the `meta` device). The real device move and ComfyUI's loader cannot be
modelled on CPU.

Gate (2026-10-04 14:52 UTC): rc 0 for all three run names without a receipt,
and with `four-card-health-20261004T1427Z.json`. The 14:32 stall after that
receipt is admitted as the known stall.

CPU tests: stall 5/5, dry run 6/6, packet 94 11/11, health 6/6. The packet 91
probe-release test now stubs the new residency step (exercised in the dry run).
Full lane sweep: 64 pass, 46 old failures unchanged.

### 94c over 94b

**Launch 94c.** `prepared-encoder-shard4-94c`, manifest
`9af04d202f5c8e7031245bfe9dfa2dbf7616e51a804bbfcb8d0b878fba5722cc`, run names
`encoder-server-shard4-94c-<mode>`, runner `scripts/run-campaign-94c.sh <mode>`.
94 and 94b stay in place; their runners refuse.

### 94b runs, and what 94c fixes

94b ran on three servers. Each started and stopped cleanly with no fault, but
no timed arm ran:

- **control, rc 9:** the decode probe ran before any pipelined prompt, and it
  needs the resident fast path's load lock, which only a pipelined prompt
  installs (node 431).
- **shard3-c and shard4-a, rc 11:** the component loader's `shared_identity`
  unpacked exactly one transformer shard owner (`shard, = ...`).

94c fixes:

1. **Order, from what installs what:**
   1. Text-window probe. Its loader loads the components and its text gate
      installs the sharded graph encoder and two encode workers. It captures
      the 1024 and window encoder graphs and needs nothing.
   2. Serial capture pass. These are window prompts, so it needs step 1. It
      installs the fast path and the graph-capture gate, loads the
      transformer shards and the upsampler, and captures the sampler graphs.
      After each prompt a coverage check (new node `LTXSamplerCaptureCoverage`,
      read only) asks whether both workers hold every graph.
   3. Decode probe. It needs the fast path from step 2. It builds the xpu:1
      replica, which is a load, so it comes before the freeze while nothing
      else runs.
   4. Freeze. It needs steps 2 and 3. Coverage again, and every expected model
      must be resident on its card: transformer owners per layout, text
      encoder halves on xpu:2/3, VAEs on xpu:3, upsampler on xpu:0. This catches
      an eviction before the freeze as well as after it. The 2 GiB floor
      applies.
   5. Placement probe. It needs step 4 and may not capture or load.
   6. Timed arms. They need the replica from step 3 and the freeze from step 4.
2. **Single-owner assumptions, searched across the shipped scripts and custom
   nodes:**
   - Fixed: `shared_identity` in `host_embedding_resident_node.py`. Two-way
     still requires exactly one shard owner and records the same fields.
     Multi-segment layouts require one owner per extra segment and record all
     of them.
   - Tightened: the graph gate's report check, now `check_shard_report`, also
     requires one owner per segment.
   - Already fail closed, and not used by any 94 arm: `ltx_block_compile.py`
     and `ltx_multiblock_compile.py` raise unless there is exactly one shard
     owner; `block_compile_node`/`multiblock_compile_node` require the
     declared split.
   - Reviewed, nothing to change: the pinned devices `xpu:2`/`xpu:3` for the
     encoder (`graph_text_encoder_node`, `host_embedding_clip`, `ltx_text_window`),
     `xpu:3` for native decode, `xpu:1` for the replica, the fusion,
     concurrent-CFG, upsampler and VAE gates (all `original` in these arms),
     and the sampler's two named streams. The extra cards are drained
     separately (94).
   None of these checks reads which transformer blocks share their card.

**Offline dry run** (`test-packet94c-dryrun-cpu.py`). With a stand-in 48-block
model, for each layout, it runs real lane code under the shipped ComfyUI tree:
the component loader module (layout from the environment, the same apply_*
call `load()` makes, the real `shared_identity` and receipt), the graph-capture
gate checks and `validate_patcher`, the sampler's placement/residency/freeze
logic, the decode probe's fast-path prerequisite, and the runner order against
the built graphs. It would have caught both 94b failures. Not covered:
ComfyUI's executor, checkpoint loading and the model manager, XPU memory, real
graph capture, and the full `apply()` bodies of the loader, text gate, window
probe, decode probe and freeze nodes.

### 94b over 94

**Launch 94b, not 94.** `prepared-encoder-shard4-94b`, manifest
`b9e5417a9799cb750c9cd67ddfd07e308b5baca7e7975e7e518398971e3e262d`, run names
`encoder-server-shard4-94b-<mode>`, runner `scripts/run-campaign-94b.sh`.
`prepared-encoder-shard4-94` (manifest `8fd0183b...`) stays in place and was never
launched; `run-campaign-94.sh` refuses. A review found these defects in 94,
all fixed in 94b:

1. **A sampler capture could overlap other GPU work on the shared cards** (native
   VAE decode on xpu:3 and the encoder's eager parts do not take the capture
   lock). 94b chooses a **serial capture pass**: before the freeze the server
   admits a sampler request only when nothing else runs (no pipeline job queued
   or running, no other prompt queued; otherwise it refuses with a receipt and
   no latch). The runner sends one prompt at a time on a fresh index base, so
   there is no lookahead, no encode-ahead and no decode-behind, and it waits for
   that prompt's sample job to finish. It repeats (at most 8) until the freeze
   confirms that every block signature is captured on both sampler workers.
   After the freeze no sampler capture can start. I chose this over making
   decode and every encoder step take the capture lock in shared mode because
   that does not work: an encode already captures its own text graphs under the
   exclusive lock, so holding shared for the whole encode would deadlock. A
   piecemeal lock over the eager parts would be hard to prove complete.
2. **Weights could be evicted after the freeze** by a fall-through to ComfyUI's
   loader. After the freeze, a load of anything not fully resident is refused
   before the native loader runs, with a receipt (`load-refused-*.json`): no
   load, no eviction. The freeze records the resident models (type, card,
   bytes) and free memory per card. Every later sampler request, the placement
   probe and the timed arms included, asserts the set is unchanged.
3. **An interrupted arm was not awaited at the stop**: the runner now registers
   the arm before its client starts. The marker check counts only what the
   client actually submitted.
4. **The memory floor compared a rounded figure**: it now compares raw bytes.

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
- `scripts/run-campaign-94d.sh <control|shard3-c|shard4-a>` (94, 94b and 94c runners refuse),
  `scripts/run-capture-freeze-94.py`, `scripts/decide-94.py`.
- Tests: `scripts/test-packet94-shard4-cpu.py`.

**Placement probe.** Before any timed arm on a layout, 13 prompts of the window
arm on the xpu:3 decode placement must reproduce all ten fixtures byte for byte
against the w93c references. This is the full pipelined path, not the serial
sampler-only run first proposed: it needs no stored conditioning and it tests
exactly what the timed arm runs. In 94b it runs after the freeze, so it may
neither capture nor load. Anything but 10/10 refuses the timed arms (exit 15).

**Restore.** There is no in-process restore to two-way: a layout cannot change
after the model loads. A failed candidate never blocks the control because the
control has its own server. The runner then stops that server gracefully.

## Runner, per server (94c)

text-window probe → serial capture pass with coverage checks → decode probe →
freeze (coverage, expected residents, 2 GiB floor, resident snapshot; captures
and loads frozen) → placement probe (13 pipelined prompts, all ten fixtures exact,
no capture or load allowed) → timed
`pipe-samp2-tsh-rep-wlean` against the w93c references (control 40, candidates
80) → candidates only: if this is the fastest exact arm so far and faster than
the control (`decide-94.py`), 160 more → summary with the context-sentry gate
(placement probe against timed arm) and engine busy per card → graceful stop on
proven quiescence. The SIGINT check, traps, submitted-job tracking and exit
codes follow 93c. Run order: control, shard3-c, shard4-a. If shard3-c beats the
control it gets its 160 when it runs; shard4-a gets them only if it beats both.

| Server | Capture pass (base, +10 ... +70) | Placement probe | Timed | Extra |
| --- | ---: | ---: | ---: | ---: |
| control (two-way) | 232000 | 232300 | 232600 (40) | - |
| shard3-c | 232900 | 233200 | 233500 (80) | 233800 (160) |
| shard4-a | 234100 | 234400 | 234700 (80) | 235000 (160) |

## Packet and gate (94c)

- `R/prepared-encoder-shard4-94c`, manifest
  `9af04d202f5c8e7031245bfe9dfa2dbf7616e51a804bbfcb8d0b878fba5722cc`.
- Gate (`--check-only`, 2026-10-04 14:06 UTC): passes for all three run names
  without a receipt (rc 0). With `data/health/four-card-health-20261004T1357Z.json`
  it passes (receipt end 13:57:49 UTC).
- CPU tests: dry run 5/5, packet 94 tests 11/11, the layer-shard test and
  packet 90c-93b tests pass.

## Packet and gate (94b, superseded)

- `R/prepared-encoder-shard4-94b`, manifest
  `b9e5417a9799cb750c9cd67ddfd07e308b5baca7e7975e7e518398971e3e262d`.
- Gate (`--check-only`, 2026-10-04 13:36 UTC, **without a receipt**, because
  no fresh one exists yet): passes for all three run names (rc 0). The operator
  passes the fresh receipt at launch.
- CPU tests: `test-packet94-shard4-cpu.py` 11/11, with new cases for the
  serial-pass admission, capture coverage, load refusal, raw-byte floor and arm
  registration. The layer-shard test and packet 90c-93b tests pass.

## Packet and gate (94, superseded)

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
P=$R/prepared-encoder-shard4-94d
M=cf13cd11b22f9e36b39747ba46dd90ed80c94ab139b5732501cec47ef46fccf3
H=<fresh health receipt>
# MODE=control -> PLACEMENT=two-way;  MODE=shard3-c -> shard3-c;  MODE=shard4-a -> shard4-a
nohup env --default-signal=INT LTX_BUSY_WINDOWS=0 LTX_SAMPLER_PLACEMENT=$PLACEMENT /home/steve/.venvs/ltx25-baseline/bin/python -B $P/launch/serve-encoder.py --packet $P --manifest-sha256 $M --run-name encoder-server-shard4-94d-$MODE --health-receipt $H > $R/encoder-server-shard4-94d-$MODE.log 2>&1 &
nohup bash /home/steve/llm-optimizations/experiments/ltx25-b70/scripts/run-campaign-94d.sh $MODE > $R/campaign-94d-$MODE.log 2>&1 &
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
- Whether 8 serial prompts are always enough for both sampler workers to
  capture (which worker takes a job is not controlled); otherwise exit 16.
- The serial pass sends `pipe-samp2-tsh-win` prompts as fills, so their
  outputs are not checked; the placement probe checks the outputs.
- Whether two sampler threads pipeline well over four cards with the text
  encoder and decode sharing xpu:2/xpu:3 (one compute engine per card).
