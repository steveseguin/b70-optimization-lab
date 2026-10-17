# Retained inputs and evidence

The copied 4 MiB `rope.bf16` is the target's pinned RoPE constant; restore its
exact bytes from packet64 and verify parent-source-manifest.json. The small
expected/actual fixture streams concatenate every real compared plan allocation
and spare bank. They independently retain the CPU byte evidence under the seal.

Build objects, caches and verbose per-request mini-engine states are ignored.
Their receipts and aggregate compared bytes are tracked; rebuild with the
recorded compiler commands and rerun cpu_gate.py in a fresh packet copy. Raw
first-attempt states remain locally under evidence/raw; no old evidence was
removed. Parent source and build identities remain in the manifests/receipts.
