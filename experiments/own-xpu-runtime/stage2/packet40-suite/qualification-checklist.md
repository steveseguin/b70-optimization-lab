# Packet 40 qualification checklist

This is a work inventory, not a passing gate. It maps all 91 gate receipts in the sealed packet 38 CPU inventory to their current executable producer or an explicit manual review/re-authentication step. No copied `passed` boolean qualifies packet 40. Exact commands, source-binding differences and required aggregation steps are in `qualification-checklist.json`.

Every command uses nice 19, idle I/O and Python `-B`; paths point only to packet 40. Start serially. Model pair gates and compiler jobs still share the task-wide process/memory limits. Check disk admission before large writes and delete each scratch directory after its receipt is retained.

## Required families

| Family | Current action |
| --- | --- |
| Owner, lifetime, prepared launches, argument safety | `cpu_campaign.py cheap`, plus focused sources listed in JSON |
| GNU/Intel/ASan mini and draft fault gates | `cpu_campaign.py mini` |
| Native controller and mailbox ASan/UBSan/TSan | Rebuild standalone binaries; rerun 1,123-case controller and five-case mailbox gates with final binary hashes |
| Full actual mini controller comparison | `native_mini_gate.py` without `--quick`; terminal abandoned speculation scratch must be separately labeled, never concealed |
| Real target identity and forced speculation | GNU/Intel real campaigns and native real comparison, with current dispatch |
| Draft KD reference | Regenerate captured draft outputs with current binary/selected dispatch, retaining immutable target input-stream provenance |
| p30/p38 kernels | `p38_kernel_gate.py`, K2 unit modules, both capacity256 CPU compiler outputs |
| Persistent suite/reset/warm-up | Rerun suite gates, current manifest/checker and exact cap/retention policy |
| Every wrapper and failure path | Packet40 rehearsal must call complete K0…W2mc wrappers including summaries and ordinary failure paths |
| Retention, cancellation, asynchronous draft | New full-state gates and independent source reviews |
| Final sealing | Refresh every hash dependency; precision flags on compile and link; reject stale receipts |

## Copied independent reviews cannot be reissued by renaming

`review-resume-controller.json`, `review-resume-reset.json`, `review-resume-authority.json` and `review-draft-capture.json` are packet 38 review records. Packet 40 changed their subject. The fresh cancellation/retention and nonblocking-draft reviews are current scope pointers; a seal must establish that they cover each required question and bind the final sources. `review-resume-storage-gates.json` and `review-resume-window-storage-gates.json` are executable regression outputs and must be rerun.

The inherited `resume-input-integrity.json`, capacity256 aggregate, p38 K2 aggregate and standalone mailbox receipts have no single dedicated inherited producer script. Their constituent commands/checkers can be run, but aggregates must be written only from freshly verified outputs. The JSON calls out each such case.

The inherited `CPU-RESULTS.md`, `cpu-tests.json`, `build-receipt.json` and old binary hashes are historical until packet 40 replaces them with an honest current seal. A partial run, `--quick`, a source review or an oracle-schema check cannot stand in for the inherited full runtime gate.

## New scope

The additional packet40 gates cover 64/128 caps, every emitted oracle token, sparse fixture ranges, final-state retention independence, cancellation at every mini kernel and sampled real kernels, nonblocking native draft publication, selected-dispatch KD references, the two timing formulas, prompt-class aggregation, and complete wrapper success/failure paths. Device runs, actual overlap, measured speed and same-boot exactness/speed companion chains remain coordinator work.
