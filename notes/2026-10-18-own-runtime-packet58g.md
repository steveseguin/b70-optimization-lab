# Packet58g: one-card p28 refusal repaired on CPU

October 18, 2026, four-card host. New packet copied from frozen 58f.
[Packet](../experiments/own-xpu-runtime/stage2/packet58g-onecard/README.md),
[one-line coordinator launch](../experiments/own-xpu-runtime/stage2/packet58g-onecard/WINDOW.md),
[closeout](../experiments/own-xpu-runtime/stage2/packet58g-onecard/CPU-PREPARATION-CLOSEOUT.md).

The refusal is at `blk.2.expsgate`. p28 receives
`card0:expert-table:blk.2.ffn_gate_exps.weight`: 8,192 bytes for 512 pointers.
It expects 512 × 640 × 1,100 = 360,448,000 bytes of packed IQ3_S weights.
The real allocation is on the device and the CPU reproduction is aligned.
Layer 2 deliberately keeps separate status checks, so it missed the indirect
handling already present in the fused IQ2_S and down paths. The up table would
fail next. This is proven by the actual one-card arena and submit path, not
inferred from a miniature fixture.

The new p28 argument declares pointer indirection. Both CPU and SYCL resolve
the selected expert row before running the unchanged math. The oracle remains
`iq3-p49-split32-v1`; weights, selection, dispatch, arithmetic bodies, BF16 KV,
cache size, host admission, reserve and device mask are unchanged.
[Exact cause and parent pins](../experiments/own-xpu-runtime/stage2/packet58g-onecard/evidence/fullshape-root-cause.json),
[source delta](../experiments/own-xpu-runtime/stage2/packet58g-onecard/evidence/58g-delta.patch).

The full-size CPU test runs actual initialization, cache publication,
prepare_plan and prepare_commands with a mock backend. Distinct mmap ranges
reserve production extents without populating weights. All 3,446 allocation
rows match the production plan; 24,287,732,980 device bytes exactly match the
failed device log. The old direct call fails on the exact table. The repaired
call validates all 1,486 sites and captures 1,633 host operations at both 32
and 4,096 context extents. The p28, p30, p49c, p49d and inherited p54
route/recurrence checks run, as do the other selected submitters. Generic
adapter/performance validation uses verbatim native-source CPU mirrors.
Peak RSS is 29,356,032 bytes; fixture scratch is removed.

K1 now tests the actual p28 IQ3 path against the unchanged direct p39 oracle
for device, host, mixed and streamed placements. All 24 checks pass and retain
the parent's exact output hash
`8ba3faa72a04985c65ea1b27d9cba2379a0fa91e00ac912334c4d86ab399c303`.
Fresh and persistent miniature requests match tokens and all 40 retained
fixture files. The full-size validation executable is separate from the
miniature reset executable: miniature shapes are outside the native ABI.
Both compiler builds pass, and the build uses 158,884,963 bytes, below 1 GB.

A failed startup now carries explicit `compute_started=false` proof. After
native drain, no remaining owned process or conflicting Xe client, and clean
supervisor kernel postflight, 58g releases its own shared drain record and
lane lease. It remains a failed window and the queue stops without retry.
Live owners, unknown receipts and faults retain coordination. The release is
implemented in the new runner, with no edit to shared screen/v3 code or prior
markers. Full-window tests exercise clean refusal, faults and surviving owners;
fast exits with no sampled owner also have a tested release path.

All W windows now inherit nice 0 and lane-A cores `0-3,16-19`, like the two-card
chain. K1, KD and every preparation command remain nice 19 on `8-15,24-31`.
The queue must start in a nice-0 coordinator unit; children never try to raise
priority. Native W receipts must prove both the declared and observed placement.
All 98 Python checks pass, including a temporary seven-stage runner dry run and
KD refusal with no retry. Admission/mask checks, cache checks, seals and the
actual fresh-output `--plan` pass. The plan creates no queue directory.

The coordinator starts fresh at `evidence/card0-58g-a/K1a`; old K1 receipts
cannot cross the new seal. The command is in WINDOW.md and accepts the
coordinator's reviewed fault boundary and library path. Existing latches and
unresolved shared markers remain untouched. Actual device access, complete
model exactness and speed remain pending. No GPU, service, sudo, power,
host-memory, swap, page-cache, reboot or external publishing action ran here.

The first `git pull --rebase` refused unrelated live changes. Fetch confirmed
local main equaled origin/main; no stash, branch or worktree was created.
Focused commits preserve concurrent packet/ops work. The threshold ledger was
refreshed after checking that the new record was still two-card, with no
matching one-card IQ3 submission. Historical failed receipts are copied under
58g/evidence/58f-failure; frozen parent hashes still match.
