# Packet58ap: record chain prepared behind the v5 gate

Packet58ap is a separate copy of the seven-window packet58aj chain, with
packet58am's repaired demand-transfer binary and source bytes preserved by
hash. It targets the one-card resident-lookup record of 31.966820 tok/s
(`cmveqsmsl00ebrf014yvrsosx`). No GPU, service, live queue, existing packet,
host setting or secret was touched.

The coordinator must rerun readiness at launch. It reads the v5 output from
`ops/lane-queue/proposed-p58am-v5-A.txt`, verifies the binary and saved raw
requests, and recomputes the comparison. Both candidate views must beat
every warm control by at least 0.5%, all sixty requests must be exact, and
warm-control drift must be no more than 3%. The first view is warm-up for
speed only. Missing or failed evidence keeps device readiness false.

The new unit is `packet58-onecard-58ap-a`; the new output is
`stage2/packet58ap-onecard-chain/evidence/card0-58ap-a`. The order remains
K1a → K1b → KD → W2m → WS → WS128x → WS128, with 90-second gaps, whole-host
admission, full BF16 KV, 300-second operation waits and graceful stops.
The fault review path is `evidence/fault-review-58ap-a.json`.

All seven native argument sequences ran on CPU under the actual closed
library environment. Every flag was checked against executable help.
The native preparation path and request resets ran, and the real stream and
memory sensors read synthetic inputs, including refusal cases. Syscall traces
show no model or device opens. The inherited single-view probe internally
selects demand off, so a separate, explicitly labeled five-view CPU probe
also exercises both demand views and both parity banks. That is test evidence,
not a device result or a substituted benchmark.

The model runtime was not compiled. A tiny K1 command adapter was necessary
because the unchanged fixture lacked help and a CPU preparation switch. It
forwards device arguments to the original core, or CPU rehearsal arguments
to the original GNU fixture. Both cores retain their original hashes.

The shared entry/report rehearsal, 138 Python checks, final-location offline
submission rehearsal, native archive verification, seven-window argument
checks and CPU sequence pass. The complete first native sequence peaked at
926,150,656 resident bytes; the final source-bound receipt records its own
peak, below 4 GB. Work used nice19, helper cores 8–15/24–31, Python `-B`
and null stdin. The shared preparation adapter keeps its explicit unranked-ABI
warning; actual native preparation was exercised separately.

The submission helper refuses an inexact chain or final WS128 at/below the
31.966820 floor, pinned predecessor or current local ledger. Notes retain
the actual v5 bracket numbers, census-gate supersession, 128-token scope and
strict512 false. The full 512-token gate and a second independent timed run
remain pending. No submission was made.

The packet vendors the repaired candidate executable
`57741828a9f50f62f2ce3b287d1c8a601992e42aa276d5e36370f44c742c0e0b`
and 116 build-source files. A verified 19,508,235-byte native archive is
deliberately retained for restoration without a changing parent or rebuild;
its retention reason and restore command are in the packet README. Original
binaries and parent evidence remain intact. Local CPU scratch is ignored;
compact source-bound receipts are tracked. CURRENT.md's pre-existing edits
and the machine's live state remain untouched.

The final READY marker is written last. The coordinator owns the next action:
recompute the v5 gate and, only on success, run the fresh chain that same day.

Evidence: [packet](../experiments/own-xpu-runtime/stage2/packet58ap-onecard-chain/README.md),
[window](../experiments/own-xpu-runtime/stage2/packet58ap-onecard-chain/WINDOW.md),
[CPU sequence](../experiments/own-xpu-runtime/stage2/packet58ap-onecard-chain/evidence/cpu-sequence.json),
[entry report](../experiments/own-xpu-runtime/ops/packet58ap-orchestration/entry-report.json),
[submission rehearsal](../experiments/own-xpu-runtime/stage2/packet58ap-onecard-chain/evidence/submission-rehearsal.json).
