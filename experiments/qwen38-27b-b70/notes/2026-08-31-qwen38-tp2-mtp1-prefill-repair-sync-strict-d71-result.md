# Qwen3.8 TP2/MTP1 strict D71 M=512 down-projection device loss

Date: 2026-08-31

D71 ran after a clean reboot and independent deterministic compute gates on
both B70s. It passed direct model verification, exact startup accounting, and
API readiness. The first strict request then lost rank 1's device inside the
real-request projection hook. With hook synchronization enabled, the traceback
is precise: the M=512 padded dense `down_proj` was submitted at
`sitecustomize.py:62`, and the immediately following `_sync()` at line 63
surfaced `UR_RESULT_ERROR_DEVICE_LOST`.

The later `OUT_OF_RESOURCES` input-preparation errors are consequences of the
same lost device. Xe recorded 605 unsuccessful fault responses, 23 CAT errors,
and one reset. Exactly 1,040 decoder begin/pass receipts remained in the log,
so serving did not execute the profile barriers. The first stream had HTTP 200
but never completed; no benchmark row, output comparison, or performance result
exists. Attempt exit 130 again reflects bounded teardown after conclusive loss.

D58 already rejects the hook's M=128 alternative because it changed the
validated response tokens. D72 therefore makes no numerical substitution: it
disables projection repair entirely while retaining the proven profile-only
startup fix and runs the complete strict suite against the frozen MTP0 oracle.
This determines whether TP2/MTP1 serving is otherwise stable and whether the
current deterministic kernel build happens to preserve outputs without the
hook. A stable but mismatched run is still rejected.

Raw evidence:
`/mnt/fast-ai/bench-results/qwen38-tp2-mtp1-prefill-repair-sync-strict-20260831-d71/`.
