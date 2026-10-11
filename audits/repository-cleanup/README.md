# Repository cleanup

The cleanup keeps useful findings, source changes and replay evidence at
traceable paths while reducing duplicated guidance and disposable files.
The first pass on 2026-10-10 covers the repository; external models, runtime
trees, mounts and running experiments are outside its mutation scope.

## Coverage and results

The [census summary](2026-10-10/census/summary.json) accounts for **64,981 files**:
53,344 tracked, 11,636 ignored and one then-untracked inventory tool. All
53,344 index paths were found. Each regular file was hashed, symlinks were
recorded without following them, and both nested dependency repositories were
included. No file changed during its read, and HEAD stayed at
`f7b5356bafa5bc2af06e9dffbc88822fb0d2cded` during the census. This is a file
inventory, not a claim that every historical experiment has been scientifically
re-reviewed. Local concurrent edits are represented by their observed hashes.

File contents occupy 3,577,517,822 logical bytes, excluding the root Git
directory's 549,746,707 bytes. Allocated file blocks differ from logical bytes;
directory overhead and shared inodes also affect `du` totals.

| Area | Treatment in this pass |
| --- | --- |
| Current state and chronological ledger | [CURRENT.md](../../CURRENT.md) reduced to a recorded-state summary; [original history](../../CURRENT-history-20261010.md) retained byte-for-byte at the same directory depth. Both hosts, pending decisions and protected artifacts remain visible. |
| Model navigation and results | [Root navigation](../../README.md), [model effort index](../../docs/model-effort-index.md), [reproducibility map](../../docs/current-reproducibility-map.md), [Qwen3.6 map](../../docs/qwen36-research-map.md) and [scoreboard](../../results/scoreboard.md) reconciled against retained evidence. Obsolete Qwen3.5 next steps replaced with dated outcomes and qualification gaps. |
| Experimental areas | [Experiment index](../../experiments/README.md) covers all 37 immediate directories, including small rescued-patch studies and research tools. Source-linked conclusions remain with their lanes. |
| Lessons and patch discovery | Eight scoped lessons surfaced in the existing [workflow playbook](../../docs/research-workflow-playbook.md); [patch catalogs](../../patches/README.md) and [note entry points](../../notes/README.md) distinguish retained history from current guidance. |
| Generated caches | Eleven tracked CPython cache files removed; all corresponding source files retained. [Exact paths, hashes, source identities and Git recovery](2026-10-10/dispositions.json). Logical bytes removed: **383,800**. |
| Link integrity | Six incorrect links repaired in three maintained notes. [Link checker](../../tools/check-doc-links.py) now has an opt-in whole-tracked-repository scan, including staged new documents. Historical host references are reported as unverified. |
| Other tracked source, patches, data, snapshots and outputs | Inventoried and retained. No unique patch, negative result, raw experiment result or model was deleted. |
| Ignored files and nested checkouts | Inventoried and retained. The protected graphsafe working tree includes a stage consumed by a historical replay script; it is not disposable merely because Git ignores it. |
| Root Git history | Size inventoried; no history rewrite or pruning. Identical Git blobs are already deduplicated. |
| External storage and checkouts | Existing [storage map](../../docs/reference-lab-storage.md) remains authoritative. No external artifact was moved or deleted. |

The precise pre-change file and duplicate lists are local generated artifacts:
`2026-10-10/census/files.jsonl.gz` and `duplicates.jsonl.gz`. Their sizes and
SHA256s are in the committed census summary. They are ignored to avoid growing
Git with repeatable inventory dumps. Dispositions and recovery identities are
committed separately. To create a fresh census at a new destination:

```bash
python3 -B tools/inventory-repository.py --output /tmp/lab-census-new
```

The output directory must not already exist. The tool reads all regular files
inside the repo, including ignored files, but does not follow symlinks or open
external models. The default action for every inventoried file is retention;
its role or membership in a duplicate group never authorizes deletion.

## Evidence kept and follow-up review

The census found 908 exact-byte duplicate groups of at least 1 KiB. This is a
review queue, not a space-saving total: sealed packet copies, Git objects and
independent consumers can require the same bytes at several paths.

| Material | Why it remains |
| --- | --- |
| Six large Laguna source bundles | Complete overlapping histories, but different tips and hash-bound provenance. Consolidation needs verified restoration of every original source identity and updates to all consumers. |
| Gemma source snapshots and repeated experiment helpers | Some are deliberate frozen packet dependencies. Removing a repeated copy could make a retained result unreplayable. |
| Eight large native-GDN prefill JSONs | Equal size but different SHA256s; preserve independent per-process/per-GPU evidence and their comparison pins. |
| Graphsafe Qwen `work/` and `staged-package/` | Protected generated research state, nested dependency histories and replay inputs. `repro/qwen36-27b-autoround-int4-b70/scripts/run-record.sh` defaults to `work/source`. Archive only after a complete restore test and consumer migration. |
| Recent Flash-Next fault traces and LTX packets | Support unresolved fault diagnosis and the current halt; unique failure evidence remains valuable. |
| Own-runtime tensor contracts | Active identity evidence. Compression requires compatible readers and unchanged original-byte verification. |

There are **231 preexisting literal pin mismatches** against two shared
Flash-Next verifier scripts (318 checks: 87 match, none absent). Cleanup does
not replace historical verifier hashes with current ones. The required repair
is to restore the exact qualified verifier identity or explicitly requalify a
new one; a matching new hash alone proves neither.

The broader link scan also exposes historical debt outside the old default
scope. Its explicit [baseline and repair map](2026-10-10/link-baseline.json)
records four remaining relative links: a copy-location community template,
a superseded LTX build-note path in a hash-pinned result, and two links inside
a frozen study-plan copy.
The last two stay byte-identical because plans and queue receipts pin them.
Companion mappings resolve their intended sources without rewriting the packet.
The broader checker validates the baseline's document and companion-source
hashes, so these exceptions cannot silently survive changed evidence or a
deleted destination.
Absolute host paths remain visibly unverified; they are not converted into
fictitious repository links.

## Validation and future cleanup

The [validation record](2026-10-10/validation.json) covers the local guide/package
workflow, broader link scan and preservation audit. The workflow now checks all
tracked Markdown and HTML on documentation changes. All 53,344 original tracked
paths were compared with the census; only the eleven listed caches were removed,
and the two script edits already in progress stayed byte-identical.

All 37 workflow commands passed locally, with the installed PyYAML dependency
verified instead of reinstalled. The link checker passed 13 tests and checked
4,753 documents: no new broken paths, four recorded exceptions, 101 unverified
host/template references, and no unreadable documents or invalid baseline pins.
The separate literal-pin check still reports the 231 preexisting mismatches.

Run the ordinary checks and the broader check with its explicit historical
baseline. The latter still prints known debt and fails on new broken paths:

```bash
python3 -B tools/check-doc-links.py
python3 -B tools/check-doc-links.py --all-tracked --baseline audits/repository-cleanup/2026-10-10/link-baseline.json
python3 -B tools/check-manifest-paths.py
python3 -B tools/validate-repro-guides.py
python3 -B tools/check-pinned-hashes.py
```

The pin check currently fails for the preexisting drift above. Link checking
does not validate every fragment, dynamically assembled path, hash or reader;
review those dependencies before a move. Tests of the new inventory covered
ignored directories, nested Git metadata, symlink boundaries, hashes, exact
duplicates, totals and output exclusion. Checker tests cover broader scope,
staged files, missing tracked documents and visible unverified references.

For each later batch, record old path, action, reason, replacement or archive,
original SHA256 and restore method. Preserve frozen evidence bytes. Verify
archives by contents and test restoration before removing originals. Update
maintained references and generators together, compare validation against the
recorded baseline, and report actual reclaimed space separately from improved
navigation. Keep current-state documents short and put dated chronology in
lane notes or linked history.
