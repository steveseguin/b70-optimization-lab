# W-A GNU host-twin preparation closed (CPU only)

<!-- campaign-closeout -->

Question: can GNU native math supply the unchanged Intel W-A host twin?
Identity: packet17 W-A elementary census, CPU-only preparation on October 11.

The first reference preparation used GNU with -mfma. Full-slab CPU readback
against Intel found a finite expf mismatch: file native-exhaustive-0.bin,
chunk start 3190030336, offset 262143, input 0xbe27ffff, GNU 0x3f5943ae,
Intel 0x3f5943af. This is a host-library/code-generation difference, not an
accepted reference change. No device ran. No seal was issued for those files.

The original W-A host twin was compiled by Intel without -mfma. Both CPU-only
generator and verifier now match those host flags (HOST_ONLY removes device
code and device libraries). The GNU directory, binary, identity and log remain
in ignored build/wa-gnu-reference-diagnostic/ as failed-preparation evidence.
W-B's v2 exhaustive hashes and CPU model oracle are unchanged and reused.

The replacement W-A CPU pass must complete full fingerprint readback and
host endpoint checks before sealing. Do not use GNU native elementary values
as a substitute for this packet's Intel host twin.

The [preservation manifest](wa-gnu-reference-diagnostic.json) records every
archived file hash. Revisit only with a separately declared reference identity;
never silently replace the original Intel twin with GNU native library results.

Read-only object/symbol review confirmed that the census device program's host
code and both corrected Intel CPU helpers reference the same scalar math
functions and contain the same Intel expf implementation family. Both helpers
have no SYCL dependency. The finite input above is now a volatile-input canary
in the CPU verifier, checked before later long precomputations. This supports
the compiler correction; it does not replace the full slab readback.
