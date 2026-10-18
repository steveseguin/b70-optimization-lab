# Retention and restoration

Keep the preregistration, complete text-token histogram, source copies, overlay,
CPU receipts, failure logs and proposed queue plan. The build remains below
150,000,000 logical bytes (including symlink targets), with no model copy.

Generated constants under `sources/**/build/` and `rope.bf16`, native objects,
executables and fixture scratch are ignored. `restore_constants.py` restores
only exact hash-bound parent constants. `build_engine.py` rebuilds the native
entries and links the individually hashed frozen parent objects. Follow README
for fixture builds. The 4 MiB RoPE constant is a required input, not duplicated
in Git; its parent source hash is in `constant-pins.json`.

Each full-shape output directory is compressed into its `evidence/shape-*.tar.gz`
only after every member is rehashed against the original. The receipt records
all member counts, source bytes and archive hash; extract to an empty scratch
folder to inspect it. No frozen parent evidence was deleted. Raw model weights,
GPU measurements and a public portable binary release are not part of this CPU
preparation. Source copies use the lab's existing local dependency paths.
