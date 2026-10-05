# Packet 97: decode replica on a chosen card, an optional third decode worker, failed jobs on disk (build, 2026-10-05)

Built offline. **Not launched.** R = `/mnt/fast-ai/bench-results/ltx25-baseline-20260913`.
No GPU was used. Built on top of [packet 96](2026-10-04-packet-96-build.md) (results:
[packet 96 results](2026-10-04-packet-96-results.md)), with the same generator
(`scripts/prepare-graph-capture-runtime.py`).

## In plain words

Each clip is turned into pictures and sound by a decode step. Today half the clips decode on
card 3 and the other half on a copy of the decoders (the "replica") on card 1. On the two-card
layout, card 1 also carries 25 of the 48 transformer blocks. That makes it the busiest card
(95 % busy), while card 2 sits two-thirds idle.

This packet lets each server choose where the replica lives: card 1 (today's setup, the default)
or card 2. It can also run two replicas, on cards 1 and 2, so three decode workers take turns
(card 3, then the first replica, then the second). Moving work changes only which card does it,
not the arithmetic. Before any replica is used, the server decodes ten known clips on every
replica card and requires every byte to match. So no new reference clips are needed.

Two more fixes:

- **Failed jobs leave their error on disk.** A failed background job used to keep its error in
  memory, so a crash nobody waited for left no trace. That is what hid the cause of the two-worker
  batch-4 failure. Now every failed job writes `pipeline-failed-<stage>-<index>-<ms>.json` with the
  full traceback, and logs one line. The runner stops at once when it finds one (exit 20) and
  prints the traceback, instead of waiting out a 15-minute timeout.
- **Clip numbers up to 100,000,000.** ComfyUI refuses a clip number above the node's declared
  maximum (1,000,000). That is how the first 96r run lost its timed arm. Packet 97 raises the
  maximum to 100,000,000, so its index bases can start at 10,000,000.

## Design

### Replica placement (item 1)

- **Options** (`ltx_decode_replica.py`, read once at import; anything else raises at import):
  - `LTX_DECODE_REPLICA_DEVICE`: allowlist `xpu:1` (default) and `xpu:2`. With two replicas it is a
    comma list in slot order (`xpu:1,xpu:2` or `xpu:2,xpu:1`).
  - `LTX_DECODE_REPLICAS`: allowlist `1` (default) and `2`.
  - Unset, the tables are exactly packet 96's (`ALLOWED_DEVICES`, `PLACEMENTS`, `slot_for`), which
    the test checks against the packet 96 module.
- **xpu:0 is not admitted.** The code would allow it with one more list entry. But xpu:0 is
  ComfyUI's main device: its memory is budgeted by the model manager for the transformer and
  upsampler loads, and a replica placed outside that manager (1.7 GiB of weights plus its working
  set) could make ComfyUI evict or partially load something before the freeze. xpu:0 is also the
  busiest card or close to it in every layout (0.84-0.90 s per clip), so it is never the target.
- **What follows the option.** Every place that hard-coded the replica card now reads it from the
  option:
  - the replica copy (`build_replica`: admitted slot, placement check);
  - one stream per replica card;
  - one lock per replica slot (`_REPLICA_LOCKS`; the first slot is packet 96's `_REPLICA_LOCK`
    object);
  - the decode itself (`decode_replica(slot=...)`: the slot's VAE pair, lock and busy-window card);
  - the slot rotation (`slot_for`: clip index mod the number of slots, so packet 96's parity
    rule when there is one replica);
  - the decode-split device in every decode receipt;
  - the probe's memory readings (`<card>_free_after_build/_probe`, `memory_before/after[<card>]`,
    the same keys as packet 96 when the card is xpu:1);
  - the 5 GiB and 1 GiB probe floors, checked per card;
  - the release on any non-pass verdict (per card, `empty_cache` on that card).
- **Unchanged.** With the default, decode jobs call `decode_replica(vae, audio_vae, v, a)` exactly
  as in packet 96.
- **Recorded.** The decode request receipt, the decode probe receipt, and the coverage and freeze
  receipts carry a `decode_replica` record: count, cards, slots, native card and rotation. The
  runner requires the server's two variables to match its replica argument and records them in
  `runtime-environment.txt`.
- **Places that needed no change**, with the reason:
  - *Graph capture.* The replica decode is never graph-captured: VAE gate `original` on every
    arm, as in packet 91.
  - *Freeze residents.* `expected_residents` lists only ComfyUI-managed models. The replica is
    built outside model management, so it was never in that list, on any card.
  - *Text encoder sharing card 2.* The encoder keeps its own graph pools and capture streams per
    (card, thread) (`ltx_graph_text_encoder.py` 223-235), separate from the default allocator the
    replica uses. Its captures take `CAPTURE_LOCK` exclusive (line 324) and its replays take it
    shared (line 334). Replica work also holds it shared (the packet 91b lock order). So an
    encoder capture on card 2 can never overlap a replica kernel or allocation; this is the same
    rule that already protects the sampler shard on card 1. Nothing assumes card 2 has one user:
    no per-device lock exists in the encoder path. The window module's `_free_cached` empties the
    cache on cards 2 and 3 only after a failed window probe, and that probe runs before the
    replica exists.
  - *Busy windows.* They are named by card. They are off in speed runs (`LTX_BUSY_WINDOWS=0`).

### A third decode worker (item 2): built

The two-slot code generalised cleanly. Slots are `native`, `replica`, `replica2`, with one VAE
pair, lock and stream per replica slot. `pipeline-replica` starts one decode worker per slot (3).
Clips rotate by clip index mod 3. Emission stays in clip order, because the unchanged
`run_behind` collects clip i-2 before returning. The decode depth stays 2 (the arm graphs are
unchanged). With depth 2, the jobs of clips i-2, i-1 and i can be in flight together, and they
fall on three different cards, so all three workers can be busy.

The probe builds both replicas and decodes every fixture natively and on both replica cards.
Every image and waveform must equal the reference and the native decode, byte for byte. A
difference on either card refuses the probe and releases both replicas, each on its own card.
`pipeline-moved` still uses the first replica only.

### Failed-job receipts (item 3)

`ltx_pipeline.record_failure` is called in `_worker_loop`'s `except` block, before the job's
done event is set:

- **What it writes:** `pipeline-failed-<stage>-<index>-<ms>.json` (schema
  `ltx.pipeline-failed-job.v1`). Fields: stage, index, clip, worker thread, target, tag, exception
  type and message, the full traceback, the time, job seconds, the server identity hash and the
  pid. It also prints one stderr line, which lands in the server log:
  `[ltx-pipeline] FAILED JOB stage=... index=... worker=... Type: message (receipt: path)`.
- **It never raises.** Everything is wrapped in `BaseException` handlers. The CPU test covers an
  unwritable run directory, a missing run directory, an index that is not a number, and an
  exception whose `str()` itself raises.
- **It covers every stage:** encode, sample and decode jobs all go through `_worker_loop`.
- `scripts/check-failed-jobs-97.py` lists the receipts and prints the last traceback lines
  (exit 3 when any exist).

### Clip-index ceiling

`ltx_pipeline.CLIP_INDEX_MAX = 100000000` is now the `max` of the `clip_index` input on the
text-encode, sampler and decode nodes (was 1,000,000). ComfyUI's validation
(`execution.py:1027`) refuses a larger literal. This is a range check only; no arithmetic depends
on it. The test proves that `pipeline_sampler_node.py` and `pipeline_node.py` equal packet 96's
syntax tree except for this constant and the new receipt field.

## Exactness and fail-closed

| Condition | Enforced by | Proven offline (`test-packet97-place-cpu.py`) |
| --- | --- | --- |
| Default = packet 96 | unset variables give packet 96's tables; the default decode call is packet 96's | every graph byte-identical to packet 96; manifest sections differ only by hashes and the three new sections; placement tables and `slot_for` equal packet 96's module; the sampler node is packet 96's tree plus the two marked changes; headroom arithmetic equal for spec `xpu:1`; test-packet91's node path (four-argument stand-in) still passes |
| Replica bytes = native bytes, on the chosen card(s) | decode probe before the freeze; replica modes refused without a pass (does not latch) | real probe with stand-in VAEs for all four specs: every replica card decodes all ten fixtures; a one-byte difference on the last replica card refuses, releases every replica on its own card, and the next replica request is refused without latching |
| The probe really ran on the requested card(s) | `run-decode-probe-97.py --expect-replicas`: recorded cards, slots, the device each replica was built on, per-card memory readings and per-slot row hashes must all name the spec | accepts its own receipt; refuses every other spec |
| Every clip decoded on its slot's card | `check-decode-placement-97.py` after the timed arm (exit 21) | runs over real decode receipts from the real node path; a wrong spec is caught |
| Ordered emission with 2 and 3 workers | unchanged `run_behind` | 12 prompts per spec: emission `[-1, -1, base..]`, each clip decoded once on slot `index mod n` and that slot's card, with its lock, stream and busy-window card |
| Failed jobs visible | `record_failure`; runner's `failed_jobs` | a failing job in each stage writes its receipt and log line before done is set; the worker keeps serving; the runner's real capture-pass loop stops with 20 and prints the traceback (and waits it out when nothing failed) |

## Memory

Figures are measured, from packet 96 receipts (`data/batch-96/*`):

- **What the replica costs on its card**, from coverage to freeze on xpu:1: 2.12-2.19 GiB, of which
  the copy itself is 1.71 GiB (video 1.37 + audio 0.34). The decode probe on xpu:1 dropped free
  memory by 1.73 GiB at the copy and by another 2.0 GiB of decode scratch after the probe.
- **xpu:2 with no replica**, at the freeze on two-way: 11.84 GiB free in every run.
- **One pooled worker at batch 2** costs 0.42 / 0.31 GiB on xpu:0 / xpu:1 (`two-way-w2-b2-p1/pool-calibration.json`).

| Run (two-way, pooled) | Replica | Free at the freeze, GiB (xpu:0 / 1 / 2 / 3) | Basis |
| --- | --- | --- | --- |
| W2 B1 | xpu:1 (96, measured) | 7.53 / 10.11 / 11.84 / 14.74 | 96 freeze receipt |
| W2 B1 | xpu:2 | ~7.5 / ~12.2 / ~9.6 / 14.7 | xpu:1 back to its coverage reading (12.28), xpu:2 minus 2.2 |
| W2 B2 | xpu:1 (96, measured) | 7.06 / 9.93 / 11.84 / 14.74 | 96 freeze receipt |
| W2 B2 | xpu:2 | ~7.1 / ~12.0 / ~9.6 / 14.7 | as above (coverage 12.05) |
| W3 B2 | xpu:2 | ~6.6 / ~11.7 / ~9.6 / 14.7 | plus one more pooled worker (0.42 / 0.31) |
| W2 B2 | xpu:1,xpu:2 | ~7.1 / ~9.9 / ~9.6 / 14.7 | both replicas |
| W3 B2 | xpu:1,xpu:2 | ~6.6 / ~9.6 / ~9.6 / 14.7 | both replicas, three workers |

Every card stays far above the 2 GiB floor.

**The decode probe on xpu:2:** about 11.8 GiB free before the copy, about 10.1 GiB after it
(rule: at least 5), about 8.1 GiB after the decodes (rule: at least 1).

**`worker-headroom-97.py`** (a copy; the live 96 tool is untouched) handles the replica card(s):

- It takes `--replicas <spec>`.
- It charges the zero-worker free memory 2.2 GiB on every replica card other than xpu:1. It does
  not credit xpu:1 when xpu:1 loses its replica. That is conservative: it never admits more than
  the memory allows.
- The live check's room still to come puts 1.8 GiB on each chosen replica card, plus 1.9 GiB on
  xpu:3.
- `plan` also skips the combination before anything is captured if a replica card's predicted free
  memory at the freeze with one worker is under 4.51 GiB. That figure is the probe's 5 GiB
  after-copy rule moved to the freeze reading (5.0 - (2.2 - 1.71)).

What the plan predicts:

| Layout and spec | Plan says | Why |
| --- | --- | --- |
| two-way, xpu:2 | runs | |
| two-way, xpu:1,xpu:2 | runs | |
| shard4-a or shard3-c, any spec that includes xpu:2 | skipped (exit 18) | xpu:2 would have 1.7-1.8 GiB |

**Pool calibration:** packet 96 calibration receipts are **not** accepted. Packet 97 changed
`pipeline_sampler_node.py`: one receipt field and the index ceiling. The syntax-tree test shows
nothing else changed, and the capture adapter is byte-identical. But the headroom tool accepts
calibrations only by manifest, and I chose not to add a cross-packet exception. Packet 97
recalibrates in its own first pooled multi-worker run, which is planned run 1 (two-way W2 B1 p1).
Packet 96's first pooled run was admitted on the private-pool bound in the same way (plan:
5.31 / 7.78 / 9.64 / 14.55 GiB with one worker). Calibrations live at
`data/place-97/<layout>-w<W>-b<B>-p1-d<spec>[-rN]/pool-calibration.json` (schema
`ltx.pool-calibration-97.v1`, packet 97 manifest only).

## Runner: `scripts/run-campaign-97.sh <layout> <W> <B> <pool> <replica-spec> [repeat 1-9] [timed prompts 120-9000]`

This is `run-campaign-96r.sh` (current version) with these changes:

- **Names and output:** run names `encoder-server-place-97-<layout>-w<W>-b<B>[-p1]-d<spec>[-rN]`
  (spec without punctuation: `dxpu2`, `dxpu1xpu2`); arm prefixes `f97-<tag>-...`; output
  `data/place-97/<mode>`.
- **Preflight:** it requires the packet 97 manifest, `NEOReadDebugKeys=1 EnableDeferBacking=0`, and
  the server's `LTX_DECODE_REPLICA_DEVICE` / `LTX_DECODE_REPLICAS` matching the spec (unset counts
  as `xpu:1` x 1).
- **References:** it reuses the existing ones and makes none. B = 1 is checked against w93c; B = 2/4
  against `stability-01-b<B>` through `data/stability-01-batch<B>-prereg.json`. A missing prereg
  refuses at preflight (exit 8). The reference-making branch is removed.
- **Helpers:** memory plan and live checks use `worker-headroom-97.py --replicas`; the decode probe
  uses `run-decode-probe-97.py --expect-replicas`.
- **After the timed arm:** `check-decode-placement-97.py` over the self-check, probe/proof and timed
  arms (exit 21).
- **Failed jobs:** `failed_jobs` runs in the capture-pass wait (finish 20 at once), in the
  quiescence wait (it stops waiting for done markers, but idleness is still proven before the
  SIGINT, and a clean finish becomes 20), and after any failed arm (it prints the cause).
- **Unchanged from 96r:** the client, marker check, summary, self-check, proof checker and
  coverage/freeze tools are reused untouched (`run-throughput-fixtures-96.py`,
  `missing-markers-96.py`, `summarize-campaign-96.py`, `selfcheck-94f.py`,
  `check-batch-proof-96.py`, `run-capture-freeze-94.py`, `run-sampler-pin-95.py`).

Sequence per server:

1. window probe
2. memory plan
3. serial capture pass (live headroom; failed-job watch)
4. coverage
5. pool calibration (pooled, W of 2 or more)
6. decode probe on the chosen card(s)
7. freeze
8. self-check
9. B = 1: placement probe (13 prompts, against w93c) and timed arm. B > 1: proof arms
   (neighbours, slots) and timed arm against b<B>, then the timed proof check
10. decode-placement check
11. summary
12. graceful stop

## Index bases

The formula:

```
IDX = 12 x layout + 3 x (W-1) + batch index          (as 96: layout two-way/shard4-a/shard3-c = 0/1/2,
                                                      batch 1/2/4 = 0/1/2)
S   = spec index: xpu:1 0, xpu:2 1, xpu:1,xpu:2 2, xpu:2,xpu:1 3
C   = IDX + 36 x (pool + 2 x (S + 4 x (repeat - 1)))  0 <= C < 2592
short arms: 10,000,000 + 1000 x C   (capture +10 k, self-check +100, probe +200, proof-n +300, proof-s +400)
timed arm:  20,000,000 + 10000 x C  (up to 9000 prompts)
```

- All 2592 combinations are disjoint.
- The short arms run from 10,000,000 to below 12,592,000; the timed arms from 20,000,000 to below
  45,920,000.
- Everything is above every earlier index, including 96r's planned 2.0-9.2 M timed blocks, and
  below the 100,000,000 ceiling.
- The test runs the runner's own parsing block for all 2592 combinations.

| Planned run | C | Short base | Timed base |
| --- | ---: | ---: | ---: |
| two-way W2 B1 p1 xpu:2 | 111 | 10,111,000 | 21,110,000 |
| two-way W2 B2 p1 xpu:2 | 112 | 10,112,000 | 21,120,000 |
| two-way W3 B2 p1 xpu:2 | 115 | 10,115,000 | 21,150,000 |
| two-way W2 B2 p1 xpu:1 (control) | 40 | 10,040,000 | 20,400,000 |
| two-way W2 B2 p1 xpu:1,xpu:2 | 184 | 10,184,000 | 21,840,000 |
| two-way W3 B2 p1 xpu:1,xpu:2 | 187 | 10,187,000 | 21,870,000 |

## Packet and gate

- `R/prepared-encoder-place-97`, manifest
  **`6e232f72a9835727323c383bc9baaa167844b58dc6400a5de43a3b9eb4e44b9f`**.
- **The same file inventory as packet 96.** Changed files:
  - `ltx_decode_replica.py`, `pipeline_decode_node.py`, `ltx_pipeline.py`, `pipeline_sampler_node.py`
    and `pipeline_node.py`, each with its custom-node copy;
  - the checker (`launch/encoder_runtime_common.py`).
- **Every graph is byte-identical to packet 96's.**
- **New manifest sections, checked by the gate:** `decode_replicas` (variables, allowlists,
  defaults, module hashes), `pipeline_failures` (schema, file name, module hash) and
  `clip_index_max`.
- Gate (`--check-only`, 2026-10-05 01:30 UTC): rc 0 for
  `encoder-server-place-97-{two-way-w2-b1-p1-dxpu2, two-way-w2-b2-p1-dxpu2, two-way-w3-b2-p1-dxpu2,
  two-way-w2-b2-p1-dxpu1, two-way-w2-b2-p1-dxpu1xpu2, two-way-w3-b2-p1-dxpu1xpu2,
  shard4-a-w3-b2-p1-dxpu1xpu2}`, both without a receipt and with the newest health receipt in
  `data/health/` (`four-card-health-20261005T0123Z.json`).

### Files

- **Edited lane sources** (none is called by the live packet 96 runner or its helpers, which use the
  sealed packet copies; the only lane module a live 96 helper imports is `ltx_sampler_batch.py`,
  which is untouched):
  - `ltx_decode_replica.py`, `pipeline_decode_node.py`, `ltx_pipeline.py`,
    `pipeline_sampler_node.py`, `pipeline_node.py`;
  - `prepare-graph-capture-runtime.py` (output name, gate checks, manifest sections, status text).
- **New:** `run-campaign-97.sh`, `worker-headroom-97.py`, `run-decode-probe-97.py`,
  `check-failed-jobs-97.py`, `check-decode-placement-97.py`, `test-packet97-place-cpu.py`.
- **One packet 96 test adjusted:** `test-packet96-batch-cpu.py` line 519-526. Its build-time check
  "packet 96's copy equals the lane copy" can no longer hold for the two lane files packet 97
  edited (`pipeline_sampler_node.py`, `ltx_pipeline.py`). Those two are now held to packet 96's own
  manifest hashes, and the two untouched files are still compared with the lane.

### Tests

- `test-packet97-place-cpu.py`: 8/8.
- Packet 90c-96 tests pass: 90c, 91, 92a, 92b, 93, 93b, 94, 94c, 94d, 95, 96.
- Lane sweep (116 test files; run sequentially, niced, with GPUs hidden through
  `ONEAPI_DEVICE_SELECTOR=opencl:cpu ZE_AFFINITY_MASK=99`): 67 pass, 46 fail, 3 not run (the three
  packet-copying negative tests write into R). The baseline was the same sweep over a frozen copy of
  the pre-97 scripts: 63 pass, 49 fail. Three tests failed there only because of the copy's location
  (94, 94d, host-transition-builder); they pass in the tree. No test went from pass to fail. The new
  test is the 67th pass. Packet 96's note counted 68 / 47 over 115 files in a different setup.

## Launch (one server per run; wait for each runner to stop its server)

```
R=/mnt/fast-ai/bench-results/ltx25-baseline-20260913
P=$R/prepared-encoder-place-97
M=6e232f72a9835727323c383bc9baaa167844b58dc6400a5de43a3b9eb4e44b9f
L=two-way W=2 B=1 SP=1 SUF=-p1
D=xpu:2 N=1 DS=dxpu2          # three-worker variants: D=xpu:1,xpu:2 N=2 DS=dxpu1xpu2
nohup env --default-signal=INT NEOReadDebugKeys=1 EnableDeferBacking=0 LTX_BUSY_WINDOWS=0 LTX_SAMPLER_PLACEMENT=$L LTX_SAMPLER_WORKERS=$W LTX_SAMPLER_BATCH=$B LTX_SAMPLER_SHARED_POOL=$SP LTX_DECODE_REPLICA_DEVICE=$D LTX_DECODE_REPLICAS=$N /home/steve/.venvs/ltx25-baseline/bin/python -B $P/launch/serve-encoder.py --packet $P --manifest-sha256 $M --run-name encoder-server-place-97-$L-w$W-b$B$SUF-$DS --health-receipt <fresh receipt> > $R/encoder-server-place-97-$L-w$W-b$B$SUF-$DS.log 2>&1 &
nohup bash /home/steve/llm-optimizations/experiments/ltx25-b70/scripts/run-campaign-97.sh $L $W $B $SP $D > $R/campaign-97-$L-w$W-b$B$SUF-$DS.log 2>&1 &
```

**Planned order:**

1. two-way W2 B1 p1, replica xpu:2. The exactness gate for the placement change against the w93c
   references; it also writes packet 97's pool calibration.
2. two-way W2 B2 p1, replica xpu:2 (proofs and timed against the b2 references; compare with
   packet 96's 1.122 s per clip).
3. two-way W3 B2 p1, replica xpu:2.
4. two-way W2 B2 p1 and W3 B2 p1 with replicas `xpu:1,xpu:2` (three decode workers).

What runs 2 and 3 should show (not measured): card 1 loses its decode share (packet 96: 1.07 s
of compute per clip on card 1) and card 2 gains it (0.37 s). The busiest card should become
card 0 or card 1 at about 0.85 s per clip.

## Unverified offline

- That the replica on xpu:2 decodes byte-identically to xpu:3 on the real cards. The probe decides
  before the freeze. Packet 91 showed this for xpu:1; xpu:2 is the same hardware, but its decode
  will now overlap the text encoder on the same card.
- Speed, all of it:
  - whether moving the replica actually lowers the stream interval;
  - whether sharing card 2 slows the window encoder enough to matter (about 0.56 s per window
    encode on two workers);
  - whether a third decode worker helps at all, since decode is not the limit at about 1.1 s per
    clip.
- The memory figures in the table are predictions, built from packet 96's freeze, coverage and
  probe receipts. The real figures will come from the freeze receipts.
- Whether any lane path keeps a clip index in a 32-bit field. None was found in the lane modules,
  the client or the checkers, but indices above 1,000,000 have never run through the real server.
- The failed-job receipts on a real failure: the stage jobs are covered by CPU stand-ins only.
  The two-worker batch-4 capture failure should now leave its traceback; this packet does not fix
  that failure.
- The runner end to end. Only its parsing block, the capture-pass wait loop and the failed-job
  helper were executed offline; the rest is checked by text and `bash -n`.

## Review fixes (2026-10-05, runner side only; packet unchanged)

An independent review found no launch blocker and three should-fix items. All three are fixed
outside the packet, so the manifest is unchanged.

1. **Arm timeouts follow the prompt count.**
   - Every arm passes the client its own `--timeout`: 1800 s plus 2.5 s per prompt. The outer
     `timeout` is 300 s longer.
   - After a failed or expired arm, the stop step (quiescence part 1) waits up to that client
     timeout for the queue to drain. It still aborts on a latched fault. So a server that is still
     busy goes through the normal proven-quiescence stop instead of being left running after
     five minutes.
2. **`check-decode-placement-97.py` (schema v2) needs complete coverage of every arm.**
   - Each arm needs requests 0..N-1, and each request needs a readable decode receipt on disk.
   - Each receipt must have `passed` true, the mode of its own submitted graph, and the spec's
     placement record.
   - Each receipt must emit exactly clip base + i - SD - DD, or be an explicit fill.
   - The decode card must match the mode. `pipeline-save`, used by the batch-1 placement probe,
     must be native on xpu:3 for every clip.
   - Anything missing, malformed or empty fails (exit 4, so the runner exits 21).
   - Placement is read from the per-prompt receipts on disk. Each receipt copies the decode split
     when its prompt emits the clip, a few clips after the decode ran. So the server's bounded
     in-memory record (512 entries) only ever needs the live window. The exit-21 risk I listed for
     long arms does not exist.
3. **A broken failed-job monitor stops the campaign.** `failed_jobs` now separates three results:
   - 0: no failed jobs;
   - 3: failed jobs (handled as before);
   - anything else (a timeout or crash of the helper): the monitor itself failed. In the capture
     pass the campaign stops with exit 22 through the graceful stop. Elsewhere it is recorded, and a
     clean finish becomes 22.

`test-packet97-place-cpu.py` now passes 9/9. The new placement-check case covers: a missing timed
receipt, a missing request, a malformed index, a wrong emitted clip, a wrong mode against the
graph, a failed receipt, a fill without its flag, the wrong card, an unreadable receipt, a
malformed graph, an empty arm and a fills-only arm. The runner case adds a broken monitor
(exit 22) and checks the timeout arithmetic.
