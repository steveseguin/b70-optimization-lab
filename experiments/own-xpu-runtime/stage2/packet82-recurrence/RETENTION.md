# Retention and restoration

New build storage is capped below 1 GB; no old files were removed. Ignore build/
and hardlinked compat view binaries. Retain source manifests, commands, compressed
offline assembly, CPU digest receipts, state comparison counts and full-shape
startup receipts in Git. Raw CPU state is compared before SHA256 transcripts are
written. The 20 production NaN cases per compiler have ignored raw snapshots
for auditing cross-compiler payload differences; rerun cpu_gate.py to restore.
No real model weights, secrets or device measurements are in this packet.
Incremental rebuild requires the pinned packet75 objects named in object-identity.json;
this research screen is not a standalone publicly reproducible release.
