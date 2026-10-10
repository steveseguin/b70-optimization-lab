# Packet 135: storage ownership accounting

CPU-only successor to packet 133b. The selected production arm remains 145
frames, split36 text placement, cone graph, serial display on card 3, legacy
audio/auxiliaries, parent capture reserve, idle maintenance, 60-second GC,
digest cache, full fingerprint snapshots and background storage sampling.
This preparation performed no GPU, launcher, check-only, port 8188, unit,
process-signal, host-setting, existing-run write or ltx-stream operation.

## What the stopped run can establish

The halted 133b run ended after receipt 72; request 73 failed at 14:48:49 UTC.
The coordinator subsequently renamed its directory with
`.completed-20261010T145013Z`. Its generic halt and failure records contain no
path, inode or observed link count. All 348 retained regular files have one
link at inspection. The shared stream133b output/request names from that
session are no longer available there. **The offending historical path and
linker are unknown.** Neither an external tool nor any particular disposer
can be blamed from this evidence.

[The audit](../data/resume-20261008/continuation135-tests/storage-incident-audit.json)
records the full run path, receipt hashes, scope and source findings. Receipt
72 reports 1,086,050,304 allocated bytes, 73,568,780,288 free bytes, a 16 GiB
allowance, the 50 GiB reserve and 256 MiB pending margin. This halt was not
capacity exhaustion.

The parent guard actually checks `st_nlink != 1`, including **zero**, rather
than only values greater than one. A successful pathname stat can observe
zero links when a concurrent unlink completes after lookup. A bounded CPU
scratch reproduction using only creation and deletion observed 26,055 such
zero-link stats; it created no hard links and removed its scratch. This
establishes a plausible alternative to linking, not the historical cause.

Sealed source, launch and resolution searches, including ComfyUI core, found
no filesystem hard-link creation call. Atomic evidence and preview publication
use `renameat2(RENAME_NOREPLACE)` without a hard-link fallback. Graph receipts
use exclusive file creation. The sink reads with `av.open`. Candidate deletion
paths are consumed-preview disposal in the client, stale-anchor removal in
`session.py`, and frame-anchor pruning in `integration.py`. A directory's
ordinary multiple links cannot trigger this guard: it handles directories
before testing regular files.

## Change and boundaries

The accounting scope is inherited: the run itself, prefix-selected output and
request entries, and prefix-selected output/validation entries. Other prefixes
and shared parent directory blocks remain excluded. Regular-file allocated
blocks are charged once per `(st_dev, st_ino)`; distinct files with identical
content are still separate charges. Directories retain their own charges.

An unusual link count, changing link count or inconsistent observed inode
membership gets one whole-tree retry after 10 ms. That retry discards cached
directory membership. Zero-link entries are deleted files, not external links.
A stable multi-link inode passes only when its link count matches its distinct
owned entries. Unaccounted links refuse with the full path, nlink, owned link
count, device and inode. The background failure retains the complete message
so the next halt will contain evidence the old halt omitted. A failed scan
does not commit partial totals.

The 50 GiB reserve, allowance grammar/default and selected allowance, 256 MiB
background pending margin, freshness and publication-epoch checks are unchanged.
Descriptor-relative no-follow traversal, cross-device refusal, special-file
refusal and entry/depth bounds remain. There is one wait per scan, not per
file. Scans remain non-atomic metadata observations; a persistently changing
namespace can conservatively refuse after the bounded retry. No claim is made
that this detects every adversarial filesystem change between observations or
attributes links to processes.

## Packaging and CPU validation

Parent manifest: `ed908a9031a937801d17264edacfe0807bea543badc412a32eb6118daa214fd3`.
All changed parent bytes are preserved under `provenance/packet133b` and the
parent manifest is a recursive dependency. Packet 135 uses numeric id 135,
`stream135-` names and clip bases 13500000/13501000. All 220 qualification ids
and numerical contracts remain equal; graph equivalence is checked after
namespace and clip-id normalization. No model arithmetic is changed.

The sealed-import gate runs two exact startup-path modes plus an inventory
probe covering all bundled components and runtime helper copies. Device,
server and network imports/operations stay blocked. Missing helper and oracle
negative controls exercise the actual sealed import layout. The client pins
the inner plan identity, never the JSON envelope hash, with the all-pins test.

[Contract](../recovery/20261010-continuation135-stream/CONTRACT.md),
[future command](../recovery/20261010-continuation135-stream/LAUNCH.md), and
[build receipt](../data/resume-20261008/continuation135-build.json) carry the
exact sealed identity and final counts. Native sustained streaming remains
for the coordinator; CPU fakes do not establish native speed or output parity.

## Reproduce preparation

Packet: `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-135`.
Manifest: `4356482eae2f1d7ac95b17e6483379ceed0cc90ed488d46765803451980402c3`.
Inner plan: `7750e7b54c885f99a73ab87b17013fc0a850a1af942f0c00422adbae596258c4`.
Input inventory: `2f39540fc2c08ebfa9061aee7b9603dac40dd44bea70cf7352e930b28fb1f859`.
The manifest binds 2,327 files, plus manifest/status give 2,329 physical files.
Thirteen changed parent-bound files retain originals; the additional changed
entry is the exact parent manifest. No parent-bound path is deleted.

From the repository root, every CPU command uses this prefix:

```bash
nice -n 19 env OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1 /home/steve/.venvs/ltx25-baseline/bin/python -B
```

Append the script and arguments:

```text
experiments/ltx25-b70/recovery/20261010-continuation135-stream/runtime_packet.py --inspect-assembly
experiments/ltx25-b70/recovery/20261010-continuation135-stream/runtime_packet.py --build --input-inventory-sha256 2f39540fc2c08ebfa9061aee7b9603dac40dd44bea70cf7352e930b28fb1f859
experiments/ltx25-b70/recovery/20261010-continuation135-stream/run_tests_135.py
experiments/ltx25-b70/recovery/20261010-continuation135-stream/run_client_suites_135.py
experiments/ltx25-b70/data/resume-20261008/continuation135-runtime-validation.py
experiments/ltx25-b70/data/resume-20261008/continuation135-verify-packet.py
```

Build destinations and validation logs are exclusive; an existing sealed packet
is verified read-only, never overwritten. Set TMPDIR to a fresh owned CPU test
scratch directory for client suites. Remove only that scratch after all children
finish. This preparation used `continuation135-tests/scratch` in the lane data
folder; it wrote no scratch into existing model runs or ltx-stream.

## Development evidence

The first recovery discovery loaded six copied expectations for parent 133 or
133b clip ids. Those fixtures were corrected to parent 133b and packet 135 clip
ids, and a full clean discovery was started. The initial log remains available;
no sealed runtime bytes changed. The first CPU-runtime driver completed all
three cases but correctly marked its aggregate invalid when fixture source
hashes changed during execution; the unchanged-source rerun passed.

The first focused client check encountered the concurrently authored packet134
registration before its sealed plan existed. After that worker sealed134 and
filled its pins, the unchanged all-pins checks passed. That concurrent work
was preserved. The new135 cleanup callback tolerates the outer CPU harness
having already removed its owned temporary tree.

The repository-wide literal pin audit still reports the same231 unrelated
Flash-Next drifts (318 checked,87 matching); no unrelated pin was rewritten.
Packet135's recursive closure passed. Documentation and manifest-path integrity
checks are recorded alongside the CPU logs.

## Final CPU result and commit boundary

- Recovery: **1,076/1,076**, no skips, 1,148.330 seconds in the clean full run.
  The initial full run was1,070/1,076; its six stale identity assertions are
  retained in `recovery-development.log`.
- New storage filesystem cases: **15/15**, included in recovery.
- Sealed imports: **9/9**, included in recovery; three preseal child probes;
  **67 helper copies** (36 components and31 runtime copies).
- Full shared-worktree client regression: **6,718/6,718 across45 suites**,
  including **36 inner-plan assertions across18 packets**.
- The exact135-only client committed separately from the concurrent134 work:
  **113/113 contract +208/208 integration checks**, with **34 inner-plan
  assertions across17 packets**. The shared working file was never rolled back.
- Mocked preflight: **10/10**; three CPU runtime cases and **22/22** exact
  output comparisons, with unchanged author-source hashes during the clean run.
- Recursive closure: **2,327 bound files**,2,329 physical files. Zero Python
  caches in authored and sealed trees. Owned scratch removed; the auditor's
  bounded `/tmp` reproduction removed its own temporary directory.

The shared client also contains packet134's unfinished changes from another
worker. The full suite tested that combined working tree. To keep commits
focused, packet135's registry, prefixes and inherited gate membership were
applied separately to the unchanged committed133b client, and that exact
source passed the two135 suites before staging. Both tested source snapshots
and their hashes are retained under `continuation135-tests`, with
`client-commit-isolation.json` explaining the boundary. Packet134's edits stay
in the working file and are not adopted by the135 commit. The build receipt's
shared-client source pin names the separately tested committed135-only bytes.
The full-worktree source hash is recorded separately with its suite counts.

All native model, memory and performance qualification remains pending for
packet135. No launch, live request or operational change occurred here.
