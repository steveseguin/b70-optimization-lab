# Decoder axis-cache packet09 prepared

Previous goal turn made progress: a retained native profile exposed mask
construction, the invocation-local cache passed23 CPU groups, scoped routing
passed11 actual CPU dispatcher groups, and private C++ operators passed119 CPU
comparisons. Native video speed remains unqualified for all these candidates.

This successor adds the private `LTXNAAxisDecode` node, whose9 CPU integration
groups use the original extracted VAEDecode class and actual Kitchen custom op.
Nested latent handling, output reshape, owner/config identity, original/cache/
original output equality, exclusive receipts, failure cleanup and sticky failure
are covered. CPU tests explicitly block device access. Root reviewed source and
tests; actual native startup/shape coverage and four-output parity remain pending.

Packet `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-na-axis-09`
has manifest SHA256
`a53e06ae5bd1be8931eff11d4e9112b850912147b37fcabf1bda064b12f419ed`.
It retains all packet08 numerical files, launch code and old graphs unchanged.
The only modified inherited file is the identity checker, whose old source and
all ancestry gates are retained. Three new helper sources and one custom-node
copy implement startup-only routing; the complete candidate source is extracted,
never imported with its custom-op decorators. Installed Kitchen files are
hash-checked, not edited. Two new graphs change only decode node374. Transformer
guider edges remain direct original420 outputs; no compiler gate is present.

Builder `scripts/prepare-na-axis-runtime.py` SHA256
`2201ffd44862073b1fa76e704b6de33b9d3ae2257626c222cdbfbd022798dd44`
passed source-only checks, sealed1287 files, and verified the sealed result.
The unchanged launcher's check-only path passed and whitelists the new node.
[Manifest, delta and check evidence](../data/na-axis-runtime-09/summary.json).
Independent source review found no blocking integration issue. Comfy can
continue after a failed custom-node import, so actual startup admission must
also verify `LTXNAAxisDecode` in object_info before requests.

Planned native screen: two bare boat controls for cold/warm setup, then
original/cache/original triples for boat42, marble17 and bird123. First scoped
original must match the configuration-derived complete ordered NA call sequence;
all subsequent calls retain that sequence, model/component owners, sampling,
seed, resolution and precision. Every clip compares all four raw tensors to
its independent original reference. Failure preserves evidence and halts the
campaign without restart, retry, graph widening or restoration requests.
This preparation performed no native request or application reload.

The independent C++ tiny-block CPU compilation probe detected unexpected XPU
initialization after the first Python-boundary compiled call and halted before
any C++ compiled call. Its failure is preserved separately. Root observed the
original server as sole render-device owner, empty queue, no fault latch and no
kernel entries since16:07:27UTC. Absence of fault evidence does not establish
that the probe performed no incidental accelerator activity; its exact trigger
needs a guarded isolated source diagnostic. It is excluded from this packet.
