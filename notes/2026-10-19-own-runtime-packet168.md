# Packet168 — incomplete CPU preparation for the two-card body census

The requested measured census is **not ready**. No GPU ran, no model was loaded,
and no measured class ranking or new price was produced. The record remains
packet136 bundle8,58.798108759182306 tok/s.

The private packet builds and retains the unchanged bundle8 selection and
arithmetic objects. Its optional diagnostic command snapshots state, skips a
class, restores it, checks an unchanged repair and restores again. The native
CPU fixture exercises both ranks with actual snapshot byte copies and deliberately
corrupted bytes. It completes264 partial observations and2,376 real sensor
samples, below824MB peak RSS. Ordinary compute is marked, not evaluated, so this
is lifecycle evidence only. The full requested arm sequence has not passed.

The obstacle is incomplete implementation: the prototype's isolated half loop
does not preserve the concurrent native timing boundary. Transfer is unimplemented;
the head mask covers only the local part; existing fusions cross the requested
router/shared-expert/glue labels. The new analyzer refuses those incomplete
inputs. These are not measured negative optimization results and do not close
the census. The remaining work is a coupled native skip/repair path with complete
class ownership, both head partitions and transfer, followed by the full CPU
sequence and opening K1a/K1b qualification.

The analyzer reproduces all five real parent runs: packet136's58.798109,
packet163's58.609736/58.625233 and packet165's58.631653/58.556502. All60 real
prompt streams pass the same control validator used by the census, with real
reset receipts and the unchanged128-token oracle prefix. Corrupted copies are
refused. No missing class costs are inferred from those records.

Six analyzer tests and the seven-case private report adapter pass. Built native
flags and passive device-path imports pass under both real launch environments.
Both fresh temporary queue plans pass. Shared `rehearse_entry.py --report`
failures are retained; the private adapter tests the census report layout only,
not the missing native orchestration. Both new proposal rows are explicitly
blocked and were never queued. The final READY marker is false.

CPU commands used nice19, cores8–15/24–31, `python3 -B`, closed stdin and the
shared compile turn. No service, sudo, power, memory setting or frozen packet,
screen or ops implementation changed. The pre-existing dirty `CURRENT.md` was
left untouched; no host/card state changed. Only new packet168 proposals were
added under ops.

The first entry compile caught a string/`const char*` mismatch. A subsequent
CPU fixture compile caught a missing `.data()`; running its old binary exposed
the marker backend's missing compute method. All failures are retained. The
fixed CPU builder now records pending state before compilation and binds the
current fixture and binary before a run, preventing stale-binary qualification.

[Packet and reproduction commands](../experiments/own-xpu-runtime/stage2/packet168-twocard-body-census/README.md),
[actual gate receipts](../experiments/own-xpu-runtime/stage2/packet168-twocard-body-census/evidence/),
[remaining qualification](../experiments/own-xpu-runtime/stage2/packet168-twocard-body-census/qualification.json).

## Packet168b: partial census taken to READY (Claude, after the Codex usage limit)

Codex stopped mid-way through p168b when it hit its API usage limit. Its
six-class contract was kept: router and shared expert stay one fused class,
the transfer and split head go to the residual, and the per-prompt drift
gate was added. The remaining gaps were closed on CPU.

**The design follows the coordinator's decision.** One load on lane B runs
these views, each over all 12 prompts: C0, attention, gdn, routed_experts, C1,
router_shared_expert, dense_hc, norms_glue, C2. Every request starts with a
complete native reset and decodes 64 tokens. Those tokens must equal the oracle
prefix in-run. In a class view, native command 20 runs on both ranks after the
prompt's exact setup request. Each call does three repeats of: snapshot,
control pass, restore, arm pass with one class skipped, restore, repair pass,
restore. The repair must be byte-exact, and each restore must equal the
pre-probe image. A class marginal is the median over prompts of
(rank0 + rank1) median(control − arm), in ms per isolated body pass. The
**residual** is the exact native control ms/token minus the sum of the six
marginals. It holds the cross-card transfer, the split head, controller time
and overlap. It is not causally isolated, and negative values are kept. Arms
are never reported as speed.

**Two device failures were found and fixed before any GPU contact:**

1. Codex's p168b probe refused any arm whose expert routes changed. Every skip
   upstream of a router changes router inputs, so the run would have stopped
   at the first arm. The marker-only CPU fixture could not see this. The probe
   now records `route_identity_preserved`; the expert count and shapes stay
   fixed.
2. `--census-probe` gives rank 1 a snapshot image. The parent memory plan has
   1.2 MB slack on rank 1, so the memory gate would have refused the start.
   The CPU fixture's production-arena census measures the image. Its rank-0
   image equals the real device rank-0 image in packet165
   `device-warm512-B-a` (344,064,536 bytes). Rank 1 adds **373,887,468
   bytes**, recorded in a private `memory-plan-census.json`. The planned
   rank-1 total is 31.80 GB, with 2.44 GB free and 411 MB of 30 GiB arena
   headroom; the parent margin rules still apply.

A third failure was packaging. The device screen imports `fault_review.py`,
which needs `lineage/window_driver.py`. The file is now copied from packet165
with an identical digest.

For the QUIET protocol (chain 58as-a), the first full lifecycle rerun was
stopped while rank 1 was running. All heavy steps were rerun after the QUIET
flag cleared at 05:58.

**Gates (evidence/final-audit.json): all pass, READY true.**

* Native CPU fixture, both ranks: the registered order × 12 prompts × 3
  repeats gives 324 probe rows and 2,268 real host sensor samples per rank.
  Snapshot copies are real; compute is marker-only. Peak RSS is ≤ 822 MB.
* Worker gate: the real `census_worker.py`, `suite.reset`, NativeController
  and analyzer run over a host transport that replays the real fixture probe
  rows. This covers 109 native requests, 144 probe commands (the exact
  registered sequence) and 220 rank resets. The report passes, and a wrong
  token or a failed repair is refused.
* Analyzer: 10 unit tests pass. The 60 real parent streams pass;
  packet136 replays at 58.798109.
* Private report adapter: 11 cases through the real entry and report route.
* Built `--help` covers every worker rank flag. Device-path imports, the oracle
  binding and the census memory plan load under the real A/B launch
  environments.
* `lanequeue plan` passes on temporary copies of
  `proposed-p168-body-census-{B,A}-v2.txt`, both before and after READY.
* The shared `rehearse_entry.py --report` refuses: its generic screen report
  probe cannot produce `run/census-input.json`, and it WARNs that no
  preparation probe is declared. The receipts are retained and listed in READY
  `shared_tool_limitations`.
* Waits: native 600 s and controller 1,200 s, against a 60 s cold floor.
  Device floor 25 GB. Planned writes are 1.84 GB, which is 2 × the projected
  110 resets plus one raw snapshot. Expected run time is 900–2,400 s, with a
  7,200 s watchdog.
* There is no optional smoke. The single load opens with the excluded
  warm-up and the exact C0 on all 12 prompts.

The jobs are `packet168-body-census-B-v2` (lane B, cards 2 and 3) and the
lane-A twin. They are not queued.

## v3 fix loop after the B-v2 device failure (2026-10-19, CPU only)

`packet168-body-census-B-v2` (commit 30ba2c94a) ran on lane B from 10:22 to
10:27 UTC and exited with rc 1. Rank 0 failed with "packet168 arm raised sticky
error" and rank 1 was stopped cooperatively. The GPU fault count stayed at 2,
and teardown completed.

**Root cause.** The attention skip did not cause this failure. The probe
passed on the first five prompts. It failed on the sixth prompt,
benchmark-analysis (65 tokens), in the **control** pass of repeat 0: only the
`before-control-snapshot` sensor was recorded. The setup request's last half
step was at position 127, with launch extent 128. `commit` left the device
position at 128.

`native_probe.hpp` ran the body pass without calling `admit_position`. So
`qsa_select`/`qsa_attention` were still prepared with extent
`((127+32)/32)*32 = 128`. These are set in `main.cpp:1285` (`s.extent`) and
`main.cpp:1465-1469` (`admit_position`). The device guard
`pos > position_limit(s) - s.tokens` then fired. It is defined in
`kernels.hpp:25`, where `position_limit` is `launch_extent` for select and
attention, and it fires in `round2.hpp:11`, `specialised.hpp:94` and
`kernels.hpp:122`. All three write the sticky error in slot 15.

Of the 12 probe positions (prompt tokens + 63), only 128 is a multiple of 32.
Every view would have failed at that prompt, including any view without the
attention arm.

**Changes.**

* `probe()` now reads the device position, calls `admit_position(P)` before the
  image and signature (as a non-speculative half step does), and mirrors the
  guard on the host.
* As instructed, the attention arm is dropped. `qsa_*` runs in every pass and
  is part of the residual (packet173 finds no attention lever).
* The final arm set is gdn(2), routed_experts(4), router_shared_expert(3),
  dense_hc(6) and norms_glue(7). The order is
  C0, gdn, routed_experts, C1, router_shared_expert, dense_hc, norms_glue, C2.
* Native arm 1 is now refused, like 5, 8 and 9.
* None of the remaining arms skips a `qsa_*`, `begin`, `commit` or
  `check_status` launch. So none can change the position or extent. Their other
  sticky sources (route42 non-finite input, route and status validity, p39
  capacity) only see restored state from the exact setup request.

**CPU proof.**

* `test_analyze.StickyGuard` models the exact guard over the real v2 launch
  plans of both ranks, copied to `lineage/v2-root-cause/`:
  * The old arm set without admission fails. Its first trip is
    (rank 0, attention, benchmark-analysis, control), which matches the device.
  * The new arm set without admission **still fails**.
  * The v3 arm set with admission passes every view, prompt and pass.
* The native CPU fixture now probes at the real positions. It first admits
  P-1, and it reproduces the uncovered extent once per view on each rank (8).
  `probe()` admits the position, and 288 rows per rank pass. Marker compute
  with real snapshot copies; peak RSS 823 MB.
* The analyzer has 16 tests, including one that refuses a v2-shaped
  (attention) stream. The 60 real parent streams pass, and packet136 replays at
  58.798109.
* The worker gate covers 96 observations and 120 probe commands. A wrong token
  and a bad repair are both refused.
* The report adapter passes 11 cases. Flags were checked against the rebuilt
  binary's `--help`.
* `lanequeue plan` passes on temporary copies for B and A. The shared rehearse
  refuses for the same reasons as in v2 (accepted limitation).

**Proposals.** `ops/lane-queue/proposed-p168-body-census-B-v3.txt` (job
`packet168-body-census-B-v3`) and the lane-A twin `-A-v3`. Not queued. The v2
proposal and lineage files are unchanged. `READY-FOR-DEVICE.json` is written
last by `finalize.py`, in a separate commit.
