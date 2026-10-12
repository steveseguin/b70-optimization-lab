# Context capacity: source argument and measured gate

The source path for this CPU oracle is packet17 `oracle.cpp` -> `runtime_main.cpp`
-> the packet3 plan builder -> packet17 `runtime_kernels.cpp` host operation ->
`core_v2.hpp`. All original source hashes are bound in build-receipt.json.

- `runtime_main.cpp:279-295` sets Geometry.context and rebuilds the same layer schedule.
- `packet3/step/plan.hpp:163-171` uses context for keys, values, raw indexer and pooled
  storage extents and the append-pool shape. Head widths and attention budget are unchanged.
- `core_v2.hpp:383-401` writes keys/values/raw at the current position and recomputes
  precisely (position+1)/4 complete pools. Neither capacity nor unused trailing slots
  enters a numerical reduction.
- `core_v2.hpp:402-424` scores only valid complete pools, then includes valid trailing
  positions. The selected-ID vector has the same budget+3 extent at either capacity.
- `core_v2.hpp:425-456` reduces only the selected valid positions in unchanged order.
- `rope.hpp` indexes the same frozen table by position and rotary coordinate, not context.
  Capacity does not regenerate or rescale RoPE. Other operators have unchanged shapes.
- The CPU host adapter uses the same `evaluate` implementation; no capacity-dependent
  device kernel selection or launch geometry is involved.

Consequently, for positions supported by both capacities, 192 -> 256 changes allocation
and unused cache suffixes, not any output arithmetic bit. This is a source conclusion
for this implementation, not a claim about arbitrary runtimes or models.

Measured proof is required before proceeding: the incident oracle at context 256 waits
immediately after generating token 64. The supervisor compares canonical int32 token
bytes, all 64 logit hashes/top-five records, 384 raw BF16 fixtures and eight layer ledgers
against the sealed context-192 incident. Only success releases token 65. The proof is
saved as incident-retrospective/capacity-prefix-proof.json and equality-proof.json.
The measured gate passed before token 65 was released. All twelve completed prompts
also passed comparison against their available 64-token suite results before sealing.
See [final-verification.json](final-verification.json) for the complete recheck.

The old binary hard-codes context 192 and cap <=64. oracle128.patch is the entire
wrapper delta: context 256, cap <=128, retention of steps 97-104 as well as 1-8,
and a supervisor checkpoint wait at token 64. Numerical source and build flags match
the sealed build. The new executable gets a distinct recorded SHA256; it is not claimed
to be the old binary. The executable is built with OWN_RT_HOST_ONLY and readelf confirms
no SYCL, Level Zero, OpenCL or CUDA dependency. No device discovery is run.

Input independence: packet29 prepare.py prepare(out,prompt) reads admitted weights'
metadata, encodes only the rendered prompt, writes identity.tsv, plan.tsv, tokens.txt,
vocab.bin and input.json. It has no generation-cap/context input. Each bundle-reference
and suite manifest pins all five existing files by SHA256. Nothing is copied or changed
in the old suite. Native --input uses tokens.txt; the Python runtime window --input uses
the bundle directory referenced in the manifest.
