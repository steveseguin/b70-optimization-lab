# FP8/native-MTP transfer work: implemented, GPU validation halted

No new speed improvement is qualified. The metadata candidate and exact
communication prototype were implemented, but the communication test failed
its exact-output gate and the same attempt produced GPU memory faults. GPU
work stopped. The new runtime, metadata endpoint tests and speed comparisons
remain unrun; this is a failed research attempt, not a promoted recipe.

## What was achieved

| Work | Evidence and outcome |
| --- | --- |
| Metadata subtraction relocation | Actual original/candidate builders matched all 36 offline cases on each of the original and refreshed source versions, including 24 metadata fields, aliases and retained-buffer reuse. Native and full-model gates remain pending. |
| Exact two-GPU communication | Implemented uncompressed FP16 IPC/copy/sum with bounded host synchronization. Both ranks captured 12 matching one-row finite/edge cases, then a two-NaN payload mismatch. Overall qualification failed; no timing was run. |
| Runtime preparation | Built a separate newest-base V1/native-MTP control with the accepted overlay preserved. It was never loaded or qualified. |
| Full model validation tooling | Implemented and independently reviewed a persistent-endpoint control/candidate campaign, with frozen-oracle/source identity checks, both-rank native gates, complete realistic outputs and 512/2K/16K continuation checks. It was not launched after the fault. |
| Convolution attribution | Reused the original 512-token trace: native convolution sums 3.547/3.571ms on the two ranks, about 2.02/2.03% of each rank's summed kernel time. The native implementation already tiles 256 channels and 8 tokens. This does not justify a broad rewrite in this bounded campaign. |

The exact payload example is informative: the two-NaN pair contained FP16 bits
`fe02` and `7e03`. The candidate returned `fe02`, while XCCL returned `7e03`.
Both ranks agreed within each arm and the recorded inputs remained unchanged.
The test did not discard NaNs, relax bitwise comparison, or replace the oracle.
Only 13 of 14 registered cases at the first 1×5120 shape were attempted; rows 2,
512 and 4096 and every timing block were unrun. The partial matches do not
qualify this communicator for inference.

There are **no newly measured model prefill, HTTP first-token or decode rates**
from this campaign. The earlier [qualified measurements](2026-09-14-amd-transfer-results.md)
keep their original identities and values. Official FP8 target weights, native
MTP and the accepted target arithmetic remain the required contract. DFlash
was excluded throughout this work.

## Attempts and incident

| Stage | Result |
| --- | --- |
| communication-native-01 | Torch rendezvous tried container-hostname resolution without networking. Root stopped the launcher before GPU worker startup; Docker's 30-second stop timeout ended it with 137, without OOM. |
| communication-native-02 | Static localhost rendezvous worked, but XCCL's OFI transport could not initialize in the isolated network. Workers exited before candidate operations. |
| communication-native-03 | Matching the qualified bridge/host-IPC/SYS_PTRACE/device-selector settings fixed startup. XCCL, peer capability, dedicated allocation and SCM_RIGHTS transfer passed. An invalid receiver-side export-map lookup stopped the candidate before peer import/copy. |
| communication-native-04 | Corrected receiver import reached the exact-output tests. The NaN mismatch and GPU copy-engine faults occurred during this attempt. The controller latched the fault and confirmed container exit. |

Pinned Intel source for the actual container driver 26.27.39122.11 confirms that
`zeMemGetFileDescriptorFromIpcHandleExp` looks in the caller's local export map;
it is not a receiver import validator. The corrected path retains exporter
validation, checks the received OS descriptor, preserves handle metadata and
uses the driver import API. Numeric descriptor collisions are handled without
closing an exporter's descriptor. [Source and exact version evidence](../probes/mtp-exact-tp2-20260914/ipc-import-source-review.json).

The final attempt started at 18:30:37 UTC on September 14. At 18:30:41 UTC the kernel
reported unsuccessful memory-fault responses on both B70s, a CAT error and
BCS engine resets initiated by the driver. At 18:30:42 UTC the controller had
preserved the campaign fault latch and confirmed container exit. The separate
NaN assertion and abrupt worker-exit path are recorded. Their causal relation
to the memory fault is **not established**; IPC teardown/lifetime remains an
investigation lead, not a diagnosis.

No later GPU workload, model reload, host reboot, agent driver reset or
power/swap/page-cache change occurred. The original qualified service had been
stopped once at 18:07 UTC for the exclusive experiment. Read-only checks at 18:36 UTC
showed no render-device owners, no running containers and closed ports 18124 and
18129 on the same boot. **The API is offline and GPU compute health has not been
requalified.** The fault-halt rule prevents a model reload under this campaign.
The earlier user-reported [startup freeze](2026-09-14-amd-transfer-results.md)
is a separate preserved incident.

## Evidence and next admission

- [Execution plan and fixed quality contract](2026-09-14-mtp-lossless-transfer-plan.md)
- [Replayed evidence summary](../data/2026-09-14-mtp-lossless-transfer/summary.json)
- [Archive/member hash manifest](../data/2026-09-14-mtp-lossless-transfer/manifest.json)
- [Metadata implementation and complete planned endpoint gates](../probes/mtp-metadata-20260914/README.md)
- [Fault postmortem and quarantined launcher](../probes/mtp-exact-tp2-20260914/native04-postmortem.md)
- [Exact communication source and its limits](../probes/mtp-exact-tp2-20260914/README.md)
- [Convolution attribution](../data/2026-09-14-mtp-lossless-transfer/convolution-attribution.json)
- [CPU-only evidence collector and replay](2026-09-14-mtp-transfer-evidence-collector.md)

Replay all retained raw-output hashes, failed-stage classifications and frozen
reference timing evidence without using a GPU or the raw host directory:

```bash
python3 experiments/qwen38-27b-b70/scripts/collect-mtp-transfer-evidence.py --verify
```

The raw campaign stays at
`/mnt/fast-ai/bench-results/mtp-lossless-transfer-20260914`, including the root
`FAULT.json` and each immutable stage snapshot. Further native work requires
fault review and a separately admitted recovery/health step. Then the prepared
metadata campaign can be considered before any revised communicator. No
unmodified retry, new performance headline or public-default change is admitted.

The metadata relocation adapts Radiance’s observation about unused query-length
work; its supplied patch retains the eager subtraction. The actual branch
relocation is a lab change.
The communication lead is StillDeadcode's uncompressed two-rank design,
integrated by Radiance; this Intel implementation and its validation are lab
follow-up. The lab also documented the collective direction earlier. Neither
contribution receives a validated speed boost from this unsuccessful campaign.
[Original source/provenance review](../../../community/1337hero-r9700-qwen38-radiance/validation/2026-09-14-mtp-fp8-transfer-review.md).

## Publication checks

Archive replay passed for one archive and 310 members, including both ranks'
26 retained output records. The focused CPU suites passed: 28 communication
protocol/controller/retirement tests and 32 server/client/collector tests.
The guide/model/family suites passed 91 tests; four catalog browser tests,
package/claim validation, AMD prefill synchronization, family generation,
repository links and manifest paths passed. Model pages were regenerated with
no content change; the catalog adds evidence dependencies only.

The homepage follow-up link was checked at 390px and 1440px with JavaScript
both enabled and disabled. It remained visible without page overflow. No
benchmark value or recommended runtime identity changed.

A broader historical `test_*mtp*.py` discovery ran 668 tests and reported
5 failures, 66 errors and 3 skips. These included missing old host staging/raw
files, a clean-checkout prerequisite and a formerly missing coverage cell now
recorded as measured. This broad suite did not pass and is not a qualification
claim for the new work. The literal-pin audit reports the existing 231 drifted
Flash-Next pins across two old verifiers (86 matches, no missing targets);
historical hashes were not rewritten. The three whitespace warnings are blank
context lines in the retained inactive unified patch; its hash-bound bytes
were preserved. Other changed files pass the whitespace check.
