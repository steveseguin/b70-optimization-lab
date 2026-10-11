# W-B attempt a on card 3: one-input mismatch traced to the link line (2026-10-11 08:38–08:52 UTC)

**Result.** `device_window.py --mode W-B` stopped after 19 s with `v2 host/device hash
mismatch`; no kernel fault, child exited by itself. `exp-v2` matched the host on all
16,384 chunks (2^32 inputs). `log-v2` matched 4,063 chunks and failed on the chunk
starting at `0x3f7c0000`.

**Forensics (coordinator, scratch builds, card 3, each run a few seconds).**

1. Inverting the chunk fingerprint shows exactly one differing input:
   `x = 0x3f7ffffe` (1 − 2^-23); host `0xb4000001`, device `0xb4000000`. The true value
   lies 2^-48 (relative) beyond the rounding midpoint, the hardest case there is.
2. The packet's `census-device` reproduces the same wrong chunk hash on every rerun.
3. The same `census.cpp`, rebuilt in one compile-and-link command with the same flags,
   passes all 32,768 chunks. `-std=gnu++20` versus `-std=c++20` gives byte-identical
   binaries; reference-slab contents, block size and position do not matter.
4. One object file, three links ([link-variants.txt](forensics/link-variants.txt)):
   plain `-fsycl` fails at the same chunk; `-fsycl -fno-fast-math` fails the same way;
   **`-fsycl -foffload-fp32-prec-div -foffload-fp32-prec-sqrt` passes all 2^32 inputs
   for both functions.**

**Cause.** The offload precision options select the device image's backend build
options at link time. `CMakeLists.txt` passed them only to `target_compile_options`,
so the card's divide (and square root) were not correctly rounded. `log-v2` contains
two divisions; `exp-v2` contains none, which is why it passed.

**Scope.** Packets 13, 14 and 15 were linked the same way, without these options at
all. Their device results therefore also contain approximate divide and square root,
in addition to the device's own `exp`/`log`. Their receipts stay as recorded.

**Fix.** Put both options in `target_link_options` of every device target and rerun
W-B. The latch from attempt a is kept here as `device-fault-latch.resolved.json`.
