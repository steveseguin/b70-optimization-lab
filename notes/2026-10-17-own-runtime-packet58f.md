# Packet58f: keep the one-card owner on card 0

October 17, 2026; four-card host; CPU preparation only.
[Packet](../experiments/own-xpu-runtime/stage2/packet58f-onecard/README.md),
[coordinator commands](../experiments/own-xpu-runtime/stage2/packet58f-onecard/WINDOW.md),
[CPU closeout](../experiments/own-xpu-runtime/stage2/packet58f-onecard/CPU-PREPARATION-CLOSEOUT.md).

58e passed only `ONEAPI_DEVICE_SELECTOR=level_zero:0` to the native child,
just as 58c did. The lane-A pair mask existed in imported code but was never
applied. Lane integration added the strict owner-FD sensor; it exposed extra
or unidentified Xe opens that the older wrapper did not check. The failed
record did not save the offending BDF. Driver enumeration is consistent with
the failure and the screen-v3 investigation, not a traced call from this run.
The failed child cooperatively stopped and its log records completed cleanup;
that does not make its K1 result pass.

58f is a new copy. It passes the exact BDF filter `0000:23:00.0`, affinity `0`
and selector `level_zero:0` before discovery. A fresh private HOME and a check
for a driver debug file prevent mask overrides. The actual model worker also
checks the complete mask. Passive topology maps exactly one render node,
`/dev/dri/renderD130`. The sensor still rejects every other owned Xe FD and
now records the offending rows. CPU checks prove the child environment and
mapping; actual native FD isolation awaits K1. This is not an OS device sandbox.

The shared teardown record is now acquired after CPU admission completes.
A preflight refusal releases its own lease without changing a prior drain
record. Successful K1 owner exit and clean postflight release the drain before
CPU report validation, following the shared screen v4 drain design. A failed
report stays failed. Live owners, postflight faults and uncertain native exits
retain their records. Lane A remains leased during device work; lane-B
compatibility and the 60-second shared drain spacing are unchanged.

All 165 native source/constant files match 58e. Arithmetic, BF16 KV, the memory
fence, 18 GB cache, 8 GiB reserve, 90-second chain gaps and full memory budgets
are unchanged. Exact model admission remains **85,565,068,816 bytes**;
one byte below refuses. K1 stays at 12 GiB; WS128 stays at 118,308,908,048 bytes.

All **81 Python checks** pass, including **22 admission/mask checks**. Actual
window-entry CPU mocks cover preflight refusal, clean exit plus report failure,
postflight failure and success. Full-shape native CPU setup passes 144 expert
banks, 48 routes, all three post-load allocations and both lifetime regressions
using 2,457,406 backing bytes. Fresh/persistent requests match tokens and 40
retained fixtures. K1 passes 24 checks with its prior exact hash. Both compiler
builds are serial CPU work; no device binary is executed.

The final seal binds the new mask and failure tests. The actual `--plan` passes and
matches the saved seven-command plan and creates no queue directory. Start fresh
at **`evidence/card0-58f-a`**, beginning with K1a. The coordinator supplies its
actual reviewed fault boundary; the saved January date is only a CPU planning
fixture. All existing latches, packets, screen wrappers and ops files remain
untouched by this task. Device memory, exactness and speed are still pending.

The first `git pull --rebase` refused unrelated staged and unstaged work.
Fetch showed local main equal to origin/main at that point. No stash, branch
or worktree was created. Focused commits preserve concurrent work.

No GPU, service, sudo, power, memory, swap, page-cache or reboot action ran.
CPU commands used nice 19, CPUs 8-15/24-31, Python -B and null stdin. The bounded
500 MiB preparation passed the inherited packet-specific 8 GB storage floor;
the general 50 GiB floor is not claimed. The copied 4 MiB rope is required by
the native loader; its restore source and hash are in the retention note.
