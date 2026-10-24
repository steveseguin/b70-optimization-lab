# Duplicate closed draft-state preservation

The independently audited Q6 engine index contains28 identical4MiB draft key/value
files. Full raw readback on all28 files confirms the recorded identical SHA256.
Keep `gsq-dense-q6-p33-engine-a/prompt-00-none/rank0/draft-final-state/blk.0.qsa.keys.bin`
under the USB result root as the canonical copy. It is protected: future archive
or relocation work must preserve it or explicitly update all restoration mappings.

The helper has separate verification and reviewed release phases. The root-local
durable restore map retains every old path, hash, extent and filesystem metadata.
Release rehashes the canonical file and every duplicate, checks held inode
identities, writes a durable per-file receipt, and only then removes that duplicate.
No target-state evidence, unique draft bytes, JSON metadata or model payload is
removed. Restore by copying the canonical bytes to the recorded original path and
verifying its size/hash before applying retained metadata.

Expected recovery is113,246,208 bytes. Completion remains pending until the actual
release receipt exists. This retains original model evidence without changing
storage reserves or model execution.
