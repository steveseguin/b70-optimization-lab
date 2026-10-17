# Packet49: split32 QSA in the SPEED6 two-card engine

This is a separate integration derived from packet45 SPEED6 at `34c62b433`.
It preserves the recorded 23/25 target split, draft rank1, capacity4096,
write-set snapshot rules, 30GiB arena cap, memory reserve, and pinned host cores.
Packet45 and its 39.422tok/s result (`cmv9wjmtj013gle01v8k1yg4v`) are untouched.
The exact SPEED6 non-QSA dispatch is pinned in `dispatch-speed6.json`. K2
retains its fresh measurements and recommendation separately; it verifies the
pinned kernels without selecting unrelated new changes for the model run.

The production QSA attention path uses packet47's split32 reduction.
The independently expressed full-model CPU reference has arithmetic identity
`iq3-p49-split32-v1`; the attention operator identity is
`iq3-p47-qsa-split32-v1`. BF16 KV and weights are unchanged. Output changes
relative to the old reduction are reported separately, never hidden by
replacing the old oracle. There is no packet49 speed claim before device tests.

The bridge supports M=1 and M=2. Both are checked by the integrated owner
fixture in K1a/K1b. SPEED6's full engine continues to submit each attention row
separately during verification; this packet preserves that scheduling. The
standalone M=2 bridge result is not evidence that the engine now batches rows.

No packet48 GEMV is enabled in production. The reconciliation found that its
dense controls used a different wrapper, while the expert timing still needs
a full-layer control. [Packet48b](../packet48b-production/) prepares that
comparison. Its passing device results must select actual winners before a
further integration and seal. Packet46 launch fusion and the ordered packet47
attention alternative remain closed.

- [Coordinator chain and exact commands](WINDOW.md)
- [Serial queue](queue_runner.py), with CPU-only `--plan`
- [Oracle coordinator and checked completion](oracle/oracle_job.py)
- [Independent attention review](REVIEW-QSA.md)
- [Independent queue review](REVIEW-ORCHESTRATION.md)
- [Independent source review](REVIEW-INDEPENDENT.md)
- [CPU preparation closeout and remaining device work](CPU-PREPARATION-CLOSEOUT.md)
- [CPU build and seal commands](CPU-BUILD.md)
- [Task record, status, commits and limitations](../../../../notes/2026-10-17-own-runtime-packet49.md)
- [Storage and artifact retention](ARTIFACT-RETENTION.md)

CPU preparation never executes a binary under `build/device`. Kernel-window
qualification and all full-model device comparisons belong to the coordinator.
The first phase K0/K1a/K1b/K2/W0p is oracle-free once the fresh packet49 CPU/build
seal passes. KD and model windows wait for the new oracle completion binding.
The build seal stays fixed when that separately bound oracle finishes.

The inherited packet45 helper files are implementation dependencies and
historical tooling, not permission to run their old campaigns or resealers.
Use only packet49's new build, seal, oracle and queue entry points. In
particular, old CPU campaigns reference obsolete receipts and must not be used
to claim new qualification. Fresh GNU-host and device build receipts identify
what was actually built. The scoped seal includes GNU host, Intel device and
GNU ASAN/UBSAN builds, fresh owner/fixture checks and miniature snapshot gates.
The full historical compiler/test matrix is not claimed. Final seal:
`c95a6cdf423d4c059afda23a6b9a5a2372f16781d021b7f65749fad1fd7ce5bb`.

The 12-prompt ×128-token comparison has the SPEED6 record's scope. It cannot
pass the separate 512-token final publication gate. One-card engine
qualification and a matched comparison to another runtime remain future work.
