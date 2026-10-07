# Fixed 107b archive retirement candidate

This helper is prepared for review only. Author validation used synthetic files;
no real plan, deletion, restoration, process probe, endpoint or GPU operation ran.
The live 107b application and all its outputs remain protected until the coordinator
performs an authorized necessary controlled reload and reviews a fresh plan.

The fixed set is exactly 40 `tensors.safetensors` archives from
`resolution-sparse-transport-20261007-`: native-p1 and native-p2 for each of
the ten fixtures, candidate-check-04 through 13, and timed-fast-04 through 13.
Each maps **directly** to the corresponding protected
`resolution-client-reverse-20261007-native-p1-FIXTURE` archive. No restoration
chains, models, source, metadata, previews, failures, diagnostic trace evidence, or
other archives are selected. All 26 previous anchors plus these ten 105 anchors
are excluded from the deletion set. Estimated reclaim is 2.780 GiB; a real plan
reports current allocation. Storage admission for subsequent work is separate.

Before both planning and applying, exact 107b identity, PID/start/boot, absence of
that PID, controlled SIGINT stop intent and clean stopped receipt, and absence of
fault/halt markers are required. The sealed `verify_fast_receipt` reconstructs
native, candidate and fast quality from the original evidence. Counts and
closeout hashes must match. The banked closeout/proof from commit `dc236bf46`
are pinned by file hash; their historical retained-application fields remain
unchanged, with the later stop evidenced separately. This retirement makes no
new diagnostic-validity or performance claim.

Keeper provenance is the exact reviewed post105 retirement plan and completed
receipt, pinned by SHA256 below. All ten keepers must still match their complete
recorded SHA256, size, inode, device, mtime, ctime, block count and nlink1. Missing
105 retired archives are never read or reconstructed. Each 107b candidate is
freshly hashed, compared to its complete proof and keeper, and required to have
a distinct inode. Fixture and four-tensor identities also agree across runs.

Operational interface (coordinator, within authorized work, after independent review):

```text
python3 -B retire.py plan --out ABSOLUTE_NEW_PLAN.json
python3 -B retire.py apply --plan ABSOLUTE_PLAN.json --sha256 EXPLICIT_SHA256 --receipt ABSOLUTE_NEW_RECEIPT.json
python3 -B retire.py restore --plan ABSOLUTE_PLAN.json --sha256 EXPLICIT_SHA256 --receipt ABSOLUTE_NEW_RESTORE_RECEIPT.json
```

Control files must be outside the artifact root. Apply rebuilds the complete
plan before writing its exclusive, fsynced intent containing the entire restore
map. Each file has a fsynced intent/completion event and a final complete or
incomplete receipt. Stop and keeper identity are checked before every operation.
No process is signaled, no server started, and no retry occurs. The coordinator must
maintain exclusive control over these stopped run artifacts; these checks are
not a filesystem-wide lock or atomic 40-file transaction.

Restore requires every destination absent and sufficient free space above the
50 GiB floor, plus block-rounded writes and 16 MiB overhead. It creates ordinary
exclusive copies, verifies hashes and fsyncs files/directories; no hardlinks or
overwrite. Partial failure preserves evidence and partial files for explicit
coordinator recovery; automatic partial resume is intentionally unsupported. The full
sealed 107b proof was verified *before retirement* and requires restoration of
all selected paths before unchanged replay. No post-retirement full-proof claim
is made.

Pinned inputs:

- Adapted reviewed post106 helper: `f84c78426081e503656e0a0faba124e5106829fec1aceeb68bd886b5823ed215`
- 107b closeout summary: `0201d9d02b5d2d9ffeea3f73f700430f779b31d1e44390907e05bfba040ca0a5`
- 107b post-completion proof: `a9f7792ce20e8367963e1cb3092b44b6f63ae50238b1ae460286638c558f94f9`

- 107b packet: `fb26b0d5d3d2d892bce046e93547e1b71bf4c7d34ba2b1d0992dfabf9a4ab1fb`
- 107b identity: `bcb2e9ad525f476d15c1bbef3c28205d7e4b1949bad85cb46167daa9ab18a0ce`
- 107b candidate gate: `3c4931720643f36c6016937bfb0ada7275292347fabfc89fec8af0f302dec737`
- 107b fast receipt: `bb89b4130201a39e4bfea2684c7edd93a01fbf515afb7b5b40ab9165574b7d65`
- Post105 keeper plan: `e7bcebdd89002487bc4e9c675a02de1b155fefc034e0b869ae88fa4eaea9ddfa`
- Post105 completed receipt: `c6490ffc178f90a637c725d2494dab39eecbc62b372180950b717adfa52ef573`
- Existing 103 file primitives: `043912bdf375d36f0691cfa3d000a66a48408747d5837871b3d1af8da76150bb`

CPU validation: `python3 -B test_retire.py` — 17 synthetic controls, including
real temporary-file deletion/copy roundtrip, live-PID/fault refusal, exact stop
identity, source/summary/receipt pins, missing or changed archives before first
intent, whole-file disagreement despite tensor metadata, hardlinks/symlinks,
inode drift, wrong mappings, cross-run keeper provenance and incomplete prior
retirement, storage refusal, exclusive restore, and partial I/O evidence.
Synthetic tests stub full numerical reconstruction and process existence; the
real owner-run plan/apply must perform the complete sealed reconstruction.
