# Closed restore20–28 compiler-cache retention

## Question and identity

Can one verified external archive recover useful headroom without repeatedly
moving small checkpoint sets? The fixed candidates are the eighteen directories
`/home/steve/inference/qwen38-27b-fp8-card{0,3}-20261023-restore{20..28}/cache/torch_compile_cache`.
They contain 8,766 regular files, 1,070,345,088 logical bytes and 1,088,151,552
allocated bytes. All file inodes are distinct. The metadata inventory fixes
every file stamp and 2,197 directory identities; preparation did not read cache
contents. Active restore29, application logs/state/overlays, `modelinfos`, vision
logs, model files and research results are outside the candidate set.

## Outcome

CPU preparation only. Fifteen tests exercise small temporary fixtures, with
service/mount queries intercepted. No real archive, copy, deletion or service
query has run during preparation. The archive destination is fixed:
`/mnt/usb-models/own-runtime-archives/closed-restore20-28-compiler-caches-20261023.tar`.

Archive and prune are separate one-shot operations. They require nice19/helper
cores, exact external mount/parent identity and at least 50 GiB remaining external
space (plus source bytes and 32 MiB tar allowance before copy). There is no native
execution, service mutation, restart, settings change or retry. A failed attempt
keeps its partial archive/receipts and blocks reuse of these operation paths.

## What worked

The archive hashes every source, copies through no-follow file descriptors,
fsyncs the tar and its parent, verifies every tar member and the whole archive,
then rehashes all originals. Its source pins also bind the prune implementation.
The prune step independently verifies the archive and originals again, holds the
recovery archive descriptor throughout deletion, and rechecks it before each
unlink. Each original is hashed immediately before an inode/stamp-checked
relative unlink through a held parent directory descriptor; that directory is
then fsynced. Directories are not removed.

Before the first unlink, a complete restore map is durably written to the
exclusive prune-start receipt and each cache's sibling
`ARCHIVED-torch_compile_cache-20261023.json` marker. Markers remain after success
and explicitly label the local compiler cache incomplete. Partial deletion is
recoverable from the full map even if interruption precedes final accounting.

Current configuration proof reads only `ActiveState`, `SubState`, `MainPID`,
`ExecStart` and `WorkingDirectory` for the three application units. It compares
their complete command arguments against retained restore29-ready receipts and
checks the exact restore29 state directory (vision uses its working directory).
No environment values are requested or printed. This proof runs before copying,
after verification, before pruning and before each cache-root deletion batch.

The prune step also checks effective write/search access to every unlink and
marker parent before writing its start receipt or any markers. Permission changes
after this check still halt the operation without retry; the complete recovery
map covers any partial deletion.

## What failed or remains uncertain

No test failed in the initial fourteen-test preparation run. That candidate is
retained under `lineage/closed-restore-caches-before-permission-review`; the
fifteenth test covers the added pre-mutation permission refusal. Historical closure
for restore20–22 uses successful graceful-stop/inactive-wait logs; its old
unprivileged owner scan was weaker than a complete privileged inventory. Later
complete passive drains corroborate that no old owners survived. Restore23–28
have subsequent-window preflight and complete passive post-stop drain receipts.
These exact evidence files are pinned in the fixed metadata inventory.

The current service check proves configuration, not absence of a hostile
same-user process opening an old cache or changing files after a check. Fixed
stamps, held descriptors and exclusive operation locking refuse observed drift;
the operation assumes the trusted coordinator does not concurrently reconfigure
services or reuse historical directories. There is no immutable-filesystem or
transactional deletion claim. Directory fsync failure refuses progress and
preserves evidence. No archive verification or reclaimed space is claimed yet.

## Evidence and patches

- [Archive helper](archive_closed_restore_caches.py)
- [Separate prune helper](prune_closed_restore_caches.py)
- [Fifteen CPU fixtures](test_closed_restore_caches.py)
- [Fixed metadata and closure inventory](receipts/closed-restore-caches-inputs.json)
- [Preparation receipt](receipts/closed-restore-caches-preparation.json)
- [CPU test log](receipts/closed-restore-caches-tests.log)

The helper imports exact SHA-pinned p199/p184 archive primitives. New files are
additive; previous sealed source, results and failed experiments are unchanged.
The 4.26 MB plain JSON input inventory is intentionally retained permanently in
Git: both archive and prune consume its exact SHA-pinned 8,766 file stamps and
2,197 directory identities to prevent scope expansion. It is original admission
evidence, not a transient build output. Recover its exact historical bytes with
`git show <preparation-commit>:experiments/own-xpu-runtime/integration/receipts/closed-restore-caches-inputs.json`
into a separate review path; never regenerate it from a partially pruned tree or
silently replace its pin. Its consumers and closure receipts remain in the same
commit so the old archive/prune decision can be reconstructed.
The archive uses each path relative to `/home/steve/inference` as its member
name. The receipt maps each exact original absolute path to that member and
records its SHA256 and original stamp. Restore by validating the archive and all
member hashes, extracting into a fresh separate directory, then reconstructing
only the recorded roots. Restoring a cache does not authorize starting an old
application. Cache generation is reproducible but the original bytes are kept
externally for research retention.

## When to revisit

The root coordinator may run these commands only after reviewing this frozen
preparation and independent review. Both helpers refuse changed inputs, current
service configuration or prior operation artifacts. Do not loosen pins or erase
failed artifacts to rerun; record and review any new attempt separately.

From `/home/steve/llm-optimizations`:

```bash
nice -n 19 taskset -c 8-15,24-31 /home/steve/.venvs/vllm-xpu/bin/python -B experiments/own-xpu-runtime/integration/archive_closed_restore_caches.py --plan
nice -n 19 taskset -c 8-15,24-31 /home/steve/.venvs/vllm-xpu/bin/python -B experiments/own-xpu-runtime/integration/archive_closed_restore_caches.py --copy-verify
nice -n 19 taskset -c 8-15,24-31 /home/steve/.venvs/vllm-xpu/bin/python -B experiments/own-xpu-runtime/integration/prune_closed_restore_caches.py --prune-verified-copies
```

`--plan` performs metadata/source-pin checks only, without service or mount
queries. Successful copy creates `closed-restore-caches-archive-start.json`,
`closed-restore-caches-archive.json` and a tar SHA256 sidecar. Prune creates
`closed-restore-caches-prune-start.json`, per-root markers, and
`closed-restore-caches-prune.json`. Receipt JSON is kept under `integration/receipts`.
