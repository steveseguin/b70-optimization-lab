# Continuing SC117 engine work

Owner direction, October 24: finish making the downloaded model work in our
engine, test correctness, then continuously optimize speed without quality
loss or benchmark shortcuts. Continue until the owner stops the work or a
concrete blocker requires their decision. The previous Unsloth lane remains
closed; this direction applies to the requested SC117 target.

The target authority is the two downloaded shards at revision
`eec4e10a2c29b440a2ae85591fa11569ce752963`, with the full readback hashes in
`model-identity.json`. Do not change target weights, quantization, context
contents, sampling identity, or full 16-bit KV to obtain a faster number.
Keep all target verification for MTP. Draft-only approximations are acceptable
only insofar as the exact target still verifies every emitted token and the
completed target state matches the target-only path.

1. Complete the all-source native build and actual persistent-pair lifecycle
   check. Load the real target once with the draft available, then compare
   target-only and MTP tokens/state after a complete request reset. Preserve
   failures, source changes, physical ownership and safe teardown evidence.
2. Establish a measured baseline with complete model/run identity and honest
   prefill/decode/acceptance/memory accounting. The short correctness comparison
   is not a speed record. Use full fresh prompts and no reused prompt/KV/output
   state for benchmark claims; separate model residency from prompt reuse.
3. Profile only after correctness passes, select changes with worthwhile
   expected benefit, and test exactness before promoting speed results. Keep
   failed candidates and matching controls. No hidden precision reductions,
   hand-picked easy prompts, extrapolated records, or speed claims from
   diagnostic work. Keep operating under the user's existing host constraints.

A dedicated subagent reviews progress every 30 minutes. It should challenge
unnecessary gating, repeated builds/tests, speculative scaffolding, and low-value
work; identify the next highest-value bottleneck; and check model identity,
correctness scope and benchmark fairness. It reports recommendations to the
coordinator and records concise dated feedback here in the lane. It does not
operate GPUs, alter services/settings, or authorize a shortcut. The coordinator
owns action selection, all device operations, and evidence-backed conclusions.

## Measured next step — 06:12 UTC

The [resident baseline](baseline/RESULT.md) and [class diagnostic](profiling/RESULT.md)
are independently audited. The next single candidate is existing p33 segmented Q8
variant6, split1, restricted to the48 attention projections at N2560/K6144. It preserves
lane products, ordered accumulation, SG32 reduction and BF16 output; no precision or
model change is allowed. It replaces packed shared-memory staging with exact expanded
codes/scales, adding47,185,920 device bytes perrank. Actual native equality and speed
must be measured; the slightly larger read footprint could erase the staging benefit.
Preserve the frozen baseline binary and source closure. A dependency-proven one-TU
build is preferable to rebuilding39 unchanged objects. Test control/candidate kernels
within one owner; do not create a fresh-server timing chain. End-to-end candidate
numbers remain provisional until their control comparison is fair.

## Storage incident hold — 06:33 UTC

The candidate stopped after seven exact pairs because USB NTFS exhausted MFT records,
not free data bytes. Both owners exited/drained; there is no new classified GPU fault.
Do not promote the partial candidate or start new device work. Preserve failed receipts
and source. Complete reviewed, verified per-request lossless archival of closed baseline
state binaries, preserving six micro fixtures and all JSON; no model or filesystem-setting
changes. Resolve record capacity before root admits any further bounded device task.

## Storage recovery complete — 06:56 UTC

Verified27 archive chunks preserve every closed baseline state byte.57,045 duplicate
raw files were removed after verification, with six micro fixtures and all JSON kept.
USB archive creation/readback succeeds,11.2GB free; no new NTFS messages or GPU faults.
The storage-capacity hold is resolved for small explicitly admitted tasks, not a blanket
capacity guarantee for another large run. The original candidate remains incomplete.
Independent partial readback confirms14 arms/7pairs; next is fixed3-case paired kernel
latency/byte equality, then deliberate completion of the remaining five prompt pairs
under a new bounded identity after source/admission review. Preserve the interrupted
run and do not combine timing sessions into a full resident throughput claim.

## Exact kernel result — 07:10 UTC

The [paired kernel test](attention-q8-p33/micro/RESULT.md) passed independently:
84/84 pairs exact, all72 measured pairs retained, summed candidate/control event
latency0.21412 with both orders improved. Owner exited cleanly and target card drained.
This supports finishing the unchanged candidate's five missing correctness pairs,
not an end-to-end speed claim. New completion identity retains original indices7–11,
12requests/13dumps, original arm ordering and exact baseline comparisons. Its file
forecast is below57,045 records released by verified archival; monitor capacity and
retain any failure. Do not rerun the seven passed pairs or merge timing sessions.

## All twelve attention pairs exact — 07:16 UTC

The [separate completion](attention-q8-p33/completion/RESULT.md) independently
verifies the ten remaining arms. All24 arms of the unchanged candidate now match
the original baseline, with the interrupted session and timings kept separate.
The focused kernel gain supports retaining this exact internal candidate, not
promoting a model speed record. Next lever:22 Q6_K GDN-QKV projections N10240/K2560,
existing p33 variant6/split1, first exact CPU arithmetic and same-owner3-case micro.
GDN-QKV's aggregate profile includes mixed formats; do not label it Q6-only time.
Before another full model suite, archive verified closed candidate state binaries
to recover file records; preserve original failed-request and JSON evidence.

## Q6 micro exact and faster — 07:28 UTC

The [Q6 micro](qkv-q6-p33/micro/RESULT.md) independently passes all84 pairs against
saved baseline bytes. Summed measured event latency is0.30441 of control; both
orders improve, all72 measured pairs retained. This supports one full-engine
candidate combining the48 verified attention sites with only22 Q6 GDN-QKV sites.
The arithmetic proof covers all binary16 patterns and signed scales; three real
payloads and full output bytes are authenticated. No full22 payload rescan is
needed merely to repeat that proof. The complete model gate still compares all
original prompt tokens/full states. Finish closed candidate archival before that
suite; do not publish micro timing as model speed or merge different sessions.

## Combined full-engine measurement next — 07:40 UTC

The single-entry native build and independent source/build/operating reviews pass.
Retain original26request/27dump schedule, all12prompt pairs and unchanged cap128,
fullRESET, target verifier and BF16KV. Compare every arm to the original baseline
before another request. Record absolute resident rates and within-run MTP behavior;
a previous-binary comparison stays explicitly between runs, not a matched causal
speedup. Do not begin a third micro before measuring this engine. All27 closed
attention-state archives are verified,56,981 files released, and explicit next-run
storage admission binds the plan. Byte/file forecasts are monitored, not quotas.
