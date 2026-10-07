# Conditional storage plan after resolution103

Planning only while103 is active. No files were retired or content-hashed from
the active run. Do not implement/apply until the full103 proof passes, the
coordinator reviews an exact ledger, and a controlled application stop has
completed. Do not stop a healthy application solely to manufacture a cleanup
opportunity; combine this with the already-needed transition if one is required.

The next bounded A/B screen is estimated at64 raw captures:4.447739GiB of tensor
payload plus a5GiB total write allowance, retaining the50GiB free-space floor.
If103 leaves53.4GiB available, retiring30 exact duplicate archives would add
about2.084877GiB, giving55.484877GiB: only0.484877GiB over the next admission
threshold. These are planning estimates, not a reservation. Recheck the actual
destination filesystem after103 closes and immediately before the next writes;
include any new packet source copy (previous allowance384MiB) and other planned
writes. With that source allowance too, the illustrative margin is only0.110GiB.
Reduce the next finite screen or defer it if the full budget does not fit.

## Exactly what could be retired

Use the immutable103 plan at
`recovery/20261007-resolution-full-103/candidate-plan.json`, canonical SHA
`84bdccba3e2fe39b9bf5bcd1cd074c6ee74bbd8ade2a9be7aa63e945f5b07e1d`.
Only the30 emitted rows marked `timing_scope=bounded-continuity` are candidates.
The exact archive path for name N is
`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/output/validation/N/tensors.safetensors`.

| Candidate names, prefix `resolution-full-20261007-` | Retained names, same prefix |
| --- | --- |
| `timed-14` through `timed-23` | `timed-04` through `timed-13`, respectively |
| `timed-24` through `timed-33` | `timed-04` through `timed-13`, respectively |
| `timed-34` through `timed-43` | `timed-04` through `timed-13`, respectively |

Derive pairs by exact `expected_emitted_fixture`, not filename arithmetic alone.
Preserve all20 native captures,10 emitted candidate captures,10 initial timed
captures, all fills/setup outputs, every summary/request/worker receipt, full
raw hash lists, previews, logs, source packets and failed research artifacts.
Only each selected `tensors.safetensors` is eligible; no directory deletion.
Tensor payload is30×74,620,672=2,238,620,160 bytes; actual archive headers,
allocated blocks and hardlink counts must be measured before claiming reclaim.

## Minimal separate103 ledger and application

`retire-verified-outputs-99.py` supplies useful exact-file safeguards: exclusive
plan/intent/receipt, SHA plus device/inode/size/mtime/ctime/nlink checks, no-follow
parent traversal, fsynced per-unlink events, server-PID absence, and immediate
retained-reference rechecks. Its plan builder accepts only
`ltx.throughput-fixtures-96.v1` and external parity/preregistration receipts.
103 instead has source-bound same-size native/candidate/timed gates. Do not
coerce103 evidence into that historical schema or weaken the sealed verifier.
Prepare a separate small103 helper only after success, retaining the lower-level
exact-file safeguards and using a distinct reviewed schema.

Before listing eligibility, independently rerun the unchanged103 reference,
candidate and timed evidence checks while all raw files remain present; require
20 independent native executions/10 exact repeat pairs,10 exact candidate
outputs and all40 exact timed emissions with the full original fixture order.
Bind the complete campaign result, native/candidate/timed receipts, plan,
server identity, packet manifest, clean shutdown and postflight receipts by
full-file SHA. Refuse any partial, cached, nonfinite, failed, faulted or uncertain
run. Model provenance and each execution/prompt/graph/emitted-index association
must match those already verified receipts.

Each of the30 ledger rows must hold candidate and retained paths, full-file SHA,
size, allocated blocks, device/inode/mtime/ctime/nlink, fixture, request/prompt
IDs, emitted index, and all four tensor names/dtypes/shapes/content hashes.
Require complete-file bytes equal (not merely tensor values) and distinct
regular nlink1 inodes with no symlinks. If archive metadata makes byte equality
fail, preserve that candidate; do not normalize or rewrite it. All30 mappings
must be unique and the ten retained archives protected from retirement.

After root reviews the concrete ledger, apply only its exact paths while the
recorded server is absent, with a durable intent followed by individual unlink
events and completed/incomplete receipt. Revalidate every bound input and keeper
immediately before application and each candidate immediately before unlink.
No automatic retry after partial failure. This is duplicate consolidation, not
permission to discard failed experiments or their metadata.

## Restore and proof status

Store an explicit restore map `deleted path -> retained path + expected full
SHA/bytes`; the keeper is a byte-identical restoration source, not an independent
backup. Restore by exclusive ordinary-file copy, fsync file+directory, then
check SHA/size and nlink1. Hardlink replacement is unsuitable: the unchanged
same-size verifier deliberately refuses linked evidence files. Never overwrite
an existing path, silently use a missing keeper, or claim original inode/ctime
has been reconstructed. The verifier binds file bytes, while the retirement
ledger preserves original stat identities separately.

Preserve original successful proof unchanged and append the retirement receipt.
Mark the dataset as **verified before retirement;30 raw paths absent, restorable
from retained exact duplicates**. An unchanged full103 verifier must currently
fail missing-path checks until restoration; do not claim post-retirement full
proof, patch around missing files, or represent the retirement ledger as a new
full replay. Restoration consumes the reclaimed space again and needs admission
before copying. Reverification is a separate explicit operation after restore.

## Less disruptive cleanup alternatives

The existing maintenance ledgers show the obvious large caches already handled:
`data/maintenance/disk-cleanup-20261006.json` removed npm/uv/pre-commit/ccache/
go-build/APT caches; `data/maintenance/consolidation-20261006/summary.json`
archived and removed both vLLM caches, strict Qwen cache and libsycl cache;
`data/maintenance/staging-consolidation-20261007/summary.json` preserved and
removed all eight cold staging trees. The Qwen0.8B model-cache duplicate was
already deduplicated with both paths preserved. These earlier reclaimed bytes
cannot be counted again. Same-disk preservation archives, model caches,
currently-used GPU/compiler caches and backups are not disposable substitutes.
No additional safe2GiB cache candidate is established by those ledgers. A later
bounded read-only check of the exact already-cleaned generic cache paths could
measure regrowth, but must prove inactivity/reconstructibility before removal;
this plan performed no broad model scan or cleanup.
