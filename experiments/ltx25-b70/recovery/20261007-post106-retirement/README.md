# Fixed 106 archive retirement candidate

This helper is prepared for review only. Author validation used synthetic files;
no real plan, deletion, restoration, process probe, endpoint or GPU operation ran.
The live 106 application and all its outputs remain protected until the coordinator
performs an authorized necessary controlled reload and reviews a fresh plan.

The fixed set is exactly 40 `tensors.safetensors` archives from
`resolution-sampler-accounting-20261007-`: native-p1 and native-p2 for each of
the ten fixtures, candidate-check-04 through 13, and timed-fast-04 through 13.
Each maps **directly** to the corresponding protected
`resolution-client-reverse-20261007-native-p1-FIXTURE` archive. No restoration
chains, models, source, metadata, previews, failures, diagnostic accounting, or
other archives are selected. All 26 previous anchors plus these ten 105 anchors
are excluded from the deletion set. Estimated reclaim is 2.780 GiB; a real plan
reports current allocation. Storage admission for subsequent work is separate.

Before both planning and applying, exact 106 identity, PID/start/boot, absence of
that PID, controlled SIGINT stop intent and clean stopped receipt, and absence of
fault/halt markers are required. The sealed `verify_fast_receipt` reconstructs
native, candidate and fast quality from the original evidence. Counts and
closeout hashes must match. This does not promote the independently unsuccessful
driver-accounting diagnostic into valid performance evidence.

Keeper provenance is the exact reviewed post105 retirement plan and completed
receipt, pinned by SHA256 below. All ten keepers must still match their complete
recorded SHA256, size, inode, device, mtime, ctime, block count and nlink1. Missing
105 retired archives are never read or reconstructed. Each 106 candidate is
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
sealed 106 proof was verified *before retirement* and requires restoration of
all selected paths before unchanged replay. No post-retirement full-proof claim
is made.

Pinned inputs:

- 106 packet: `59765f873aa553104691053c43f0964725353ddb25df471f806b039e1aa4c6e2`
- 106 identity: `e292b16b347bf2673e3c7657aa17f85ebac70d58c00560c1c6d18ce1b53e9dda`
- 106 candidate gate: `6c66f4cfbccc2dfc64cb62782912f785398da7ffb5644c0efd93d990a3edb9b7`
- 106 fast receipt: `9371b161bc6a6daa304679edf1dc92347c17e134727a31a7ca1550f1375483e8`
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
