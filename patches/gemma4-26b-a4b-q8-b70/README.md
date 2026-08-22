# Gemma 4 26B A4B Q8 record-source packet

This directory is the in-repository source of truth for the one-B70 Gemma 4
Q8 short-decode record stack.  The canonical aggregate is:

[llama-cpp-c926ad098-gemma4-q8-record-source-20260701.diff.gz.b64](llama-cpp-c926ad098-gemma4-q8-record-source-20260701.diff.gz.b64)

It restores the complete llama.cpp source state that was snapshotted
immediately after the accepted `124.97714084813418 tok/s` reproduction and
before the next direct-egress experiment.

## Identity

- upstream project: `ggml-org/llama.cpp`;
- upstream tag: `b9769`;
- base commit: `c926ad09857517978575d6a74d225b463f7417a0`;
- encoded artifact SHA-256:
  `9cdb1b03a173489e295cc95ac35f66afb40cac96c4c8b5ffbd99f938ddc0a87c`;
- decoded patch SHA-256:
  `2dab9dce3d6a41cba8edad559eb754088c6f5ca1de6531f408c069e45b7f727a`;
- decoded patch shape: 36 files, 13,546 insertions, 856 deletions;
- journal source:
  `../../experiments/gemma4-26b-a4b-q8-b70/sweeps/20260701-direct-sampled-egress-negative.md`.

The decoded bytes are identical to the preserved pre-edit snapshot at
`source-snapshots/20260701-direct-sampled-egress-preedit-source.patch`.

## Verification

On 2026-08-22 the aggregate was decoded, hash-checked, and applied to a fresh
checkout of `b9769`. Both `git apply --check` and `git diff --check` passed.
See `record-source-verification-20260822.json` for the machine-readable receipt.

Use the fail-closed restoration/build helper from the reproduction packet:

```bash
SOURCE_DIR=/path/to/new/llama.cpp-gemma4-record \
  ../../repro/gemma4-26b-a4b-q8-b70-125tps-20260701/restore-and-build.sh
```

## Important scope

This is an exact aggregate source snapshot, not a hand-pruned collection of
only positive hunks. It includes default-off research and diagnostic paths
that coexisted in the record checkout. The record recipe enables only the
documented accepted flags; enabling other flags does not reproduce the record.

The historical `llama-server` binary was not retained with a byte hash. A new
build from this source is therefore a source reconstruction, not a claim of
binary identity. It must pass the target-verified canary and cold-suite gates
before a result is compared or published.
