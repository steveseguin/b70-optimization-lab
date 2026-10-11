# Historical verifier recovery — October 10, 2026

The 231 literal pin mismatches are now individually classified and bound to
their original client bytes in [pin-audit.json](pin-audit.json). **230 have exact
historical verifier copies; A317 remains blocked by a wrong-family pin.**
Original clients, supervisors, generators, result evidence and shared verifiers
are unchanged. This is source recovery and CPU validation, not a new benchmark
or authorization to replay. The [current-state record](../../../CURRENT.md)
and subsequent owner/host receipts govern live gates; this audit describes
the identities at the source commit below.

## What was recovered

The scan at `8c4505c311ba4c98fb1edcea0d22e2137a739997` covered 318 literal shell
pins: 87 match the present path, 231 drift, none are missing. All 231 holders
are distinct frozen Flash-Next clients. Eight N32 versions cover 230 clients:

| SHA-256 prefix | Clients | Git commit containing exact bytes | Preserved copy |
| --- | ---: | --- | --- |
| `0bd36f13056d` | 24 | `ea58981cda85` | [Existing lossless recipe snapshot](../../../repro/qwen38-flash-next-fp8-tp4-mtp1-lossless-b70-27tps-20260905/verify-moe-selection-frozen.py) |
| `13073e712ba4` | 9 | `d1db2695d3c9` | [Existing placement snapshot](../../../repro/qwen38-flash-next-fp8-tp4-mtp1-placement-b70-32tps-20260906/verify-moe-selection-frozen.py) |
| `20546ff1b349` | 16 | `33500141c1a7` | [Existing Triton-HC snapshot](../../../repro/qwen38-flash-next-fp8-tp4-mtp1-hctriton-b70-37tps-20260907/verify-moe-selection-frozen.py) |
| `4f4942289f38` | 108 | `4e27ee27f406` | [Recovered snapshot](../../../experiments/qwen38-flash-next-fp8-b70/historical-verifiers/sha256-4f4942289f38.py) |
| `790f48b37e51` | 7 | `d1356e5a2faf` | [Recovered snapshot](../../../experiments/qwen38-flash-next-fp8-b70/historical-verifiers/sha256-790f48b37e51.py) |
| `94487432c575` | 2 | `66285ee8e0bd` | [Recovered snapshot](../../../experiments/qwen38-flash-next-fp8-b70/historical-verifiers/sha256-94487432c575.py) |
| `a464b0f6a46e` | 57 | `d5212f63c84c` | [Recovered snapshot](../../../experiments/qwen38-flash-next-fp8-b70/historical-verifiers/sha256-a464b0f6a46e.py) |
| `dd58fde9d6ea` | 7 | `15f84050218f` | [Recovered snapshot](../../../experiments/qwen38-flash-next-fp8-b70/historical-verifiers/sha256-dd58fde9d6ea.py) |

The manifest retains every full SHA-256, original path, Git blob and commit,
client path and client SHA-256. The five additional snapshots total 64,356 bytes;
three existing copies are reused. Each snapshot was extracted with
`git show <origin_commit>:<original_path>` and independently compared byte for
byte, by SHA-256 and by Git blob ID. CI verifies bytes and Git blob identities
without requiring a full-history clone. Never edit these snapshots in place.

A317 points at N16 while pinning `c874852b…`, the N32 verifier's digest.
Neither recorded N16 version (`076ec3f3…` or `9762fe69…`) matches. Its
[original generator](../../../experiments/qwen38-flash-next-fp8-b70/tools/rewrite-q38-a311-to-a317-mtp1-w13-blockn16-screen.py)
explicitly says the screen bypassed the frozen client; the
[A317/A318 result](../../../experiments/qwen38-flash-next-fp8-b70/notes/2026-09-07-a317-a318-the-w13-tile-never-applied-at-mtp1.md)
records that the tile change was inert in that MTP1 screen. Both sources are
hash-bound in the manifest. Substituting N32 code for an N16 map or inventing a
replacement pin would falsify this history; preparation refuses A317.

## Maintained replay paths and dependency boundaries

The lossless, placement and Triton-HC recipes already use frozen snapshots via
the [September repair](../../../notes/2026-09-09-replay-and-validator-audit.md).
The fused-QSA and exact-GDN recipes still match the shared N32 verifier.
All five verifier descriptors, replay makers and identity scripts are now
checked by the explicit historical-review mode; their source was not changed.

Before editing, the audit searched path/hash consumers. Frozen client hashes
are used by supervisors, rewrite generators and recipe hash manifests; public
package dependencies also name historical clients. This is why the repair
redirects a **new client derivative** instead of editing 231 clients and
re-pinning their parents. Other absolute-path/variable-held hashes, retired
staging trees, runtime libraries, model receipts, ports and output directories
remain separate replay requirements. Recovering one verifier is not full
dependency closure or proof that every client was historically executed.

## CPU-only checks and preparation

Run from the repository root:

```bash
python3 -B tools/check-pinned-hashes.py --historical-manifest audits/repository-cleanup/2026-10-10/pin-audit.json --quiet
python3 -B -m unittest tools/test_pinned_hashes.py tools/test_flash_next_frozen_verifiers.py
python3 -B tools/prepare-historical-verifier.py \
  experiments/qwen38-flash-next-fp8-b70/tools/run-tp4-mtp0-2304-ple-only-a56-fullgraph-w13n32-client.sh \
  --output-dir /tmp/a56-verifier-review
```

The output directory must be new, outside the repository, with an existing
parent. Preparation validates the complete manifest, then copies the exact
original client and verifier plus a derivative redirecting its two verifier
references. Every 40/64-hex token remains unchanged. All files are read-only,
without execute bits, and code filenames end in `.txt`; `receipt.json` hashes
the inputs/outputs and explicitly records the unchanged frozen parent-chain
constraints and requirement to consult live host gates. It runs no shell, GPU
code, verifier or generator.
Use an explicitly reviewed successor generator to build any later full packet;
do not drop the derivative into a frozen supervisor.

The default checker still exits 1 with 231 raw historical path mismatches.
Reviewed mode exits 0 only when the exact catalog, snapshots, blocked evidence
and maintained verifier identities validate. It reports **230 recoverable and
one blocked**, never 231 repaired live paths. New drift, changed clients,
missing targets, changed snapshots, duplicate/stale exceptions or moved
maintained identities fail. `--json` exposes full findings. Scope is
Git-tracked `.sh` files under `repro/`, `experiments/`, `scripts/` and `tools/`
(including staged additions); it does not interpret shell variables, absolute
paths, non-shell pins or runtime dependencies.

Validation: 17 new mutation/integration tests plus the three existing frozen
verifier tests pass. All 230 clients pass two-reference/hash-token preservation
checks. Real CLI preparation and output re-hashing passed for one client from
each of the eight versions in disposable directories; A317 was refused before
writing. No historical script was executed and no GPU/system state was touched.
