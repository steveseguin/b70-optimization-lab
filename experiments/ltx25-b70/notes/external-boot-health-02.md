# Bounded health assessment after the user-confirmed reboot

Prepared September14,2026 for boot `5414a640-c223-4a67-baa2-ec2f4c4c5917`.
The user reported a freeze and confirmed rebooting afterward. The agent did
not reboot or reset the computer. See [incident evidence](user-reported-freeze-02.md).

The earlier same-boot diagnostic `scripts/check-incident-health-01.py` never
ran natively. Its passive check passed on the old boot, but the changed boot
invalidates its exact admission. Preserve that source and its check-only evidence
as an unexecuted historical preparation. It also predates the source-closure
and single-worker admission improvements in this successor.

The new [diagnostic](../scripts/check-external-boot-health-02.py) binds
[admission02](../data/external-boot-health-02/admission.json), SHA
`131ab0b474d38c7bde4eceb6f64718e4ee1099ff559dc6d849f31f8a3b65e8ab`.
It pins the user-confirmed new boot, unchanged old FAULT bytes, original runtime,
helper hashes, original ordinal device properties including UUID/driver, and
the complete canonical2261-record new-boot kernel prefix. That prefix contains
no existing GPU/host detector matches or OOM signatures. New fault/error records
are rejected; historical prefix loss or alteration also refuses admission.

The local recovery procedure permits one bounded health assessment after passive
risk review and a quiet interval; [policy review](same-boot-health-assessment-policy-review-01.md)
records the exact scope. This is not permission for model requests, reset,
reboot, settings changes, or an automatic retry. The diagnostic keeps the root
FAULT byte-identical and reports `model_admission=false` even on success.

One parent holds the host/benchmark/four-card locks and checks absent incident
processes, no container, unowned render nodes, unchanged PCI mapping, unbound
port8188, at least16GiB available RAM and a quiet interval. It creates one
exclusive output directory and spawns at most one worker. The child validates
parent PID/boot/source/admission and inherited lock descriptors, then creates
an exclusive worker-started receipt before importing Torch. Repeated worker
entry cannot rerun native work. Original FAULT and source/runtime identity are
rechecked throughout.

The native scope is four original1024² F32 copy/add/sum checks followed by
twelve directed256² BF16 inter-device copies. Each card must have exactly the
saved ordinal properties before allocation. A kernel/identity gate precedes
each peer-source allocation and each directed copy. No XCCL, model weights,
benchmark, cache clearing or host setting change is involved; Torch's
process-local16threads and strict determinism match the prior diagnostic.
The peer copies test tensor transfer results, not the driver's physical
transport mechanism or transport performance.

The worker has a60second bound. Timeout or parent interruption sends at most
one graceful SIGINT and waits at most10seconds; no reset, kill escalation or
retry follows. A stuck child is recorded and retains inherited exclusive locks.
Parent postflight preserves journal and ownership evidence on success/failure;
any failure leaves the hold in place. A pass establishes only the tiny tested
device paths in that attempt. It does not prove large-memory model transitions,
full-clip correctness, endurance, or subsecond generation.

The [new passive check-only receipt](../data/external-boot-health-02/check-only-01.json)
passed without native imports or device discovery. Source review/tests and any
later native result must be recorded separately; check-only is not a health pass.
No automatic fault removal or application start is implemented by this script.

Independent source review and16 pure journal/AST tests passed for source SHA
`1e55edc46ce3efe1642ea5847a376a5a9cfea6d3afbf3858835951b0c36f8abd`;
[review receipt](../data/external-boot-health-02/source-review-01.json) binds all
helper/admission/test identities. The admitted boot prefix contains seven
priority3 USB/audio errors, explicitly listed in the receipt; it is not wholly
error-free. The exact historical records are preserved, and any new such error
fails the assessment. Failed test-only assumptions and their corrections are
preserved separately. No native result follows from these source tests.

## Actual assessment and root admission

The one native attempt ran19:29:19–19:29:31UTC, parent8068/worker8088,
and both exited0. All four copy/compute checks and all twelve BF16 directed
copies passed. Device UUID/properties matched the original ordinal mapping;
strict determinism was enabled. Parent postflight and a separate root locked
passive recheck found released render nodes, absent diagnostic processes,
unchanged boot, and no new kernel records/faults. No reboot/reset, host settings
change, model load or repeated probe occurred.

The [native result](../data/external-boot-health-02/result.json),
[worker result](../data/external-boot-health-02/worker-result.json) and compressed
journals are preserved. The root then reviewed those results and archived the
old-boot FAULT byte-for-byte using the one-use
[archival script](../scripts/admit-external-boot-health-02.py).
[Recovery admission](../data/external-boot-health-02/recovery-admission.json)
and [completion receipt](../data/external-boot-health-02/fault-archive-completed.json)
bind that state transition. The original model campaign remains failed.
No large-model or stability qualification is implied by archiving its hold.

The first root archival invocation used system Python for the metadata-only
runtime verifier; it refused before passive admission or any file/latch change
because that interpreter has no Torch package metadata. The corrected invocation
used the original venv and the explicit archival script. This did not rerun the
native health probe or relax runtime identity. Future runtime-fingerprint checks
must use `/home/steve/.venvs/ltx25-baseline/bin/python`, even when stdlib-only.

The next admitted operation was the guarded tiny CPU encoder lifecycle test,
which [passed all six cases](host-embedding-resident-lifecycle-native-01.md).
LTX remains stopped pending a reviewed successor runtime and full-model gates.
