# Packets 93 / 93b / 93c: lean conditioning and the short-window text encoder (build, 2026-10-04)

Built offline. **Not launched.** R = `/mnt/fast-ai/bench-results/ltx25-baseline-20260913`.
No GPU was used to build or test either packet.

**Launch 93c.** `prepared-encoder-window-93c`, manifest
`b02b844ed5e15d40113e3d3d2fbd5e2e41c20d656be54a2f4b6423eb581ffdc8`, run name
`encoder-server-window-93c`, runner `scripts/run-campaign-93c.sh`. 93 and 93b
stay in place; their runners refuse.

### 93b result, and why 93c

93b ran once (`data/window-93b/`): control 36/36 exact, lean 36/36 exact, the
context sentry identical on 10/10 fixtures, no fault, clean stop. The window
probe was deterministic on both workers, captured all 384 graphs with memory
to spare, and encoded in 0.343 s at W = 64 against 1.70 s at 1024, but it
refused with `window-not-close`. The bound was wrong for this tensor, not the
window: the compared conditioning is the output of the bf16 projection
(`lt.py` casts the hidden-state stack to bfloat16 before
`text_embedding_projection` and returns the bf16 result as fp32), so every
value is a bf16 number. Checked in the receipt: every fixture's max_abs is
0.125 or 0.25, exactly one bf16 step at magnitudes 16-32 and 32-64, against
max |full| of 40.5-51.25 (step 0.25 there), with mean_abs about 1e-4. One
step is 0.4-0.8 % of such an element, so max|d| / max|full| <= 1e-3 could
never pass and said nothing about a bug.

**93c changes only that definition.** Per prompt, ALL of:
(a) mean |window - full| / mean |full| <= 1e-3;
(b) max |window - full| <= 2 bf16 steps at the largest magnitude in the full
tensor, step = 2^(floor(log2 max|full|) - 7);
(c) the share of elements that differ at all <= 5 %;
(d) no non-finite value in either tensor.
All four numbers and the count of differing elements are in the receipt;
the old max/max figure stays there as `rel_max_over_max`, for information
only. Anything outside these still fails the probe as a bug. New references
are named `stability-01-w93c-*`; arms, order, oracle strictness and the
finished-clip table are unchanged. Index bases 218800 / 219000 / 219200 /
219400 / 219600 / 219800.

Gate (`--check-only`, 2026-10-04 04:33 UTC, no `R/FAULT.json`): passes with and
without `--health-receipt data/health/four-card-health-20261004T0413Z.json`
(receipt sha 98acad3f..., end 04:13:30 UTC). CPU tests: window/lean 14/14
(judge cases: a one-step flip on 0.1 % of elements passes; three steps, a 10 %
differing share or a NaN fails), health 6/6, runner tools 4/4, packets
90c-92b and custom-node imports pass.

Launch (93c; the receipt must be under 6 hours old and the journal clean since
its end):

```
R=/mnt/fast-ai/bench-results/ltx25-baseline-20260913
P=$R/prepared-encoder-window-93c
nohup env --default-signal=INT LTX_BUSY_WINDOWS=0 /home/steve/.venvs/ltx25-baseline/bin/python -B $P/launch/serve-encoder.py --packet $P --manifest-sha256 b02b844ed5e15d40113e3d3d2fbd5e2e41c20d656be54a2f4b6423eb581ffdc8 --run-name encoder-server-window-93c --health-receipt /home/steve/llm-optimizations/experiments/ltx25-b70/data/health/four-card-health-20261004T0413Z.json > $R/encoder-server-window-93c.log 2>&1 &
nohup bash /home/steve/llm-optimizations/experiments/ltx25-b70/scripts/run-campaign-93c.sh > $R/campaign-93c.log 2>&1 &
```

The sections below describe 93/93b; everything there holds for 93c except
the closeness definition, names, index bases and manifest above.

### 93b over 93

`prepared-encoder-window-93` (manifest `997b2913...`)
stays in place, unlaunched and superseded; `run-campaign-93.sh` refuses to
start. A review found these defects in 93, all fixed in 93b:

1. A timed window encode ran before checking that its graphs existed, so a
   missing signature would have been captured during live work (and the
   1024 fallback had no check at all). 93b refuses such a request before
   anything runs: on the prompt thread for every encode worker, again on the
   worker, and a capture guard raises before any capture while a timed encode
   runs. Refusals write a receipt and latch nothing.
2. The oracle compared summary hashes only and accepted the same pass twice.
   93b loads and re-hashes both passes' tensor files, compares layout and
   bytes, requires two distinct successful executions on the same server and
   packet, and requires every clip's own receipt to show the window bucket.
3. The health-receipt check admitted bare `{"pass": true}` cards and end times
   up to two minutes in the future. 93b requires the probe's full evidence
   inside its own thresholds and rejects any end time later than now; the
   receipt's sha256 is written into the run directory.
4. The start-check journal snapshot ended before the watcher's window began
   (a gap), and the launcher missed `Timedout job` and `wedged`. 93b starts
   the watcher's window before the snapshots and uses one signature list that
   covers the health probe's.
5. The runner had no trap: an interrupted runner now tries the same graceful
   stop once (never a kill) and says plainly if the server is still up.
6. The stop waited for jobs that were never submitted; 93b expects only jobs
   the server actually queued (`scripts/missing-markers-93b.py`).
7. The context-sentry comparison is now a gate: ten fixtures, non-null hashes,
   equal between control and lean (and oracle and window+lean), or the
   campaign fails (exit 14).
8. The finished-clip comparison (the owner's first condition) is explicit and
   printed at the end (see B2).
9. A hung probe worker can no longer block the server: the probe has a
   1200 s server-side bound, fails cleanly and leaves the window refused.

**Owner decision (2026-10-04):** the short-window encoder is approved on two
conditions: the finished-clip difference is negligible, and new references are
made with it, against which the byte-identical rule then applies. Its label
everywhere: "changes output at rounding level; owner approved 2026-10-04 on two
conditions (negligible finished-clip difference; new references,
byte-identical thereafter)". The numbers for the first condition are recorded,
not judged, by the run.

## In plain words

Two changes, each one switched on only by its own test arm:

1. **Lean conditioning** (exact by construction). Each clip ran the text
   "connector" layers four times on the same input; now it runs them once per
   clip and reuses the result only when the input bytes are identical. The
   output cannot change, and a hash check proves it in the run.
2. **Short-window text encoder** (**changes output at rounding level; owner
   approved on two conditions, above**). The encoder works on the last 64-512 token positions
   instead of 1024 padded ones. Same mathematics, about five times less work,
   but not byte-identical to today's clips (the GPU's matrix kernels round
   differently for different row counts;
   [probe note](2026-10-04-encoder-suffix-window-probe.md)). So it gets its
   own reference set, made in the same run from two identical passes, and is
   never the default. The run records how far its clips are from today's
   (picture PSNR and pixel differences, sound SNR, latent differences).

The launcher also learned the owner's 2026-10-03 rule "one fault does not end
the session": with `--health-receipt` it accepts earlier fault lines of this
boot if a passed four-card health probe came after them.

## What was built, part by part

| Part | Built | Where |
| --- | --- | --- |
| A window encoder | yes, graph-captured (see "Window implementation") | `scripts/ltx_text_window.py`, text mode `pipeline-window` in `scripts/pipeline_node.py` |
| B qualification probe | yes | `LTXTextWindowProbe` in `pipeline_node.py`, graph `graphs/text-window-probe.json`, prompts `probe/text-window-prompts.json`, client `scripts/run-text-window-probe.py` |
| B2 new oracle | yes (93b: strict) | `scripts/make-window-oracle-93.py` |
| C lean conditioning + context sentry | yes | `scripts/ltx_lean_conditioning.py`, sampler mode `pipeline-lean` in `scripts/pipeline_sampler_node.py` |
| D hidden-state crop | **left out** | see below |
| E instruments | yes | sentries, done markers and CPU counters kept; runner requires `LTX_BUSY_WINDOWS=0`; engine sampler per run |
| F runner | yes | `scripts/run-campaign-93b.sh` (93's refuses), summary/gate `scripts/summarize-campaign-93.py`, `scripts/missing-markers-93b.py` |
| G CPU tests | yes | `scripts/test-packet93-window-lean-cpu.py`, `scripts/test-packet93-health-admission-cpu.py`, `scripts/test-packet93b-runner-tools-cpu.py` |
| Launcher same-boot admission | yes | `scripts/serve-encoder-93.py` (shipped as `launch/serve-encoder.py`) |

New arms (the generator `scripts/prepare-graph-capture-runtime.py` adds them;
every older arm and graph is unchanged):

| Arm | Decode placement | Text encode | Sampler |
| --- | --- | --- | --- |
| `pipe-samp2-tsh-rep` (control, existing) | replica (xpu:3 + xpu:1) | 1024 | `pipeline` |
| `pipe-samp2-tsh-rep-lean` | replica | 1024 | `pipeline-lean` |
| `pipe-samp2-tsh-win` (oracle passes) | xpu:3 (3 fill prompts, so 13 prompts emit all ten fixtures) | window | `pipeline` |
| `pipe-samp2-tsh-rep-wlean` | replica | window | `pipeline-lean` |

**Part D left out.** The crop flag `ltx_crop_before_cpu` is refused by
`host_embedding_clip_threadsafe.load_clip` for every packet; admitting it
means loosening that general check, which is not trivial. Its payoff is copy
traffic, not compute.

## Window implementation, and why

The window runs through the **same per-layer graph stand-ins** as the 1024
encode (`ltx_graph_text_encoder.GraphedLayer`, unchanged). A W-token encode
has a different argument signature, so each layer captures one more graph per
bucket per encode worker, with the lane's existing capture proof (replay
bit-equal to a fresh eager call of that layer on the same inputs, and
non-inert) and the existing per-(device, thread) pools. This was the smaller
change: an eager window would have needed a bypass of the stand-ins plus its
own copy of the xpu:2 -> xpu:3 layer staging, while the graph path needs
neither. No line of the 1024 path changed.

Details:

- Policy (in every receipt): W = smallest admitted bucket in
  64/128/256/512/1024 that holds the real token count (BOS included); 1024 is
  the certified encode, called exactly as the native node calls it.
- Position ids 1024-W..1023 are injected by a wrapper on the Gemma stack's
  forward that acts only on a thread that is running a windowed encode (it is
  installed at the first window encode, i.e. after the control and lean arms).
- The sliding layers' window is set to W **only while the probe captures**
  (pipeline idle, the two workers strictly one after the other). The timed
  passes run with it back at 1024: a graph replay does not read it.
- Bucket graphs are captured only inside the probe, never in a timed arm.
  93b enforces this before execution: a windowed request (or its 1024
  fallback, or a prompt longer than 1024 tokens) whose row count lacks a
  captured graph on any layer of any encode worker is refused with a receipt
  before anything runs; a lookahead job is not queued for it; and a capture
  guard on `GraphedLayer._capture` raises if a capture is attempted on a
  thread running a timed encode.

## What each probe proves, and what it does not

**Text-window probe** (receipt `text-window-probe-f93b-wprobe.json`), on the two
encode workers in turn, 40 prompts (the ten fixtures plus the 30 synthetic
lengths of `scripts/probe-encoder-suffix-window.py`):

1. the certified 1024 encode of every prompt (the closeness reference);
2. per bucket, one capture encode: 48 layer graphs per worker, each with the
   lane capture proof (replay equals eager, bit for bit);
3. two windowed passes. Passes only if, per prompt, all four results (two
   workers x two passes) are byte-identical, and the relative difference
   (max |window - 1024| / max |1024| over the [1, N, 6144] conditioning) is at
   most 1e-3 (93/93b; replaced in 93c by the four-part bf16-aware test at the
   top of this note). Encode time per bucket and worker is recorded.

Outcomes: `window-qualified`, `window-not-deterministic`, `window-not-close`,
`window-capture-proof-failed`, `insufficient-memory`, `error`. Anything but the
first drops every window graph, puts the sliding window back, frees cached
blocks, and keeps `pipeline-window` refused (receipt, no latch); control and
lean are unaffected. The whole probe is bounded at 1200 s on the server; on
expiry it fails, the window stays refused, the workers stop at their next
prompt, and the window graphs are not released while a worker may hold them.
It does not prove the final clip; B2 does that.

**Oracle (B2).** Two 13-prompt passes of `pipe-samp2-tsh-win`. Refused (exit
10, nothing stored, window+lean arm skipped) unless: each pass emitted all ten
fixtures; the passes are distinct successful executions (different prefixes,
request names, index ranges and timestamps; same server pid, start ticks, boot
and packet manifest); every emitted clip's own encode receipt shows
`pipeline-window`, its bucket (< 1024), its clip index and no capture; and both
passes' tensor files, re-hashed against their summaries, are equal in layout
and bytes on all four tensors. Accepted: pass 1 is copied to new references
`stability-01-w93b-<fixture>` (existing references untouched) with
`data/stability-01-window-prereg.json`.

**Finished-clip comparison (owner's first condition)**,
`data/window-93b/window-oracle-vs-1024-oracle.json`, per fixture against the
certified 1024 clip (the pinned f90c captures): images: PSNR dB, max and mean
abs difference on the 0-255 scale, fraction of pixels with any channel off by
more than 1/255; waveform: max and mean abs difference and SNR dB; both
latents: max and mean abs difference. No threshold is applied; the runner
prints the table at the end and copies it into `summary.json`.

**Lean.** No probe: the reuse needs bitwise-equal input, asserted every time.
The context sentry hashes the context fed to the first diffusion forward of
each sampler stage in every pipelined arm. 93b makes it a gate: all ten
fixtures, non-null hashes, one equal pair per fixture between control and lean
(and oracle pass 1 and window+lean), else the summary exits non-zero and the
campaign fails (exit 14). Both lean arms are also
checked clip by clip against references (control/lean against the existing
ones, window+lean against the new ones).

**Decode probe.** Unchanged from 91b; every arm except warm and the oracle
passes uses the replica placement, so if it fails the runner stops cleanly.

## VRAM (encoder cards)

| | xpu:2 | xpu:3 |
| --- | --- | --- |
| Peak reserved / allocated, 91c receipts | 21.59 / 17.40 GiB | 16.64 / 14.22 GiB |
| Device total | 31.89 GiB | 31.89 GiB |
| Room outside torch's reserve (less ~0.5 GiB driver) | ~9.8 GiB | ~14.7 GiB |
| Window static buffers, all four buckets, 24 layers x 2 workers | ~1.0 GiB | ~1.0 GiB |
| of which W = 64 (all ten fixtures) | 67 MB | 67 MB |
| Pool growth, upper bound (transients scale with W) | ~0.4 GiB | ~0.4 GiB |

Per layer per worker the statics are 21 504·W + 4·W² bytes (hidden state,
RoPE tables, mask). The probe captures a bucket only with at least 3 GiB free
on both cards and fails below 2 GiB after the probe; a bucket that does not fit
is not admitted and its prompts take the certified 1024 path.

## Packet, gate and tests

### 93b (launch this one)

- `R/prepared-encoder-window-93b`, **manifest sha256
  `655eac5725d9429a28cb0b4e87340a0c2a556d477aa0bbf5bf7b735c9db4db55`**. Same
  inventory as 93; `ltx_text_window.py`, `pipeline_node.py` (and its node
  copy), `launch/serve-encoder.py` and the label in the manifest differ.
- Gate (`--check-only`), 2026-10-04 04:09 UTC, `R/FAULT.json` already archived
  by the operator: **passes**, with and without the receipt (rc 0):

```
{"status": "inactive-startup-check-passed",
 "run_dir": ".../encoder-server-window-93b",
 "packet_manifest_sha256": "655eac5725d9429a28cb0b4e87340a0c2a556d477aa0bbf5bf7b735c9db4db55",
 "health_receipt": {"sha256": "54be59348f0d...", "end_utc": "2026-10-04 03:21:42 UTC",
   "boot_id": "73884bca-1022-490a-91be-af7f713c5813", "verified": "schema, passed, four cards, boot id, age; ..."}}
```

- CPU tests: window/lean 14/14, health admission 6/6, runner tools 4/4;
  packet 90c/91/92a/92b and custom-node imports pass. Full lane sweep: 61
  pass, 46 fail, every one of them already failing before packet 93 (same exit
  codes on an untouched HEAD copy; three earlier failures now pass because the
  FAULT latch is gone). The three packet-copying negative tests were not run.

### 93 (superseded, never launched)

- `R/prepared-encoder-window-93`, **manifest sha256
  `997b2913dc612211ee6aa797376e6082e9d929c1b2a45c4cce554de013859efd`**.
  Compared with 92b: added the two modules, three arm graphs, the window probe
  graph and prompts, and the packet13 launcher under provenance/; changed the
  checker and `launch/serve-encoder.py`; every other inherited file identical.
- Gate (`--check-only`), as run on 2026-10-04 03:52 UTC: **refuses with
  `Fault recorded; halt new work`** because `R/FAULT.json` is latched (step 1
  below). With only that latch check skipped in-process (file untouched), the
  gate passes with and without the receipt:

```
{"status": "inactive-startup-check-passed",
 "run_dir": ".../encoder-server-window-93",
 "packet_manifest_sha256": "997b2913dc612211ee6aa797376e6082e9d929c1b2a45c4cce554de013859efd",
 "health_receipt": {"sha256": "54be5934...", "end_utc": "2026-10-04 03:21:42 UTC",
   "boot_id": "73884bca-...", "verified": "schema, passed, four cards, boot id, age; ..."}}
```

- CPU tests at the time: `test-packet93-window-lean-cpu.py` 11/11 and
  `test-packet93-health-admission-cpu.py` 4/4; packet 90c/91/92a/92b and
  custom-node-import tests pass. Full lane sweep: 57 pass, 49 fail with
  identical exit codes on an untouched HEAD copy (stale historical tests:
  missing CLI arguments, old packets, the FAULT latch); the three
  packet-copying negative tests were not run (they write into R).

## Launch

Before launching (operator):

1. No `R/FAULT.json` (the 02:46 UTC one has been archived by the operator).
2. The health receipt must be no older than 6 hours at launch. If
   `four-card-health-20261004T0325Z.json` (end 03:21:42 UTC) has expired, run
   `scripts/check-four-card-health.py <new receipt>` once and use that path.
3. Nothing else on the cards; a fault line after the receipt still refuses.

Server (busy timers off, SIGINT honoured so the runner can stop it):

```
R=/mnt/fast-ai/bench-results/ltx25-baseline-20260913
P=$R/prepared-encoder-window-93b
nohup env --default-signal=INT LTX_BUSY_WINDOWS=0 /home/steve/.venvs/ltx25-baseline/bin/python -B $P/launch/serve-encoder.py --packet $P --manifest-sha256 655eac5725d9429a28cb0b4e87340a0c2a556d477aa0bbf5bf7b735c9db4db55 --run-name encoder-server-window-93b --health-receipt /home/steve/llm-optimizations/experiments/ltx25-b70/data/health/four-card-health-20261004T0325Z.json > $R/encoder-server-window-93b.log 2>&1 &
```

Runner:

```
nohup bash /home/steve/llm-optimizations/experiments/ltx25-b70/scripts/run-campaign-93b.sh > /mnt/fast-ai/bench-results/ltx25-baseline-20260913/campaign-93b.log 2>&1 &
```

The runner refuses unless the server is this packet, `LTX_BUSY_WINDOWS=0`, and
SIGINT is not ignored. It starts `sample-gpu-engine-busy.py` for the server
pid (fdinfo only) and ends by stopping the server on proven quiescence, then
checks the process is gone. If quiescence cannot be proven it leaves the
server up and exits 5/6/7 (a hard kill would itself fault the GPU). If the
runner is interrupted (INT/TERM) or exits early after it has identified the
server, it tries the same graceful stop once and reports whether the server is
still up (exit 13 when interrupted and stopped).

| Step | Prompts | Index base | Bound | Verified against |
| --- | ---: | ---: | ---: | --- |
| warm `pipe-samp2-tsh` | 3 | 217400 | 900 s | - |
| decode probe | - | - | 1500 s | stored hashes |
| control `pipe-samp2-tsh-rep` | 40 | 217600 | 1800 s | existing references (36 clips) |
| lean `pipe-samp2-tsh-rep-lean` | 40 | 217800 | 1800 s | existing references (36 clips) |
| text-window probe | - | - | 1800 s | 1024 encode, both workers |
| oracle pass 1 `pipe-samp2-tsh-win` | 13 | 218000 | 1200 s | (old refs, mismatch expected) |
| oracle pass 2 | 13 | 218200 | 1200 s | pass 1 |
| window+lean `pipe-samp2-tsh-rep-wlean` | 120 | 218400 | 3600 s | NEW references (116 clips) |

Then `data/window-93b/summary.json`: per arm clips verified, exact count,
interval median (all intervals) and mean (steady), encode/sampler/decode job
medians, compute-engine busy seconds per clip per card (window from the sixth
completed prompt), the context-sentry gate, and the finished-clip table.

## Expected outcomes

- Control and lean: all exact; identical context hashes per fixture; lean
  saves the three repeated connector passes (~0.1-0.2 GPU-s on xpu:0).
- Window probe: qualifies (eager probes were deterministic; relative
  differences ~1e-5); oracle passes identical; window+lean exact against the
  new references. Expected encode cost ~0.3-0.4 GPU-s per clip instead of ~2;
  the interval should then be set by the sampler cards.

## Unverified offline

- Whether each window graph replays bit-equal to eager (the probe decides) and
  whether the replay is as fast as hoped (eager W = 64 measured 0.30 s).
- The real pool growth of the extra captures (the probe records free memory).
- That `preprocess_text_embeds` is called four times per clip with
  byte-identical inputs (the receipts count computed/reused calls).
- The sentry's device-to-host copy adds one sync per stage to every pipelined
  arm, control included; output is untouched, timing cost expected well under
  1 %.
- `make-window-oracle-93.py` is CPU-tested end to end on a synthetic results
  root (accept and seven refusal cases); not yet on real server receipts.
- The runner's INT/TERM/EXIT trap is reviewed, not exercised (bash runs a
  trap only after the current foreground client returns; every client call
  is bounded by `timeout`).
- The capture guard patches `GraphedLayer._capture` at the first timed window
  encode; it is tested on a stand-in class, not on the real one.
- The launcher's `journalctl --since '<end_utc>'` (same format as its existing
  watcher).
