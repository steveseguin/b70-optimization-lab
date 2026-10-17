# Packet58e: make the one-card chain cheaper to run

October 17, 2026; four-card host; CPU preparation only.
[Packet](../experiments/own-xpu-runtime/stage2/packet58e-onecard/README.md) and
[coordinator commands](../experiments/own-xpu-runtime/stage2/packet58e-onecard/WINDOW.md).

The new packet is copied from frozen 58d. All **165 native source/constant
files** match the parent, including its post-load lifetime repair. Arithmetic
`iq3-p49-split32-v1`, full BF16 KV, oracle and exactness gates are unchanged.
Both host and device builds were compiled serially on CPU; no device executable ran.

All six chain gaps are **90 seconds**. The inherited work allowances plus
gaps total **93 minutes**, down by **14 minutes 20 seconds** from 58d.
This is schedule arithmetic, not measured runtime. Drains, teardown,
fault checks and watchdogs are unchanged; lease waits can add time.

Exact model windows initially require **85.57 GB available**, instead of
118.31 GB. The plan charges the complete 48.63 GB pinned expert census,
all 26.41 GB of device allocations as possible host backing, the observed
0.579 GB shadow, loader/host workspace/cache metadata, and the unchanged
8 GiB reserve. The full 18 GB cache, BF16 KV, weights and workspace are included.
Clean, sparse, unpinned file-backed pages are no longer required to remain
resident for exactness. They can reclaim normally; no memory or cache setting
changes. This overlap policy does not qualify their speed.

The 58c measurement remains explicitly incomplete. It has no successful
after_load snapshot. The new code never uses its peak alone as the full shadow
bound: all census device backing stays independently reserved. After each
successful model window, the actual native after_load sample and full live
allocation census are required. The successor's bound includes the larger of
that observation, the full supervisor peak and the seed. No fabricated
full-load measurement is present. Host-global GPUActive can move with lane B,
so the full backing charge remains even after observation.

K1a and K1b retain their 12 GiB bounded-fixture admission. K1a, K1b, KD,
W2m, WS and WS128x hold lane A; compatible lane-B screens may use cards 2+3.
WS128 publishes hold-lane-B before waiting for B to drain and retains the
118.31 GB whole-host admission. Each window rechecks memory after its leases.
The live supervisor retains the 8 GiB stop floor, original anonymous/shadow
guards and cooperative SIGTERM. Failure retains coordination markers.
Shared teardown uses packet70's protocol and its existing 60-second spacing.

All **70 Python checks pass**, including the 11 admission/protocol tests.
The full-shape native CPU mock executes the real post-load setup with 144
expert banks, 48 route sources, all three allocations and two old-lifetime
rejections, using 2,457,406 backing bytes. Fresh/persistent request resets
match tokens and 40 retained fixtures. K1 passes 24 checks and preserves hash
`8ba3faa72a04985c65ea1b27d9cba2379a0fa91e00ac912334c4d86ab399c303`.
The admission dry run covers every window, one-byte-below admission refusal,
reserve crossing through the real cooperative supervisor, live B overlap,
hold-before-wait timing exclusion, wrong-card refusal and retained stale markers.

The seal binds the admission gate and source closure. Actual `--plan` is
checked against the saved seven-command plan, for card 0 and fresh
`evidence/card0-58e-a`; planning creates no queue directory. The coordinator
starts at K1a with its real reviewed fault boundary. The saved 2026-01-01 date
is only a command-generation fixture. Prior lineage latches stay untouched.
Device fit, post-load memory, correctness and speed are still pending.

WS128x is now exactness-only. Its rates are explicitly diagnostic, and the
submission helper refuses a payload without a separate whole-host timing
repeat. There is no new speed result or external submission.

[CPU closeout](../experiments/own-xpu-runtime/stage2/packet58e-onecard/CPU-PREPARATION-CLOSEOUT.md),
[admission evidence](../experiments/own-xpu-runtime/stage2/packet58e-onecard/evidence/admission-cpu.json),
[full-shape allocation gate](../experiments/own-xpu-runtime/stage2/packet58e-onecard/evidence/postload-allocation-cpu.json),
[queue plan](../experiments/own-xpu-runtime/stage2/packet58e-onecard/evidence/queue-plan.txt).

The requested first `git pull --rebase` was blocked by an unrelated modified
frozen orchestration log. Fetch showed local main equal to origin/main; no
stash, branch or worktree was created. All 267 tracked 58d files still match
the pre-copy hashes. Existing packet/screen/ops files and latches were not
edited by this task. Concurrent unrelated logs remain outside the commit.

No GPU, service, sudo, power, memory, swap, page-cache or reboot action ran.
CPU commands used nice 19, CPUs 8-15/24-31, python3 -B and /dev/null input;
compilation was serial. The bounded 500 MiB preparation uses the inherited
packet-specific 8 GB storage floor. The general 50 GiB floor is not met or
claimed. No evidence was deleted to make space.

Large-file retention: the copied 4 MiB rope.bf16 is required by source-relative
loading; its hash and restoration source are recorded in the packet.
Build scratch stays ignored. The retained local generated fixture dependency
still makes this an originating-host experiment, not a public recipe claim.
