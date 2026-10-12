# Independent packet38 draft-baseline review

Scope: read-only review of `draft_baseline.py`, `capacity_draft_gate.py`,
`seal_context.py`, packet44 dump geometry, and the actual packet38 source
receipts and row85–93 files. No model or device binary executed. This is a
reference-provenance review, not a packet44 draft arithmetic pass.

The full 63 original files were hashed independently against
packet38 `build-receipt.json` / `draft_capture_fixture_sha256`.
Every hash matched. Every archived full-file byte sequence matched its
original file, and all three compressed source receipts embedded in the
baseline JSON matched the actual packet38 originals. The frozen capture
binary is `a9a4af196369a0050a4e0f72db840035dd078bace1237f153f1da3670bc75ecb`.
It differs from packet38's later final runtime binary; the baseline records
the historical executed identity rather than claiming a new execution.

For row j, the completed position is j+1. QSA append writes token-major
contiguous rows: 512 BF16 key elements and 512 value elements (1024 bytes each),
128 BF16 raw-index elements (256 bytes), and 128 BF16 pooled elements per
completed group of four positions. Therefore the valid prefix lengths are
`(j+1)*1024` for keys/values, `(j+1)*256` for raw index, and
`floor((j+1)/4)*256` for pooled index. Position is a full 4-byte little-endian
integer. The 5120-byte final mix and 496640-byte logits are kept in full.
At row 85 (position 86), this is 88064/88064/22016/5376 bytes for the four cache
files; at row 93 (position 94), it is 96256/96256/24064/5888. Cropping removes only
unpopulated capacity allocation tails. It does not reorder or change a value.
`kernels.hpp` pool writes and `mtp.hpp::dump` use this same layout.

The actual packet38 table's first 94 entries were independently checked:
position j, confirmed token `target_rows[j+1].input_token`, and head enabled
exactly for j>=85. The packet44 preparation reconstructs this order. The 87-token
prompt plus 8 generated-token prefix requires 94 draft rows and 95 confirmed
input rows. The nine head-enabled rows 85–93 produce exactly 9*7=63 files.
The last head row is useful additional comparison coverage; it is not an
extra accepted target token.

The baseline loader verifies full file hashes before deriving valid-prefix
hashes. Membership constraints plus 63 unique paths force complete coverage of
the nine permitted rows and seven permitted filenames. The gate compares
packet44 GNU valid-prefix row hashes directly to frozen packet38 hashes at
all three capacities, then requires identical icpx fixture hashes and a second
explicit baseline comparison. The seal re-hashes retained GNU files and binds
both compiler binaries and the frozen oracle hash. Capacity-sized final-state
files are compared between compilers at the same capacity, not falsely against
a differently sized packet38 final state.

Both receipt-link hardening findings are resolved. Read-only source review
confirmed these assertions after the parent applied the fixes:

- `draft_baseline.py:24` and `:53` require the source/embedded capture-run
  `table_sha256` to equal the corresponding capture-input table hash during
  both preparation and loading. This explicitly binds the captured execution
  to the frozen input table.
- `seal_context.py:210` repeats the runner's check that packet44
  `source_capture_receipt_sha256` equals the frozen embedded packet38 capture
  input receipt hash. Final sealing now independently verifies this link.

The parent reported successful baseline verification after these fixes. This
review verified their source placement and data flow without rerunning numerical
jobs. No unresolved finding remains in this review's prefix-cropping and proof
binding scope.

The review did not change runtime, arithmetic, pipeline or active-gate source.
The six packet44 draft executions and physical device qualification remain
separate gates. The frozen baseline JSON and full raw-byte archive ship in
packet44. Normal
CPU reproduction verifies them with `draft_baseline.py` before running the
baseline-dependent draft gate. `draft_baseline.py --prepare` is optional
regeneration from retained packet38 files, not a normal reproduction dependency.
