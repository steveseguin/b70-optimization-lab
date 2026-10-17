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

The four approximately 1.2 MB M2 expected/actual files retain independent GNU
and Intel results, including nonfinite and differing/invalid-route cases. Their
exact original bytes are required by the seal; regenerate with batch_cpu_gate.py.
The serial milestone receipts are historical and bind commit 5c22d7374; current
source changes intentionally invalidate their launch identity. Serial binaries
remain locally as build/{gnu-host,device}/serial-own-rt-iq3. The final all-M1 seal
uses the current pipelined binary and is the supported fallback for new screens.
