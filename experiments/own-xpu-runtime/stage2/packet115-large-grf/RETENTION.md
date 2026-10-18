# Packet115 retained evidence

Keep source snapshots, compiler commands, CPU output bytes, failed E5 source,
assembly and all future coordinator receipts. No weights or secrets were copied.

The current register census is exactly the entries named by
`evidence/images.json`. Surplus numbered assembly files from early namespace
and compilation checks are retained diagnostics, not additional qualified
kernels. The first E5 flag-spill failure has its own source and assembly under
`evidence/e5-first/`; the final common epilogue passes the unchanged zero-spill
gate. Compressed CPU bytes are stored once by content hash; every repeated
run retains its own receipt and cases. Decompression is checked by admission.

The build directories are ignored, are local compiler products and together
must stay at most 250,000,000 bytes. Rebuild from the commands and scripts in
this packet. V5 reuses hash-pinned packet103 objects; it is a local lab recipe,
not a public clean-build package. Nothing in this note authorizes removing
parent evidence or build objects.

The 46,080-byte route snapshot contains all 384 preregistered packet100b
vectors. Its original capture manifest and every underlying receipt remain
hash-checked at admission. All actual route, output, timing and model-quality
claims retain their original scope. Synthetic weights/activations in the
micro do not become model measurements.
