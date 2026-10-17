# Retention and rebuild

Keep source copies, parent hashes, all four selection seals, fixture receipts,
build commands, queue plans and negative history. Binaries, object links and
checked-source mirrors remain in ignored `build/`; no model weights are
tracked. Selected binaries and expected/actual fixture bytes are hardlinks
into that build, retained locally for coordinator execution.

GNU/Intel CPU checks are recreated by `cpu_gate.py`; `build_engine.py` uses
packet70's actual packet65 object provenance and recompiles the changed units
serially. Its receipt verifies every reused object and source before linking.
It is an incremental local build, not a standalone clean-host package. Do not
clean packet65's retained build before archiving/restoring those dependencies.
`build_microbench.py` compiles the optional diagnostic. Existing receipts and
seals are immutable: preserve them before making any future changed build and
prepare a new identity. This packet has no public-release reproducibility claim.

The packet build is approximately 125 MB logical; all compiler child RSS
remained below 1 GB, with an 8 GiB address-space hard cap. No large model payload
read, GPU execution, filesystem cleanup, host-setting change or service ran.

The copied 4,194,304-byte `rope.bf16` is deliberately retained: exact rotary
constants are part of the arithmetic identity consumed by `rope.hpp` and the
compiled engine. Restore from packet70's same file or this packet's committed
blob, then verify its SHA256 against `parent-source-manifest.json`. Its
duplicate content is required by the frozen self-contained source copy; it is
not a cache and must not be removed as build cleanup.
