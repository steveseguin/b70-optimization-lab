# Packet58ap: conditional one-card record chain

This private packet combines packet58aj's resident lookup record line with
packet58am's repaired `bcs-demand-retained32x2` candidate. It prepares a fresh
record chain; it contains no new device measurement and queues nothing.

The predecessor is **31.966820 tok/s**, `cmveqsmsl00ebrf014yvrsosx`.
The exact ledger value and hash are in `record-threshold.snapshot` and
`submission-policy.json`. The model is the **quantized compressed version**,
Unsloth UD-IQ3_XXS, with the unchanged packet49 arithmetic and exact oracle.

Read [WINDOW.md](WINDOW.md) before any coordinator action. The orchestration
READY file describes preparation. `verify_ready.py` recomputes device
readiness from the current proposed packet58am v5 output at launch. A missing,
incomplete, inexact, mismatched or insufficiently fast v5 refuses launch.
The first view remains exact but is warm-up for speed/drift. Both candidate
views must gain at least 0.5% over **each** warm control; drift must be <=3%.
The census supersession is disclosed in [RELEASE-AMENDMENT.md](RELEASE-AMENDMENT.md).

The chain is K1a, K1b, KD, W2m, WS, WS128x, WS128, with 90-second gaps,
fresh owners, whole-host admission, cooperative drain and no automatic retry.
Full BF16 KV, all twelve fixed prompts and every retained layer comparison
remain in place. Timing is the final WS128 only. The scope is 128 tokens;
`realistic_final_gate.passed=false`, strict512 false, and a second independent
timing run remains pending. The submission tool refuses a rate at or below
31.966820 or the pinned/current local record, and refuses any inexact chain.

The native candidate was **not rebuilt**. `parent-binding.json` records its
binary and 116 build-source hashes; source bytes are vendored in `lineage/`.
The small K1 command adapter alone was compiled to expose `--help` and a CPU
mode; both the original device core and the GNU CPU fixture remain bit-exact.
`native-artifacts.json` binds a verified archive of all six executables.
Restore missing local build files with `python3 -B restore_build.py`, then
run `seal.py --verify`. No mutable parent is a native restoration dependency.

CPU evidence is in `evidence/cpu-sequence.json`, `argument-gate.json`,
`python-cpu-gates.json`, and `submission-rehearsal.json`. Each native argv
was parsed and prepared on CPU in the real closed library environment.
The real stream sensors read synthetic streams; malformed streams and wrong
tokens refuse, but timing magnitudes do not stop a running request.
The existing single-view preparation probe internally selects demand off;
an additional explicitly labeled five-view CPU probe exercises both demand
views, both parity banks and resets. Its cap/retention changes are CPU test
fixtures, never a record workload. The ordinary seven real argv probes are
also retained. Device scheduling and device exactness remain unmeasured here.

The shared entry report is under `../../ops/packet58ap-orchestration/`.
Its preparation adapter still reports an unranked-ABI warning; the actual
binary CPU preparation is independently executed by `cpu_sequence.py`.

## Retention

`lineage/native-artifacts.tar.gz` is about 19.5 MB. It is deliberately retained
in Git: the exact parent executable is required and the parent is actively
changing. Every member was rehashed before sealing, originals were retained,
and `restore_build.py` verifies the archive and members before restoring only
missing files. No weights, cache or secrets are included. CPU stream/trace
fixtures remain local; compact receipts and hashes are tracked.
