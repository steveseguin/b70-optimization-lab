# Qwen3.8 Q64K32 reference-host stage setup

Date: 2026-08-21

Status: **transfer verified; sealing stopped before invocation**.

The structured evidence is
[`../data/2026-08-21-qwen38-q64k32-remote-stage-setup.json`](../data/2026-08-21-qwen38-q64k32-remote-stage-setup.json).
This setup follows the blocked
[`2026-08-21-qwen38-mtp5-m6-fa-q64k32-remote-clock-prereg.md`](2026-08-21-qwen38-mtp5-m6-fa-q64k32-remote-clock-prereg.md).

## Completed bounded setup

On `steve-TURIND8-2L2T`, `/home/steve/b70-optimization-lab` was clean on
`main`, with `HEAD == origin/main == 6d678cccf9519414f6f3a8162f2c3f263364f842`.
An explicit `git fetch origin main` followed by `git merge --ff-only
origin/main` advanced it to clean
`HEAD == origin/main == e63d5e24a351359acfbd8a93c0429732bf7f36ea`.

The exact incoming packet was copied to the fresh private path
`/home/steve/.qwen38-m6-head256-q64k32-remote-transfer.tmp.e63d5e24a`.
It remains unpublished. Its four top-level entries contain 20 runtime files
and 3,439,487,512 logical bytes. Remote recomputation proved:

- candidate graph manifest and aggregate:
  `d662dba3927fac706ff221902f536b67178b6875f66604597a1f2fe98a4defc4`;
- all candidate manifest entries: `sha256sum --quiet -c` pass;
- control graph manifest:
  `47861e8391b6b25dd9c3eb25e25c5939753aa470858b667d5bdf181344db18da`;
- candidate device DSO:
  `01a5b35b5a9c6321b436b137f95403db9e45ce4aabb44257dc7e4f45c84aecf5`;
- control device DSO:
  `604f1b328870f2c41ef1d05c4d6016c34d222033d905877b0f9a2ff0c66b2a0c`.

The canonical incoming, candidate, and control roots were absent under both
the shell `-e` and `-L` tests. No relevant vLLM, llama, Q64 operator, or
`xpu-smi config` process was present.

## Why sealing stopped

The committed preparer at SHA-256
`e20b1f09363b3361e5a90fa868f1a8dffced87b482dc1e9ebb016e9d945a4ea8`
passed its source audit, but review found that its canonical-root precheck
admitted dangling symlinks and ordinary `mv` publication retained a
check-to-publish collision window. The helper was **not** invoked with
`--seal-transferred-stages`; no canonical root was created.

The local follow-up hardens publication with `! -e && ! -L`, absolute
`/usr/bin/mv -T --no-clobber`, post-move source absence, destination
device/inode ownership, inode-scoped cleanup, clean `main == origin/main`, and
adversarial collision/signal tests. It must be independently reviewed,
committed, pushed, and fetched to an exact externally authorized remote HEAD
before setup resumes. The private transfer must be revalidated and published
without overwrite first.

No clock was changed, no GPU/operator/model workload ran, no remote kernel
source was edited or built, and no raw remote evidence file was persisted.
