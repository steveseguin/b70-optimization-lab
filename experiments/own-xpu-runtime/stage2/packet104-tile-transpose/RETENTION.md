# Packet104 retention

Keep copied source files, deterministic derivation scripts, the compressed
packet100b route manifest, its 46,080-byte route payload, build receipts,
protocol logs, proposed queue plan and pending integration views. The original
micro-only preparation added no tracked file of 1 MiB or larger; packet104b's
required RoPE input and final 200 MB build limit are documented below.

`build/` is ignored and bounded below 300 MB. Recreate the native micro with
`build_microbench.py` under the documented CPU affinity, priority and 8 GiB
limit. It compiles only the actual micro include closure plus the required
prepared-submission wrapper; no parent engine build or orchestration output
is needed. `derive.py` and `derive_small.py` regenerate candidate headers from this packet's
copied sources. A full model build, if the micro qualifies, still needs the
frozen packet100 runtime build inputs and its 12,582,900-byte generated RoPE
header identified in `source-origin.json`; that header is not a micro input.

`first-build-before-dispatch-audit.json` is a superseded preparation receipt.
Its binary remains `build/microbench-first` locally; it was never executed.
Its source version is preserved by commit `88cbff92c`. Later build receipts
describe the corrected selected draft baseline. No compiled binary is a
portable public release or a model result.

## Packet104b retention

The model build now has a **200 MB** ceiling. Immutable inherited object files
are read in place and hash-bound; compiled outputs remain ignored. Rebuild with
`build104b.py`. No device binary is executed by that script. Shared CPU K
fixtures are read from the unchanged packet97 paths, avoiding duplicate binary
copies; startup retains their launch argv and hashes. Redundant per-fixture
output scratch is removed only after matching its native receipt hash.

`evidence/micro-B/samples.jsonl.gz` preserves all original timing rows;
`kernel-boot-before-review.jsonl.gz` preserves the preflight kernel log.
`evidence/micro-retention104b.json` records original and compressed SHA256
values. `restore_evidence104b.py` restores missing original files and refuses
a changed existing file. Original local files are retained, not removed.
The screen override calls the restore check before validating original receipts.
Generated driver caches stay ignored. The roughly 4 MiB `rope.bf16` is a required
runtime input copied bit-for-bit from packet100 (hash in the build receipt),
not disposable evidence or a model weight; it can be restored from that exact
parent file. Large artifacts are retained because byte identity and exact
reproduction require them, not as performance claims.

Final packet104b build accounting is 186,640,277 bytes, including immutable
fixture hardlinks under `build/startup-inputs/`. Those snapshots prevent sealed
inputs from resolving outside the repository. Their hashes and original paths
are recorded in `startup97e.json` and its archive. They consume no duplicate
filesystem blocks on this host. Startup-only `.o` scratch is reproducible from
the retained source and command; it is removed after linking to preserve the
200 MB limit. Earlier successful startup evidence before this seal-path fix is
retained with the `.before-input-snapshot` suffix; it is superseded, not used by
current seals. Packaging-refusal logs remain as evidence, not runtime faults.
