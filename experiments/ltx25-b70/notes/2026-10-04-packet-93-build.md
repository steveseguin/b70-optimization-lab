# Packet 93: lean conditioning and the short-window text encoder (build, 2026-10-04)

Built offline. **Not launched.** R = `/mnt/fast-ai/bench-results/ltx25-baseline-20260913`.
No GPU was used to build or test it.

## In plain words

Two changes, each one switched on only by its own test arm:

1. **Lean conditioning** (exact by construction). Each clip ran the text
   "connector" layers four times on the same input; now it runs them once per
   clip and reuses the result only when the input bytes are identical. The
   output cannot change, and a hash check proves it in the run.
2. **Short-window text encoder** (**changes output at rounding level; owner
   decision pending**). The encoder works on the last 64-512 token positions
   instead of 1024 padded ones. Same mathematics, about five times less work,
   but not byte-identical to today's clips (the GPU's matrix kernels round
   differently for different row counts;
   [probe note](2026-10-04-encoder-suffix-window-probe.md)). So it gets its
   own reference set, made in the same run from two identical passes, and is
   never the default. The run records how far its clips are from today's
   (per-tensor differences and picture PSNR) for the owner to judge.

The launcher also learned the owner's 2026-10-03 rule "one fault does not end
the session": with `--health-receipt` it accepts earlier fault lines of this
boot if a passed four-card health probe came after them.

## What was built, part by part

| Part | Built | Where |
| --- | --- | --- |
| A window encoder | yes, graph-captured (see "Window implementation") | `scripts/ltx_text_window.py`, text mode `pipeline-window` in `scripts/pipeline_node.py` |
| B qualification probe | yes | `LTXTextWindowProbe` in `pipeline_node.py`, graph `graphs/text-window-probe.json`, prompts `probe/text-window-prompts.json`, client `scripts/run-text-window-probe.py` |
| B2 new oracle | yes | `scripts/make-window-oracle-93.py` |
| C lean conditioning + context sentry | yes | `scripts/ltx_lean_conditioning.py`, sampler mode `pipeline-lean` in `scripts/pipeline_sampler_node.py` |
| D hidden-state crop | **left out** | see below |
| E instruments | yes | sentries, done markers and CPU counters kept; runner requires `LTX_BUSY_WINDOWS=0`; engine sampler per run |
| F runner | yes | `scripts/run-campaign-93.sh`, summary `scripts/summarize-campaign-93.py` |
| G CPU tests | yes | `scripts/test-packet93-window-lean-cpu.py`, `scripts/test-packet93-health-admission-cpu.py` |
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
  passes run with it back at 1024: a graph replay does not read it. A timed
  windowed encode that would capture anything fails after the fact, so nothing
  is ever emitted from an unqualified graph.
- Bucket graphs are captured only inside the probe, never in a timed arm.

## What each probe proves, and what it does not

**Text-window probe** (receipt `text-window-probe-f93-wprobe.json`), on the two
encode workers in turn, 40 prompts (the ten fixtures plus the 30 synthetic
lengths of `scripts/probe-encoder-suffix-window.py`):

1. the certified 1024 encode of every prompt (the closeness reference);
2. per bucket, one capture encode: 48 layer graphs per worker, each with the
   lane capture proof (replay equals eager, bit for bit);
3. two windowed passes. Passes only if, per prompt, all four results (two
   workers x two passes) are byte-identical, and the relative difference
   (max |window - 1024| / max |1024| over the [1, N, 6144] conditioning) is at
   most 1e-3. Encode time per bucket and worker is recorded.

Outcomes: `window-qualified`, `window-not-deterministic`, `window-not-close`,
`window-capture-proof-failed`, `insufficient-memory`, `error`. Anything but the
first drops every window graph, puts the sliding window back, frees cached
blocks, and keeps `pipeline-window` refused (receipt, no latch); control and
lean are unaffected. It does not prove the final clip; B2 does that.

**Oracle (B2).** Two 13-prompt passes of `pipe-samp2-tsh-win`. Pass 1 and 2
must be byte-identical on all four tensors for all ten fixtures, else the
windowed identity is rejected and the 120-prompt arm is skipped. Accepted:
pass 1 is copied to new references `stability-01-w93-<fixture>` (existing
references untouched) with `data/stability-01-window-prereg.json`, and
`data/window-93/window-oracle-vs-1024-oracle.json` records per fixture and
tensor the max and mean absolute difference against the certified 1024 clip
(the pinned f90c captures) and picture PSNR in dB.

**Lean.** No probe: the reuse needs bitwise-equal input, asserted every time.
The context sentry hashes the context fed to the first diffusion forward of
each sampler stage in every pipelined arm, so control vs lean (and oracle vs
window+lean) are compared per fixture in the summary. Both lean arms are also
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

- CPU tests: `test-packet93-window-lean-cpu.py` 11/11 and
  `test-packet93-health-admission-cpu.py` 4/4; packet 90c/91/92a/92b and
  custom-node-import tests pass. Full lane sweep: 57 pass, 49 fail with
  identical exit codes on an untouched HEAD copy (stale historical tests:
  missing CLI arguments, old packets, the FAULT latch); the three
  packet-copying negative tests were not run (they write into R).

## Launch

Before launching (operator):

1. `R/FAULT.json` from the 02:46 UTC fault of this boot is still latched; every
   launcher (and the `--check-only` gate) refuses while it exists. Archive it
   (`mv R/FAULT.json R/FAULT.json.boot-73884bca-92b.archived`) as the owner
   rule allows once the health probe has passed. I did not move it.
2. The health receipt must be no older than 6 hours at launch. If
   `four-card-health-20261004T0325Z.json` (end 03:21:42 UTC) has expired, run
   `scripts/check-four-card-health.py <new receipt>` once and use that path.
3. Nothing else on the cards; a fault line after the receipt still refuses.

Server (busy timers off, SIGINT honoured so the runner can stop it):

```
R=/mnt/fast-ai/bench-results/ltx25-baseline-20260913
P=$R/prepared-encoder-window-93
nohup env --default-signal=INT LTX_BUSY_WINDOWS=0 /home/steve/.venvs/ltx25-baseline/bin/python -B $P/launch/serve-encoder.py --packet $P --manifest-sha256 997b2913dc612211ee6aa797376e6082e9d929c1b2a45c4cce554de013859efd --run-name encoder-server-window-93 --health-receipt /home/steve/llm-optimizations/experiments/ltx25-b70/data/health/four-card-health-20261004T0325Z.json > $R/encoder-server-window-93.log 2>&1 &
```

Runner:

```
nohup bash /home/steve/llm-optimizations/experiments/ltx25-b70/scripts/run-campaign-93.sh > /mnt/fast-ai/bench-results/ltx25-baseline-20260913/campaign-93.log 2>&1 &
```

The runner refuses unless the server is this packet, `LTX_BUSY_WINDOWS=0`, and
SIGINT is not ignored. It starts `sample-gpu-engine-busy.py` for the server
pid (fdinfo only) and ends by stopping the server on proven quiescence, then
checks the process is gone. If quiescence cannot be proven it leaves the
server up and exits 5/6/7 (a hard kill would itself fault the GPU).

| Step | Prompts | Index base | Bound | Verified against |
| --- | ---: | ---: | ---: | --- |
| warm `pipe-samp2-tsh` | 3 | 216000 | 900 s | - |
| decode probe | - | - | 1500 s | stored hashes |
| control `pipe-samp2-tsh-rep` | 40 | 216200 | 1800 s | existing references (36 clips) |
| lean `pipe-samp2-tsh-rep-lean` | 40 | 216400 | 1800 s | existing references (36 clips) |
| text-window probe | - | - | 1800 s | 1024 encode, both workers |
| oracle pass 1 `pipe-samp2-tsh-win` | 13 | 216600 | 1200 s | (old refs, mismatch expected) |
| oracle pass 2 | 13 | 216800 | 1200 s | pass 1 |
| window+lean `pipe-samp2-tsh-rep-wlean` | 120 | 217000 | 3600 s | NEW references (116 clips) |

Then `data/window-93/summary.json`: per arm clips verified, exact count,
interval median and mean, encode/sampler/decode job medians, compute-engine
busy seconds per clip per card (window from the sixth completed prompt), and
the context-sentry comparison.

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
- `make-window-oracle-93.py` writes new reference directories; its comparison
  logic is CPU-tested, the copy path is not exercised offline.
- The launcher's `journalctl --since '<end_utc>'` (same format as its existing
  watcher).
