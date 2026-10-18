# Reviewed screen bulk cleanup

`cleanup.py` archives only `run/adapter/build/driver-cache` and
`run/input-bundles` below v4-lanes or v5-bracket screen evidence. It never
removes a directory, JSON/JSONL receipt (including gzip copies), source tree,
queue entry, service or job. No cleanup was executed during implementation.

The coordinator maintains [closed.json](closed.json). A packet must explicitly
say `CLOSED`; unspecified packets remain live. Packet90 closes only the literal
`hc-weightcache` view, leaving E1 and production live. `84s` means the screen
views, not packet84's record chain. Packet82 and packets91–94/97–101 are absent
from the closure map and remain protected. The file records the earlier manual
archive location; missing caches/bundles need no restoration or replacement.

A screen also needs a matching `DONE` lane-queue receipt, with successful exit
facts and the identical embedded fault-review object. An explicit job output
must contain that screen; a grouped job shares its fresh review across its
screens. Post-screen review is evidenced by a `done-*-reviewed-*.txt` ledger or
the coordinator's `reviewed_jobs` list. The latter names today's jobs reviewed
under the owner's review-15 brief. A fault preflight alone is insufficient.
Failed or unreviewed jobs are skipped. Packet86's deliberately inexact
diagnostics can qualify with DONE plus device-complete and lease-release proofs;
cleanup does not turn them into quality passes.

Plan only:

```sh
nice -n 19 ionice -c3 taskset -c 8-15,24-31 python3 -B \
  experiments/own-xpu-runtime/ops/screen-cleanup/cleanup.py --plan </dev/null
```

The JSON plan lists each run, exact file paths and SHA-256 values, retained
files and reasons, logical bytes, and estimated reclaimable bytes. The estimate
counts hard-linked bytes once and excludes inodes with links outside the
deletion set. It is not a promise of filesystem free space. `DONE` means no
eligible bulk remains; protected receipts can remain there. `SKIP` explains
missing completion/review evidence.

Before selecting any file the tool reads every live packet's window and identity
JSON, including build/compat trees and linked external result trees. Named hash
entries protect their actual resolved paths; identical bytes in an unrelated
file do not make that file an input. Hashes without a named path conservatively
protect every matching file. Shared screen symlinks are classified using the
real screen owner. Unreadable/malformed live documents abort the plan. Links in
candidate bulk paths are refused.

The coordinator can execute after reviewing a fresh plan:

```sh
nice -n 19 ionice -c3 taskset -c 8-15,24-31 python3 -B \
  experiments/own-xpu-runtime/ops/screen-cleanup/cleanup.py --execute </dev/null
```

The default destination is
`/mnt/raid-models/own-xpu-runtime-archive/screen-bulk/`; execution requires the
RAID mount. There is one uniquely named tar.gz per run, with a SHA-256/size
manifest inside and an adjacent `.manifest.json`. Tar hard links are preserved.
Every file is read back from the archive, including every hard-link member,
and compared with its original hash and byte count. Archives and manifests are
flushed before deletion. All selected runs are archived before any unlink, so
hard links between runs are handled too.

After archiving, a fresh full plan rechecks closures, reviewed completion,
all live window/identity references and source fingerprints. Changed eligibility
aborts deletion. Each source is checked again immediately before unlinking it.
Only the exact verified file list is unlinked. A separate archive lock prevents
two cleanup invocations; lane queues are never opened for writing or locked.
The coordinator must serialize changes to closed runs and their closure/review
entries with execution. Live packets stay excluded; no queue or GPU is stopped
to obtain a cleanup window.

An interrupted deletion can resume against the existing full archive. Its
entire content is verified again, including already-removed source files.
An archive/manifest mismatch, missing manifest or corrupt archive fails closed;
inspect the retained source/archive rather than replacing evidence blindly.

To restore, use the manifest's repository-relative `run` directory and extract
the tar into an empty temporary directory first. Verify every listed SHA-256
and size, including hard links, then copy the listed relative files back under
that run. `MANIFEST.json` is archive metadata and is not a source receipt.
Existing source receipts must not be overwritten during restoration.

Mock-filesystem tests exercise actual tar creation, hard-link reads, deletion
and interrupted resume only under pytest's temporary directory:

```sh
nice -n 19 ionice -c3 taskset -c 8-15,24-31 \
  /home/steve/.venvs/deepseek-v4-xpu/bin/python -B -m pytest -q -p no:cacheprovider \
  experiments/own-xpu-runtime/ops/screen-cleanup </dev/null
```

The checked-in plan summary is a dated observation, not execution authority.
Always run `--plan` again. `--root`, `--closed` and `--archive-root` support
temporary fixtures and explicit coordinator paths; neither mode defaults to
deletion.
