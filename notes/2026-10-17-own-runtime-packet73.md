# Packet 73 — HC gates and second expert round

CPU preparation started at 20:29 UTC, with a 22:59 UTC sealed-candidate deadline.
No GPU, model, service or host-setting change is authorized in this task.
The coordinator owns packet70 and every future device screen.

`git pull --rebase` initially refused the live packet70 orchestration log's
uncommitted change. Fetch found no incoming main commits; that file stays
untouched. Root had 28 GB free. The owner's explicit sub-1-GB build budget
is used for this preparation. Every compiler is serial within this task,
nice 19, affinity 8–15,24–31, with an 8 GiB address-space ceiling and no stdin.

[Packet](../experiments/own-xpu-runtime/stage2/packet73-hc-experts2/README.md).
Its C++ sources are copied from packet70, with parent hashes retained.
Production means packet70's wide64 experts, draft-HC, batch rollback and 24/24
placement. It does not mean packet65's old production expert path.

The HC candidate shares packed Q8 code and scale loads across four adjacent
logical chains. Each subgroup owns four adjacent rows of ONE stream; the
four streams stay in separate subgroups and retain the packet60 mix epilogue.
This is not packet67's four-stream subgroup geometry. Exceptional activation
values use the original SG32 arithmetic. No decoded buffer is added.

Expert candidate A loads two IQ2 packed blocks before consuming them.
Candidate B shares a 64-byte IQ4 code span and four half scales across sixteen
chains. Both start from wide64, preserve its geometry, original logical sums,
reduction tree, types and rounding. Offline load/GRF/spill evidence determines
which variants can proceed. Any spilling variant is rejected before sealing.

Route fusion is deferred: preserving its globally normalized selection and
ties would require a separate synchronization design, beyond this short task.
The next performance measurement is in-engine v4-lanes, never a microbenchmark
speed claim. CPU byte identity and seals do not establish device quality or speed.
