# LTX continuation 119: keep the cone gain without blocking the next chunk

2026-10-10. CPU preparation only. No GPU work, server operation, launch rehearsal,
port access, signals, unit operation or host setting change was performed. The
coordinator's live server and existing run directories were read-only.

Parent: sealed **118b**, manifest
`248e762de49d21b02a4f95d3791dbd9da7504b731f1a88cb5a930a78448db1f1`.
This follows the [118 design](2026-10-09-continuation118-stream-design.md) and
[118b rebuild](2026-10-09-continuation118b-rebuild.md): separate author tree,
exclusive new packet, inherited numerical sources, recursive manifest closure,
three-chain byte gate, and no XPU claim from CPU tests.

## Evidence and corrected interpretation

The [dg0 result](2026-10-10-continuation118b-results-121-dg0.md) measured 5.227 s
per 121-frame, 5.041667-second chunk. The [117 result](2026-10-09-continuation117-results-121.md)
provides its earlier baseline. The dg1 cap1 run qualified exact, verdict prefix
`493c3b66a3ec`; its pre-diffusion method is captured and diffusion step remains eager.

[Evidence JSON](../data/resume-20261008/continuation119-evidence.json) contains the
fixed matched sample, per-chunk data, paths, hashes and read timestamps.
[Analyzer](../recovery/20261010-continuation119-stream/analyze_evidence_119.py)
reads only files. Both manifests and client logs were read; live files can grow,
so their hashes identify the bytes observed, not a claim that they are immutable.
The paired sample is sequence 10–35 (26 periods), with image and waveform identity
checked on sequences 0–36 (37/37 exact).

| Median, seconds | 118b dg0 | 118b dg1 cap1 |
|---|---:|---:|
| Submit to next submit | 5.226284 | 5.559306 |
| Upsample + B preparation | 0.282523 | 0.790991 |
| Cone on the chain | 0.916872 | 0.760200 |
| Display off the chain | 2.653149 | 2.116919 |
| Actual sampler-A go wait | 0.262651 | 0.243227 |
| Upsampler start to condition-B start | about 0.038 | about 0.506 |
| B precompute | about 0.149 | about 0.144 |
| B-before / B-after snapshots | 0.057 / 0.056 | 0.058 / 0.057 |

With dg1 the previous display finishes a median 1.14 ms **before** the next
condition-B node starts. With dg0 that node starts about 0.993 s before the
display finishes. B's precomputed encode takes about 0.028–0.030 s and consuming
it waits only 6–7 microseconds. Thus the penalty is in the upsampler, **before**
B's snapshot/conditioning, not in a slow precompute or a longer go wait.
The native upsampler does device work and copies its result to the intermediate
device before returning. Receipts strongly support shared-device blocking; they
do not prove the precise blocking call, driver queue submission granularity,
or the asserted single-CCS topology. No profiler or hardware tool was used.

Another correction matters for lever C. A-before's dg0 inspector timer is
0.057330 s, consisting of state 0.027028, facts 0.025538, residence 0.002814 and
memory/synchronization **0.000867 s**. A-after's memory part is 0.000883 s.
The controller also synchronizes before entering this timer; that duration is
not separately measured. The earlier statement that all 0.059 s is synchronization
is not supported by these subdivisions. Removing barriers may save almost nothing.

## A: graph cone, eager display; optional deferred display

`LTX_DISPLAY_SCHEDULE=sampler-a|eager-display|sampler-b`, default `sampler-a`.
All modes retain one decode thread, bounded FIFO, native tensor operations,
exclusive frame files, and **display last frame == cone anchor on every chunk**.
Nondefault display modes require frame/cone; eager-display with dg0 is an
explicit no-op for decode arithmetic.

**Recommended arm: eager-display.** The cone retains the qualified graph path.
The full display decode uses the original uncached eager path, exactly the path
used for the existing decoder reference gate. This restores the interleaving
seen in dg0 without postponing all display work. With dg1 only
`forward_pre_diffusion` has a signature/capture; `forward_diff_step` has zero
signatures, no capture and no capped entry. Qualification explicitly requires
that identity, plus the uncached reference comparison and unchanged cross-chain
image, latent, waveform and anchor comparisons. A graph cone followed by eager
full display is tested on the real sealed tiny decoder in FP32 and BF16, including
frozen replay. This does not prove full-model XPU identity.

**Alternative: sampler-b.** B's precompute still starts after sampler A, avoiding
a dependency deadlock. Full display waits until the actual consuming request's
sampler-B event, keyed by predecessor run name **and** anchor hash. A reset,
unrelated request or same hash from another chain cannot release it as a match.
The original A wait and the new B wait share one three-second deadline; B
precompute consumes that same budget. On expiry display proceeds and records
`bound`; no retry, unbounded wait or server cycle is introduced. This is a
bounded scheduling preference, not a guarantee that B was reached before every
display. Gated qualification cannot have a successor in flight and bypasses
this wait explicitly. The later live gate must exercise matching releases and
reject bound fallback for speed admission (exclude the terminal chunk when
there is intentionally no successor).

Delaying display may lose: B takes about 1.33 s, shorter than the 2.12 s display.
The decode FIFO could then delay the next cone by around 0.8 s. Measure the
whole submit period, decode queue wait and final display completion, not just
the shortened upsample bucket.

**Off form:** sampler-a is 118b's scheduling and display graph choice. No new
barrier event changes its order. Existing snapshot/pool choices remain available.

**Replica arm dropped.** `LTX_DECODE_REPLICA_DEVICE=xpu:2` is an environment
compatibility setting here. The stream instantiates **zero replicas**, pins the
native video VAE on xpu:3 and refuses nonzero replica state. Moving display to
xpu:2 needs a new residency/memory/cross-card exactness design; it is not a safe
launch-variable toggle in packet119.

## B: verified anchor read-ahead, without guessing successor text

`LTX_ANCHOR_READ_AHEAD=0|1`, default `0`. After the receipt commits, before stage-A
encode prep, the decode thread reads and verifies its just-written anchor using
the native reader. It retains at most one immutable CPU byte string. The consumer
checks the absolute regular single-link path, no symlinks, inode/device/size,
mtime/ctime, expected hash and a fresh SHA of the cached bytes. Changed files use
the native reader and therefore still fail on wrong bytes; a race/miss also uses
the native reader. The frame is reconstructed as before; conditioning guards
still inspect its metadata, finiteness and hash. Qualification must exercise a
verified hit on each anchored graph/repeat chunk; stream hit/miss counts remain
visible. Off means the original read/finite scan at the consumer.

This removes only repeated file reading and the native Python finite scan. It
does not remove the guard's checks or text window/reuse work. The successor's
prompt/scene/reset is unknown at receipt commit, and the window machinery is
owned by the admitted prompt thread. Moving guessed text work is rejected.
There is no claim that all of the 0.12 s bucket disappears.

Memory: one 786,432-byte frame (0.75 MiB), briefly two byte strings during
replacement, plus small metadata. No new GPU tensor cache, model or graph pool.

## C: owner-only stage-A barrier reduction

`LTX_SNAPSHOT_SCHEDULE=full|a-xpu3-sync`, default **full**; reduced barriers require
fingerprint mode. This is deliberately narrower than replacing the entire A
snapshot with an xpu:3-only snapshot. It does not return stale or fabricated
readings to the safety controller.

On nondual streaming chunks only, A-before and A-after synchronize xpu:3; both
the controller's injected synchronize callback and the inspector's memory read
path apply the selection. They still read **all four** current free-memory and
allocator counters, check every residence/ownership fact, plan/runtime/phase,
routes, controller state and VAE bindings. Request-before, request-after and
B-before/B-after retain full barriers. Setup, every qualification snapshot,
every 20th stream chunk and near-floor dual escalation also retain full barriers.
A near-floor reading escalates the current snapshot and the rest of its chunk.
Receipts list the actual synchronized cards and all four memory-reading cards.

| Check | full | a-xpu3-sync |
|---|---|---|
| P1 controller available; P2 phase/authority; P3 fault observer | retained | retained |
| P4 xpu:3 completion barrier | retained | retained |
| xpu:0/1/2 completion barriers at A-before/A-after | retained | **lost on eligible stream chunks** |
| P5 xpu:3 9 GiB before / 2 GiB after | retained | retained, fresh reading |
| xpu:0/1/2 floors 8/8/2 GiB before, 2/2/2 GiB after | retained | retained, fresh readings, without completion barriers |
| P6 allocator validity on all cards | retained | retained |
| P7 all-role ownership/residence; P8 both VAE bindings | retained | retained |
| E1 encoder lock, E2 anchor bytes/metadata, E3 cache, E4 bindings | retained | retained |

The trade is delayed visibility of asynchronous errors/completion on xpu:0/1/2,
and readings that do not certify completion of their previously queued work at
those two A sites. Later full snapshots remain. Owner approval is needed **to
select this safety trade**, not to build or test it on CPU. It is not in the
recommended first command. Merging A-after into dispatch is not implemented:
it would remove an immediate post-call observation and provides no evidenced
benefit over the narrower option. The normal P1–P8 precompute snapshots remain
unchanged in every mode. No floor is lowered.

## D: other measured buckets

Stage-A consume (0.055 s) includes native input/output hash checks, clone and
conditioning. Removing those weakens its existing exactness proof; no cheap
replacement is justified tonight. Before-request checks (0.035 s) bind authority,
plan, registry and admission; caching their result would skip dynamic checks.
Both are closed for this packet. New instrumentation records proof-path usage;
no host tuning, lower precision, decoder movement or arithmetic change is included.

## Preregistered predictions and gates

These are estimates, not measurements or a claimed record. Use matched scenes,
seeds, chain start, 121 frames, frame/cone/bo1/pa1, same sampler layout and text
reuse. Report medians of 100 interior stream chunks after the first ten, plus
range/tail, raw period intervals and full output comparisons. Preserve earlier
highs and use fresh-run repeats before a speed verdict; the coordinator owns
all operational stages. No launch is performed by this CPU task.

| Arm | Predicted median period | Interpretation / falsification |
|---|---|---|
| all new options off, dg0 | 5.15–5.40 s | must retain118b byte output; diagnostic packet overhead comparison |
| eager-display, dg1 cap1, read-ahead off, full snapshots | 4.98–5.20 s, central 5.07 | cone gain ~0.16 s; upsample+B should return toward 0.28 s |
| eager-display + read-ahead, full snapshots | **4.95–5.17 s, central 5.04** | read gain estimated 0.00–0.06 s; sub-real-time is plausible, not established |
| sampler-b, dg1 cap1 | 5.1–5.9 s | may move wait into FIFO; reject if whole period loses |
| a-xpu3-sync incremental | 0.00–0.06 s saving, low confidence | no supported 0.12 s promise; preserve all floors and live scopes |

121/24 = 5.041667 s; the requested rounded 5.04 s threshold is used above.
An anchored chunk contributes 120 new frames (5.0 s), so strictly keeping up
with *new* delivered video requires a period below **5.0 s**, not merely 5.04.
Report both denominators rather than silently counting the repeated anchor.

Memory: no extra VAE replica; graph-cone/eager-display retains at most the same
pre-diffusion capture as capped118b. The matched dg1 sample's lowest xpu:3
reading is 10,424,627,200 bytes, 760,950,784 above its 9 GiB floor. Do not assume
unchanged peak allocator behavior when alternating graph and eager paths.
Require unchanged floors, at least 0.5 GiB pre-floor margin and no latch; report
physical free plus allocated/reserved/peak at the same sites. CPU cache overhead
is under 2 MiB of additional frame bytes; scheduling tables retain at most16 entries.

Admission gates: recursive packet closure; unchanged parent numerical source
bytes; all three eager/graph/repeat chains exact; native/optimized conditioning
exact; pre-diffusion capture and expected signature identity; full uncached
reference; cone/display equality each chunk; qualification read-ahead hits;
full qualification snapshot scopes and matching launch options. Then use the
new CPU file audit on completed **interior** stream receipts to check scheduling,
hits, barrier scopes, bounds and optional exact control output comparisons.
That audit is necessary because qualification bypasses the changed live wait
and reduced barriers. A GPU fault or byte/floor failure retains inherited halt
and latch behavior. No automatic fallback, restart or retry is introduced.

Open: full-model XPU exactness, sustained cadence, real read-ahead hit rate,
allocator peak/margin, sampler-B queue tail, and any owner decision to select
reduced barriers. Public promotion and seam judgement are outside this packet.

## Build and handoff

[Build receipt](../data/resume-20261008/continuation119-build.json) records final
manifest, source inventory, recursive verification, exact CPU counts and logs.
[Contract](../recovery/20261010-continuation119-stream/CONTRACT.md) and
[launch reference](../recovery/20261010-continuation119-stream/LAUNCH.md) bind the
new packet/client options. The launchers call `bin/python -B`, never `bin/python3`.

Final seal: `d4b99d333f8193fc74041290b3cc3ebc7309b73836323997d14271a9aa246890`. Inventory:1,930 files; total regular payload123,527,904 bytes; zero `__pycache__`/`.pyc`. Recursive verification passed. CPU:375/375 recovery (no skips),278/278 client (193 historical +70 focused119 +15 fake integration),10/10 preflight. The16 builder tests are included in375, not extra. All2,378 fixed request graphs match118b after namespace/clip normalization; all132 numerical contracts and ids match. No launcher or `--check-only` was executed.
