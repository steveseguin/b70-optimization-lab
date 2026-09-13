# Result: A387 - MTP2 on the exact-serial-GDN line holds both certified pins and is slower than MTP1 at 2K/4K

Preregistration: `2026-09-13-a368-mtp2-on-the-exact-serial-gdn-line-prereg.md` (A368 -> A374 -> A380 -> A387
after three client-pin and one transient failure). Head `6d872457`, stage v2, two speculative tokens (three
verifier rows in the extension's exact serial mode), the A309-lineage certified client, port 20004, supervisor
with the ported xpu-smi bypass. Server healthy at 14:54:48 UTC; the battery ran short rows, quality, exact-2K
and exact-4K, then the client stopped at its exact-4K pin.

| row | MTP2 exact mode (A387) | MTP1 exact mode (A364) | pin |
|---|---|---|---|
| short r1/r2/r3, tok/s after TTFT | 56.73 / 56.73 / 56.70 | 53.38 | - |
| exact-2K r1/r2 (99-interval) | 43.86 / 43.89 | 48.19 | `afffd211…` held, both rows |
| exact-4K r1/r2 (99-interval) | 44.51 / 44.47 | 48.50 | `1d833e5f…` held, both rows |
| quality | 6/7 (inherited code_execution miss) | 6/7 | - |

The client's stop was a stale pin, not a server divergence: the A309 client asserts exact-4K at
`c6193cc6…`, the 2026-09-07 MTP2 screen's own hash from before the reference restoration; the server
produced the current authority's certified `1d833e5f…` on both rows. The A309->A368 generator now repins
that line (as it already repinned the selection verifier).

## Reading

- Lossless: three verifier rows in the extension's exact serial mode reproduce the certified stream at
  2K and 4K, so the exact mode is depth-independent in the verifier row count as designed.
- Speed: below the preregistered bar (48.2 at exact-2K): 43.9 (-9%) at 2K and 44.5 (-8%) at 4K. The
  three-row verify step costs more than the second draft token's acceptance returns at these depths.
  MTP2 is closed on this line as a fixed setting.
- The short rows say the opposite (56.7 vs 53.4, +6%): on short, high-acceptance prompts the third row
  pays. A prompt-class-dependent speculative depth (the 9B lane's dynamic schedule overlay) is the
  shape of lever that could use this; it would need its own identity gate on this lineage and is noted,
  not preregistered.

Evidence: run dir `…mtp2-4352-ple-only-r1-attempt387` (exact-depth-*.json, bench-short-*.json,
quality-current.log).
