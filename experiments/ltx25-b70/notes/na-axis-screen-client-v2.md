# Packet10 decoder client successor

2026-09-14. Prepared and checked
[`run-na-axis-screen-v2.py`](../scripts/run-na-axis-screen-v2.py) for corrected
packet10, preserving the original09 client and receipt validator byte-for-byte.
Packet09 refused its private decoder node before installing the router or
executing clips: its node pinned upstream `sd.py`, while the inherited packet
contains the existing CLIP small-state option propagation. VAE arithmetic did
not differ. Packet10 fixes that node dependency pin and improves error reporting.

The successor pins packet10 manifest
`d6ec6c63869d30dbe009708095f53811372e228becf16b7475ad30d11213fe6a`,
requires schema `ltx.na-axis-runtime-packet.v2`, and requires corrected node
`ffd7549d29828a11f336f07873f63a407df7722328df519f2bec3514964ad32b`.
The generated packet checker recomputes all seven declared-versus-actual source
hash edges at every packet verification. The client additionally requires its
returned closure receipt to match the actual source hashes it sees. It rejects
missing dependencies, the old `sd.py` pin, old node identity, and any source-only
receipt that claims successful runtime registration. Failed09 provenance is
bound to its manifest and preserved startup-failure JSON/log in packet10.

The11-request schedule, original transformer dispatch, graph changes, object-info
admission, decoder geometry/owner/oracle gates, retention and failure handling
are unchanged. The successor tests compare the corresponding execution-function
ASTs against09 and verify the old client and validator hashes. There is no
retry, restart, fault bypass, or automatic geometry expansion in this change.
See the original [client contract](na-axis-screen-client-01.md) for details.

Validation:16 stdlib tests passed, including the prior14 tests and successor
source-closure/provenance/unchanged-execution checks. The final packet10 offline
`--check-only` also passed. No endpoint, Torch import, native request, GPU work,
profiler action or server operation occurred during this client preparation.

- [Tests](../scripts/test-na-axis-screen-v2-stdlib.py)
- [Structured test receipt](../data/na-axis-screen-v2-stdlib-01.json)
- [Test log](../data/na-axis-screen-v2-stdlib-01.log)
- [Offline packet check](../data/na-axis-screen-v2-check-only-01.json)
- [Exact client delta](../patches/na-axis-screen-client-v2.patch)

Final client SHA256:
`28fd569ab0acecb10a9b59821a707eb917d80bb013bdb973d046a8e6ad074988`.
Unchanged validator SHA256:
`ac11e8fc95275660d76336cafd892a6ec67e0c4f68b0208f5752a328b254274c`.

These checks qualify source consistency and client validation. Native node
registration, decoder full-clip parity and performance remain separate gates
owned by the root orchestrator.
