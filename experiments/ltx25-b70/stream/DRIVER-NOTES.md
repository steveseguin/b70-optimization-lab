# ltx_stream_driver.py: notes for review

Driver for one packet 97 server launched like `chain-97.sh "two-way 2 2 1 xpu:2"` (run name
`encoder-server-place-97-two-way-w2-b2-p1-dxpu2-stream01`, env `NEOReadDebugKeys=1
EnableDeferBacking=0 LTX_BUSY_WINDOWS=0 LTX_SAMPLER_PLACEMENT=two-way LTX_SAMPLER_WORKERS=2
LTX_SAMPLER_BATCH=2 LTX_SAMPLER_SHARED_POOL=1 LTX_DECODE_REPLICA_DEVICE=xpu:2 LTX_DECODE_REPLICAS=1`).
Python 3.12, stdlib only (Phase A helpers and the comparator run in the venv as subprocesses).

```bash
PY=/home/steve/.venvs/ltx25-baseline/bin/python
cd /home/steve/llm-optimizations/experiments/ltx25-b70/stream
$PY -B ltx_stream_driver.py --print-warmup-plan                  # the Phase A commands; contacts nothing
$PY -B ltx_stream_driver.py --warmup-only                        # Phase A only
$PY -B ltx_stream_driver.py --sink-stats /path/sink-stats.json   # Phase A (unless it already passed on this server), then the stream
$PY -B ltx_stream_driver.py --skip-warmup --sink-stats ...       # stream only; refuses unless this server's own
                                                                 # window/decode-probe/freeze receipts passed
```

Defaults: `--server-run encoder-server-place-97-two-way-w2-b2-p1-dxpu2-stream01`, `--prefix
s97-twowayw2b2p1dxpu2-stream01`, port 8188, work dir `stream/runs/<prefix>/` (holds `manifest.jsonl`,
`state.json`, `parity/`, `warmup/`), `--in-flight 4`, `--max-ahead-seconds 300`, `--timeout 600`
(how long a stop waits for in-flight prompts), `--http-fail-seconds 120`, `--min-free-gib 30`.

## Index plan (why 50,000,000 and up)

The nodes accept `clip_index` up to 100,000,000 (`ltx_pipeline.CLIP_INDEX_MAX`). In run-campaign-97.sh,
`C = IDX + 36 x (pool + 2 x (S + 4 x (rep-1))) < 2592`. Short arms use `10,000,000 + 1000 x C (+ at most 416)`,
which stays below 12,592,000. Timed arms use `20,000,000 + 10,000 x C` plus at most 9000 prompts, which stays
below 45,920,000. So no runner combination, repeat or timed length ever reaches 50,000,000.

- Phase A short arms: 50,000,000 + the runner's own offsets (cap +0/+10, self +100, proof-neighbours +300,
  proof-slots +400). The highest used is 50,000,412.
- Stream: from 50,001,000 upward, one index per prompt, never reused. At the measured ~0.9 s per clip that
  lasts about 1.6 years before the 100,000,000 ceiling. The driver refuses to go past it (exit 8).

On the server side an index only has to be fresh for that server process (the grouper's `used` set, and
`run_behind`'s stale-index check). This range also keeps request names and receipts apart from every
runner arm.

## Phase A: what it will do

The runner lines are in `scripts/run-campaign-97.sh`. The r2 lines are in
`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/campaign-97-two-way-w2-b2-p1-dxpu2-r2.log`, which ran
the same combination as `two-way 2 2 1 xpu:2 2 600`. `T` = `s97-twowayw2b2p1dxpu2-stream01` (the runner used
`f97-$TAG`, i.e. `f97-twowayw2b2p1dxpu2r2`). `RUN` = the server run dir. `OUT` = `stream/runs/<prefix>/warmup`
(the runner used `data/place-97/<mode>`). Every helper is called with the runner's arguments, timeout and
pass condition.

| step | what | runner lines | r2 log evidence |
|---|---|---|---|
| pre | health wait: `GET /queue` every 5 s, up to 360 tries | 347-353 | 7 |
| pre | preflight. These are reads only: packet manifest sha, `check-b70-runtime-pm.sh` (reads sysfs), W93C + b2 prereg exist, `server-identity.json`, pid + start ticks + `serve-encoder.py --run-name RUN` cmdline, the server's environment from `/proc/PID/environ` (all 8 variables above plus `LTX_DECODE_REPLICAS=1`), boot id, model-verification passed | 342-384 | 2-6, 8 |
| A01 | rest 60 s after construction | 388-389 | 10 |
| A02-03 | queue empty, then `run-text-window-probe.py T-wprobe --graph text-window-probe.json`, timeout 2400. Must exit 0 (`window-qualified`). The timed graph's `pipeline-window` text encode needs it | 392-397 | 11-85 (`window-qualified`, `passed: true`), 86 |
| A04 | `worker-headroom-97.py plan two-way 2 2 1 --replicas xpu:2 --manifest M` → `OUT/headroom-plan.json`. Must exit 0 | 400-407 | 87 (`room_for_first_worker: true`) |
| A05-06 | queue empty, then `run-sampler-pin-95.py T-pin0 0 --graph sampler-pin.json`. Must exit 0 | 413, 425-426 | 88-98 (`outcome: pinned`, worker 0) |
| A07 | capture prompt 0: `run-throughput-fixtures-96.py T-cap0 --graph graph-capture-all48-pipe-samp2-tsh-win-b2.json --arm pipe-samp2-tsh-win-b2 --count 1 --index-base 50000000 --fixtures stability-01-window-prereg.json --order cycle --batch 2 --timeout 1803 --no-oracle` (outer timeout 2103) | 427 (via `arm`, 142-152) | 99-137 (1 prompt, pipeline fill, rc=0) |
| A08 | wait for `RUN/pipeline-done-sample-50000000.json`, 180 x 5 s. Each try also runs the failed-job check (imports `check-failed-jobs-97.find`), and a `pipeline-failed-*` receipt stops the run | 429-442 | marker written 04:08:08Z (r2 run dir) |
| A09 | sleep 5 | 443 | |
| A10-11 | queue empty, then room receipt for worker 1 (k ≥ FIRST_LIVE = 1): `run-capture-freeze-94.py T-room1 --graph sampler-capture-coverage.json`, rc ignored as in the runner, receipt copied to OUT | 413-416 | not printed in the log; `RUN/sampler-capture-coverage-…-room1.json` 04:08:15Z |
| A12 | `worker-headroom-97.py live RUN/…room1.json two-way 2 1 --replicas xpu:2 --manifest M` → `OUT/headroom-w1.json`. Must exit 0 (no PREV: worker 0 has no room receipt) | 417-423 | `data/place-97/two-way-w2-b2-p1-dxpu2-r2/headroom-w1.json` (`room_for_one_more_worker: true`) |
| A13 | `run-sampler-pin-95.py T-pin1 1` | 425-426 | 139-149 (`pinned`, worker 1) |
| A14 | capture prompt 1: same as A07 with `T-cap1`, `--index-base 50000010` | 427 | 150-188 |
| A15-16 | wait for `pipeline-done-sample-50000010.json`, then sleep 5 | 429-443 | marker 04:08:28Z |
| A17-18 | queue empty, then `run-capture-freeze-94.py T-cover --graph sampler-capture-coverage.json`, timeout 360. Must exit 0 (`covered`) | 445-450 | 190-204 (`covered`, 48 routes, 2 workers) |
| A19 | pool calibration (pool 1, W ≥ 2): `worker-headroom-97.py calibrate OUT/…room1.json OUT/…cover.json two-way 2 1 --manifest M --out OUT/pool-calibration.json`. Failure is logged and the run continues, as in the runner | 451-462 | 205-207 |
| A20-22 | settle 30 s, queue empty, then `run-decode-probe-97.py T-dprobe --graph decode-replica-probe.json --expect-replicas xpu:2`, timeout 1500. Must exit 0 (`replica-exact`) | 465-471 | 208-230 (`replica-exact`, 10/10) |
| A23-24 | queue empty, then the freeze: `run-capture-freeze-94.py T-freeze --graph sampler-capture-freeze.json`, timeout 360. Must exit 0 (`frozen`) | 474-479 | 231-255 (`frozen: true`, free/reserved per card) |
| A25-27 | settle 15 s, record t0, then the self-check through the exact timed path: `run-throughput-fixtures-96.py T-wself --graph graph-capture-all48-pipe-samp2-tsh-rep-wlean-b2-w2.json --arm pipe-samp2-tsh-rep-wlean-b2-w2 --count 9 --index-base 50000100 --fixtures W93C --order shift --batch 2 --timeout 1823 --no-oracle` | 482-487 | 256-327 (9 prompts, 7 fills, clips 0-1 emitted) |
| A28 | `selfcheck-94f.py --root R --run RUN --prefix T-wself --since t0` → `OUT/selfcheck.json`. Must exit 0 | 490-493 | 329-333 (`self_check: clean`) |
| A29-30 | settle 30 s, then check the b2 references are present (prereg batch 2, 10 fixtures, `tensors.safetensors` + `history.json` each) | 513-524 | 334-336 |
| A31-33 | settle 30 s, then proof arm `T-proofn`: `pipe-samp2-tsh-rep-wlean-b2-ref`, 13 prompts, base 50000300, `--fixtures stability-01-batch2-prereg.json --order proof-neighbours --timeout 1833`, compared byte-for-byte by the client (`compare-clip.py`), then `check-batch-proof-96.py --kind neighbours --expect-clips 10` | 532-536 | 337-425 (10/10 EXACT) |
| A34-35 | proof arm `T-proofs`: same with base 50000400, `--order proof-slots`, `--kind slots` | 537-544 | 426-515 (`proof arms passed`) |
| A36 | `check-decode-placement-97.py --replicas xpu:2 T-wself T-proofn T-proofs` → `OUT/decode-placement-warmup.json`. Must exit 0. The runner runs this after the timed arm (line 555), over these same three arms plus the timed one; here it runs before the stream because it only reads files | 555 (moved) | 3014-3015 |
| A37 | settle 60 s (the runner's settle before the timed arm) | 547 | 516 |

Any failed step stops the driver with exit 13 (6 for a failed-job receipt, 4 for FAULT.json). The server is
left exactly as it is. On success `state.json` records `warmup.passed` for this server's identity hash, so a
later run on the same server does not repeat Phase A. Phase A refuses to run if `T-w*` requests or a
`T-freeze` receipt already exist, because names must be unique and the capture pass is refused after a freeze.

### Runner steps skipped, and why

- `sample-gpu-engine-busy.py` (line 385) and `sync_watch` (125-133, 149): benchmark instrumentation.
- `save` / git commits (117-123): the owner reviews and commits.
- The SIGINT-honoured check (381-382): the driver never stops the server. It matters only for the owner's
  later graceful stop of the systemd unit.
- Quiescence and graceful stop (222-266), summary (292-296), `missing-markers-96.py`: the driver never stops
  the server.
- Timed arm, timed proof check, summary gate (547-558): Phase B replaces them.
- B=1 branches (placement probe vs w93c): not this combination.

The runner's `LTX_BUSY_WINDOWS=0` refusal (line 362) is kept as an environment check. The busy-window timers
are a benchmark feature, but the proven configuration runs with them off.

## Phase B: the stream

- **Graph and arm.** `graph-capture-all48-pipe-samp2-tsh-rep-wlean-b2-w2.json`, the runner's b2 timed arm. The
  per-prompt edits are those of `run-throughput-fixtures-96.py` (lines 186-198): every `run_name` gets the
  request name, every scalar `clip_index` gets the index, plus node 428 `stream_last`, node 364 text, and
  nodes 339/338 `noise_seed`. Requests are written the same way: `requests/<name>/prompt.json`,
  `identity.json`, `submission.json`, `history.json`, `result.json`. `compare-clip.py` needs these.
- **Names.** `s97-twowayw2b2p1dxpu2-stream01-NNNNNNN`, where NNNNNNN = index − 50,001,000.
- **Schedule.** Position p (one per prompt): fixture `p mod 10` in prereg order, `seed = fixture.seed + 1000 x
  (p div 10)`, label `"<id> seed <seed> cycle <c>"`. The runner's timed arm used order `shift`. Plain cycle
  order is used here as requested. The proof arms established that a b2 clip's bytes do not depend on its
  neighbours or slot, so the cycle-0 references still apply.
- **HTTP.** Only `POST /prompt`, `GET /history/<id>` for the single oldest outstanding prompt, and `GET /queue`.
  `/queue` is read only once, to resolve a POST whose outcome is unknown after a crash. ComfyUI runs prompts
  in order, so nothing else can have finished. In-flight stays ≤ `--in-flight`.
- **Pipeline.** Sampler depth 5 + decode depth 2: the prompt with clip i emits clip i − 7, so the first 7
  prompts are fills. The emitted clip is read from `pipeline-decode-<name>.json` `detail.emitted_index`. It
  must be the lowest submitted-but-unemitted clip, otherwise exit 12.
- **Finding the MP4.**
  - The preview is written by the writer thread under the prefix of the prompt that released the clip from
    the sampler, which is 5 prompts after its own: `output/<prefix>-<clip+5>/preview_00001_.mp4`.
    This is what r2 shows: `pipeline-save-…-timed-100.json` says prefix `…timed-98/preview`, and
    `pipeline-done-save-24000093.json` says saved `…timed-98/preview_00001_.mp4`.
  - The driver reads the emitting prompt's `pipeline-save-<name>.json` for the prefix. It then waits (up to
    `--save-wait`) for `pipeline-done-save-<clip index>.json`, joins its `saved` path to the server's
    `--output-directory` (from `server-args.json`), and checks the prefix matches and the file is non-empty.
  - It also requires every tensor in `output/validation/<emitting name>/summary.json` to be `finite`.
- **Quality gate.**
  - Every cycle-0 clip is compared with `compare-clip.py <stability-01-b2-<id>> <emitting name>`, exactly
    as the client does (`compare-clip-hash.py` if a reference lacks raw tensors). The comparison runs as a
    background subprocess, so polling continues meanwhile.
  - A clip goes into the manifest only after it passes. Any mismatch exits 3, and that clip and every later
    one stay unpublished.
- **Manifest.** One fsynced JSON line per clip in clip order: `seq`, `path`, `generated_utc` (the writer's
  `finished_unix`), `label`, `index`, `prompt_id` (the prompt that carried the clip's text and seed), plus
  `emitted_by_prompt_id`. Seq starts at 0, matching the sink's `last_played_seq = -1` default.
- **Log.** One line per clip: seq, index, label, interval between consecutive emitting prompts' server
  `execution_success` timestamps, the emitting prompt's execution seconds, decode split (seconds and card)
  from the decode receipt, the EXACT verdict, and the path. There is a status line every 60 s.
- **Throttle.**
  - With `--sink-stats` (the sink's `--stats` file), ahead = (last manifest seq − `last_played_seq`) + clips
    submitted but not yet in the manifest. Each clip counts as 25/24 s.
  - The driver submits only while ahead + 25/24 s ≤ `--max-ahead-seconds`. The pipeline tail of 7 clips
    counts.
  - If the file is missing or unreadable, only the in-flight cap applies. A stale file freezes the count,
    which errs on the side of holding.
- **State (`state.json`, atomic).**
  - Records next index, schedule position and seq; the outstanding prompts (with prompt ids); the
    submitted-but-unemitted clips; the open batch group fill; and the server identity hash.
  - Before each POST the driver records a `pending_submit`. A crash between the POST and recording it is
    resolved on restart from `/queue`, the request's `submission.json`, or the sampler receipt. A refused POST
    frees the index.
- **Resume, same server.** Indices continue consecutively, so the server treats the new run as the same
  stream. The previous run's 7 pipeline-tail clips are emitted first, so there is no gap and no reuse (tests
  B1, E3).
- **Resume, new server** (different identity hash).
  - The unemitted clips are lost with the old process. The schedule rewinds to the first lost position,
    which is re-submitted at fresh indices, so playback order stays continuous (test C1).
  - Phase A runs first unless `--skip-warmup`, and `--skip-warmup` refuses an unfrozen server.
- **SIGINT/SIGTERM.** Stop submitting. If the server's batch group is half full, submit one closing prompt
  with `stream_last=1`, exactly what every runner arm's last prompt does. Without it, any later stream that
  does not continue this index sequence would be refused by the grouper, and that refusal latches the
  sampler. Then drain until nothing is outstanding or `--timeout` passes, write state, and exit 0. A second
  signal writes state and exits 130.
- **Stops (no retry, no restart; state written).**

  | exit | cause |
  |---|---|
  | 2 | execution error, `node_errors`, or a refused POST |
  | 3 | reference mismatch or non-finite outputs |
  | 4 | `FAULT.json`, checked every cycle and before every request |
  | 5 | a GET failing for more than 120 s, or the server refusing connections for more than 120 s; immediately if a POST times out or fails mid-request (unknown state, never retried) or the server pid is gone |
  | 6 | any `pipeline-failed-*.json` newer than the stream start, checked every 5 s |
  | 7 | MP4 missing, empty, `save-failed`, or wrong prefix |
  | 9 | disk free below `--min-free-gib` (default 30) |
  | 12 | emission sequence wrong, or a request name reused |

- **Validation tensors.** By default each stream clip's `output/validation/<name>/tensors.safetensors`
  (20 MB) is deleted once the clip has been compared (cycle 0) or emitted (later cycles, and fills).
  `summary.json` with the four sha256s stays. Only names starting with the stream prefix are touched.
  `--keep-validation-tensors` turns this off. Without it the stream writes about 72 GB/h, against 57 GB free
  at the time of writing.

## Tests (no GPU, no server on 8188 touched; fake on 18188)

```bash
cd /home/steve/llm-optimizations/experiments/ltx25-b70/stream
/home/steve/.venvs/ltx25-baseline/bin/python -B tests/run_tests.py --tmp <scratch dir>     # 27/27 passed
```

- `tests/fake_comfy.py`: a stdlib HTTP server (`/prompt`, `/queue`, `/history/<id>`) that runs prompts one
  at a time with a configurable delay.
  - Mimics the real grouper: consecutive indices, no reuse, `stream_last`, and a latch on violation.
  - Mimics `run_behind` priming, Ds=5/Dd=2 emission, and writer-thread MP4s (a copy of r2's
    `…timed-100/preview_00001_.mp4`) under the releasing prompt's prefix.
  - Writes the save/done-save/decode/sampler receipts and per-prompt validation summaries.
  - Counts the maximum number of prompts in the server, and any `/history` poll that was not for the oldest
    uncompleted prompt.
- `tests/fake_compare.py`: the `compare-clip.py` CLI and report shape, comparing summary sha256s.

| test | checks |
|---|---|
| A1-A9 | 40+ clips: manifest seq/index/path continuity, seed schedule, cycle-0 EXACT ×10, ≤ 4 in server, 0 non-oldest polls, base 50,001,000, tensors pruned, clean state |
| B1-B3 | resume on the same server: tail emitted first, seq/index/labels continuous, grouper never refused |
| C1 | resume on a new server: lost positions re-submitted at fresh indices |
| D1-D4 | throttle at 20 s: holds at 19.8 s, no progress while held, releases as the sink advances, SIGINT while throttled exits 0 |
| E1-E3 | SIGINT mid-stream: one closing `stream_last` prompt, drained, exit 0, resume works |
| F1-F5 | execution error → 2; failed-job receipt → 6; FAULT.json → 4; server gone → 5 at once; server alive but hung → 5 after the window; reference mismatch → 3 with only the clips before it published |
| G1 | 200 clips sustained |

## Uncertain until the live server runs (please verify)

1. **In-flight 4 versus the runner's 600 queued.**
   - The text encode's lookahead (`run_ahead` depth 2) encodes ahead only for prompts already in the
     server's queue. With 4 in flight, 3 are pending, which is enough on paper. But the driver refills only
     after it sees a completion, one poll interval of 0.25 s plus the POST.
   - The r2 per-prompt executions are ~0.2 s, with the long waits inside sampler jobs. The queue may
     therefore drain to 1-2 between polls. Compare the logged interval (r2 steady mean 0.910 s/clip) and, if
     slower, try `--in-flight 6-8` or `--poll 0.1`.
2. **Phase A's validity for a stream.** The 15-30-60 s settles and the proof arms are copied as is. They add
   about 4-5 minutes and are not needed for correctness, but they are part of the proven preparation.
3. **The stop-time closing prompt** is one extra clip. It is emitted only if the next run continues on the
   same server. It closes the grouper exactly like a runner arm's last prompt. It has not been exercised on
   the real sampler.
4. **Disk.**
   - Even with tensors pruned, the server writes ~470 KB of receipts per prompt into the run dir, plus ~44 KB
     of requests and the 35 KB MP4. That is about 2 GB/h, so roughly 13 h from 57 GB free down to the 30 GiB
     guard.
   - The run dir grows by ~12 files per prompt. The failed-job scan (every 5 s) lists it, so its cost grows
     slowly.
   - Consider the sink's `--delete-played-after-seconds` with `--disposable-dir-regex
     's97-twowayw2b2p1dxpu2-stream01-[0-9]{7}'`. Each output dir holds exactly one clip.
5. **Server memory over very long runs.** These have not been measured past 600 prompts:
   - ComfyUI keeps up to 10,000 history entries, each holding the full graph.
   - The grouper's `used` set and per-prompt GIL/fingerprint records grow, mostly bounded.
6. **Pruning the validation tensors** is a write into the server's output tree. It follows the evidence rule
   (the sha256s stay) but is a policy choice for the owner. The default is on because the disk otherwise
   fills within the first hour.
7. **`compare-clip.py` on cycle 0.** It asserts that no node was `execution_cached`. ComfyUI runs with
   `--cache-none`, so this should hold as it did in r2.
8. **POST timeout.** This is now bounded by `--http-fail-seconds` (120 s) instead of the client's 300 s. A POST
   that times out exits 5 with an unknown submission, which the next start resolves. Before the freeze the
   web loop could stall for minutes during captures, but Phase A uses the runner's own clients for that part.
