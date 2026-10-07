# Fixed post104 duplicate retirement

Candidate helper only; its author has not run an operational mode. The coordinator
owns proof scans, review, deletion and restoration. No service, endpoint, GPU,
model, source-packet or host-setting operation exists in this tool.

The fixed selection contains52 scored tensor archives, with direct local anchors:

- 101c:16 duplicates; retain native-p1 boat/marble/bird.
- 102:16 duplicates; retain native-p1 boat/marble/bird.
- 104: candidate-check04–13 and timed-fast04–13; retain all20 native captures
  and control timed04–13. No103 archive or restoration anchor is eligible.

`selection()` enumerates every exact request name and corresponding fixture;
there is no supplied root, glob, retention-policy option or directory deletion.
Every eligible file is `output/validation/NAME/tensors.safetensors` below the
fixed lab root. The retained path is not among the candidates. The scope follows
`notes/2026-10-07-after104-storage-options.md`; recorded allocated reclaim is
about3.614GiB, subject to fresh stat/hash verification.

## Interface and prerequisites

Use exclusive absolute control paths outside the experiment artifact root:

```sh
python retire.py plan --out /absolute/control/post104-plan.json
python retire.py apply --plan /absolute/control/post104-plan.json \
  --sha256 PRINTED_PLAN_SHA256 --receipt /absolute/control/post104-applied.json
python retire.py restore --plan /absolute/control/post104-plan.json \
  --sha256 PRINTED_PLAN_SHA256 --receipt /absolute/control/post104-restored.json
```

Both planning and application require allthree exact server identities stopped
and their PIDs absent, with no fault/halt receipts.101c uses its actual historical
`resolution-stop-intent.json`/`resolution-stopped.json` format;102/104 use their
`controlled-reload-stop-intent.json`/`controlled-reload-stopped.json` receipts.
104's folder is `data/resume-20261007/client104-closeout/`. This helper never
stops an application or introduces another device health probe.

Each lane loads its unchanged sealed verifier only after checking the exact
packet manifest and both gate source hashes.101c/102 reconstruct the complete
native/candidate/timed proof;104 reconstructs timed-fast with its required
native/candidate/control chain. Each actual stored receipt must equal the
reconstruction. The corresponding closeout schema, success counts and file SHA
bindings must match. Do not edit these summaries between plan and application.
No103 proof replay/restoration is needed.

The plan includes full raw-file hashes, size and original stat identity, nlink1,
per-tensor metadata and independent execution associations, proof/source/stop
bindings, and a direct restoration map. Whole-file equality and distinct inodes
are mandatory; tensor parity alone is insufficient. Apply rebuilds the full plan
before its first write/removal and refuses any difference. Its output contains
an exclusive fsynced full-map intent, per-file intent/completion journal, and
completed or incomplete receipt. Exact no-follow file unlink and immediate
keeper rechecks use the hash-pinned reviewed103 helper's low-level primitives;
its old103 plan builder and operational modes are never called.

Restoration uses exclusive ordinary copies, never hardlinks or overwrite. It
admits the actual destination filesystem with a50GiB remaining floor, rounded
file allocation plus16MiB overhead, then verifies full hashes/nlink1 and fsyncs
files/directories. Space is not reserved. All52 destinations must be absent;
there is no automatic retry, rollback or partial-resume mode. Partial failures
preserve remaining/partial files and journals for separately reviewed recovery.
An interruption can fall between a filesystem operation and a completion event;
the durable per-file intent records the exact source/path/hash for reconciliation.

Run under exclusive coordinator ownership of these artifacts. The metadata/stat
checks do not prevent an unrelated writer from racing them. The keepers remain
on the same filesystem and are not independent backups. The recorded proof is
**verified before retirement**; unchanged full replay requires restored paths.
A restore receipt confirms ordinary file copies, not a new full proof or original
inode/ctime restoration. Revalidate with the unchanged gates separately.

## CPU controls

```sh
PYTHONDONTWRITEBYTECODE=1 python test_retire.py
```

Temporary synthetic files exercise the actual52-file deletion/copy round trip,
mapping protection, allthree stop formats,104-live refusal, source/summary/raw
hash drift, missing files, inode changes, hardlinks/symlinks, tensor metadata,
space refusal, no overwrite, and incomplete deletion/restoration receipts.
Wrapper controls verify each historical verifier signature and104's mandatory
control-receipt argument. Expensive sealed proof bodies are stubbed in these
tests; production `plan` and `apply` always execute the real pinned gates.
