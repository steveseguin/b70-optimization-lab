# Qwen3.8 Q64K32 reference-host stage setup

Date: 2026-08-21

Status: **canonical stages sealed and independently exact; launch remains
blocked**.

The structured evidence is
[`../data/2026-08-21-qwen38-q64k32-remote-stage-setup.json`](../data/2026-08-21-qwen38-q64k32-remote-stage-setup.json).
This setup follows the still-blocked
[`2026-08-21-qwen38-mtp5-m6-fa-q64k32-remote-clock-prereg.md`](2026-08-21-qwen38-mtp5-m6-fa-q64k32-remote-clock-prereg.md).

## Completed bounded setup

On `steve-TURIND8-2L2T`, `/home/steve/b70-optimization-lab` was clean on
`main`, with
`HEAD == origin/main == e63d5e24a351359acfbd8a93c0429732bf7f36ea`.
An explicit `git fetch origin main` and `git merge --ff-only origin/main`
advanced it to clean
`HEAD == origin/main == aae4f7f867ccc067e4f43869a1e43309767e831d`.
The externally frozen helper SHA-256 was
`feebec0a3b2ee835fcd5519b670e16f2dd9921d2db258226665cc303832bf716`.

The 23-file, 3,439,487,512-byte private packet was revalidated, then published
at `2026-08-21T06:34:12,778818347-04:00` with absolute
`/usr/bin/mv -T --no-clobber`. Its source and destination device/inode were
both `66308:13137856`, and the source was absent under both `-e` and `-L`
after publication. The immutable remote publication receipt is:

- `/home/steve/qwen38-m6-head256-q64k32-remote-transfer-20260821-r1.publish-receipt.txt`;
- mode `0444`;
- SHA-256
  `5830bea643f9e2f40ab8c416ba06e33cf950281c3e54f4377b3402b8a6e1b739`.

The frozen helper was invoked exactly once with
`--seal-transferred-stages`. It returned `0` and sealed at
`2026-08-21T06:37:23,730431843-04:00`. Its immutable remote evidence is:

- stdout log SHA-256
  `346a3de193de20e674c1d7b90ecf3334e14fd46f015d2180435bff81887dac17`;
- stderr log SHA-256
  `d5acfa1f42eb6c820af3f40f93e3ddf8315c0defdc725c4c7b9f255b32695656`;
- seal receipt SHA-256
  `7e0fbf60143007790467d2336080e869404eee65f355f15cffdc29c1e380df5b`,
  mode `0444`.

The receipt paths and the complete structured identity are recorded in the
linked JSON. The helper process ID was not recorded, so this note does not
infer one from a temporary-path suffix.

## Independent final-stage validation

The candidate root
`/home/steve/qwen38-m6-head256-q64k32-attn-override-20260821-r2` has
device/inode `66308:13137891`, 23 regular files total, and exactly 20 runtime
files. The control root
`/home/steve/staged-xpu-commitfix-graphfa-composite-20260820` has device/inode
`66308:13137918` and exactly 20 regular files. In both trees:

- all directories are `0555` and regular files are `0444` or `0555`;
- there are no writable, symlink, or other nonregular nodes;
- all manifest entry checks pass;
- exactly 19 common runtime files are hardlinked across stages;
- the device DSOs use distinct inodes;
- no candidate-stage file aliases the mutable incoming packet.

The independently recomputed identities are:

- candidate graph manifest and aggregate:
  `d662dba3927fac706ff221902f536b67178b6875f66604597a1f2fe98a4defc4`;
- control graph manifest:
  `47861e8391b6b25dd9c3eb25e25c5939753aa470858b667d5bdf181344db18da`;
- candidate device DSO:
  `01a5b35b5a9c6321b436b137f95403db9e45ce4aabb44257dc7e4f45c84aecf5`;
- control device DSO:
  `604f1b328870f2c41ef1d05c4d6016c34d222033d905877b0f9a2ff0c66b2a0c`;
- generated immutable build-input manifest:
  `70f6c6a86098dbf42722b8c601a7b238868ccb4fa23ba9ad0c9f1789083ddb5e`;
- generated strict canonical candidate-stage JSON:
  `31965ea3904cf2081df6e6ce31f93c36b65b66c120e8c3f7a12f9744a2b4b6e3`.

The build-input manifest binds the frozen patch, build helper, candidate DSO,
and candidate graph; all four entry checks pass. The stage JSON rejects
duplicate/nonfinite input and binds schema
`qwen38-mtp5-m6-fa-q64k32-r2-stage-v1`, candidate role, canonical stage,
artifact, and the exact four runtime identities.

## Helper warning and boundary

The helper's stderr is not empty. Plain `rm` encountered the write-protected
candidate-DSO hardlink in the temporary control tree through an interactive
SSH TTY and emitted one prompt.
The following `install` still produced the exact control DSO on a distinct
inode, the helper returned `0`, both final manifests passed, and the
independent full-tree audit above passed. This is therefore classified as a
**setup-helper reproducibility defect**, not evidence of stage corruption.
Do not rerun this setup. A future reconstruction helper should use nonprompting
fail-closed removal and have a noninteractive regression test.
The local successor now uses absolute `rm -f` and has an exact-line PTY
regression; its SHA-256 is
`c3a99abb5bd401b1e6d14ad5576f7493ec7dd9e5b106e3d03892d04dcd9ae6d9`.
That source correction did not recreate or modify the accepted remote stages.

This setup does not authorize the campaign. The preregistered launch,
campaign, and clock-writer gates remain false until separately reviewed and
enabled. The campaign result root remains absent, the remote repo remains
clean at the exact authorized commit, and no relevant vLLM, llama, operator,
or `xpu-smi config` process was present after setup. No clock or XPU setting
was changed; no GPU, qualifier, operator, model, or vLLM workload ran; and no
remote kernel source was edited or built.
