# Public result synchronization — September 13, 2026

The homepage and discovery metadata lagged result packets. This pass updates
existing measured claims; it launches no GPU workload and changes no service.

## Promoted display changes

- Qwen3.5 4B/9B W4A16 TP1 MTP3: use the R294b 67,248-row shortlist strict
  pair centers, 191.72757360955967 and 124.0842546855242 tok/s. Values, samples
  and TTFT were read directly from each `20260912-slu67k-strict-result.json`.
  Current R304 revalidation remains a distinct runtime identity.
- Qwen3.8 27B INT4 TP2 MTP4: R299 shortlist pair center
  117.5280834152335; R304 TP1 MTP4 pair center 81.1630632580305, displayed
  **81.16**, rather than selecting the faster repeat rounded to 81.17.
  Both come from the graph-capture result ledger's typed `rates` arrays.
- Added R304 two-card 4B/9B shortlist strict results: pair centers 245.83
  and 177.28, from the R304 summary's TP2 strict pairs. Their missing
  context and concurrency cells stay empty rather than borrowing another run.
- Added the already-qualified official-FP8 27B MTP5 profile, 86.18172184524545.
- 4B/9B no-speculation high-capacity results use repeat-qualified R293 c128:
  2520.0 and 1955.3, four passes and 512/512 exact. Each new curve is a separate
  CLASSPAD=1 profile, not the CLASSPAD=0 MTP3 shortlist setup. R304 warm-only
  summaries (2522/1960) are not substituted for the repeat-qualified evidence.
- Added R299 and R304 INT4 27B HTTP profiles directly from the two-pass ladder
  arrays. A point is eligible only if both passes match every sequential
  oracle output; the graph shows the warm-pass rate. TP1 MTP4 ends at c8;
  TP2 R304 MTP4 excludes c4 and c16 after mismatches. No interpolation.
- Homepage Flash-Next 34.50/46.85 and 32K 32.67/44.06 were already current.
  Retained other catalog headlines and explicitly pending entries. Added
  Flash-Next to the lower summary and synchronized its stale README summary.
- Removed the withdrawn output-changing 27B MTP5 row from homepage discovery,
  and the strict-failed Qwen3.6 27B 98.77 row from the lab-qualified table.
  Historical evidence remains in the result ledgers.
- Corrected the lower table's 9B INT4 two-card cell, which had copied the
  FP8 147.8 result. Added the missing 4B summary; rebased ratebar widths.

Package/catalog/family pages, README headline generation, recipes' current
pointers and the performance index now agree. Historical profile curves and
record image identities are preserved. Family heroes explicitly show a named
repeat and disclose the pair; package/homepage records show pair centers.
No starter/clean-host certification was upgraded.

## Evidence integrity and validation

The publication manifest's graph-result hash was stale before this change.
The prior bound SHA-256 `52a9b67d…becde5` was recovered from commit
`22bcbf85086f17c410025da15c8a84147e42fb88`. Every pre-existing JSON key and value
is unchanged. Only eight top-level result records were appended: R295, R296,
R297, R298, R299, R300 and the two R304 topologies. The manifest now binds the
reviewed full ledger `f1f0b12f…1bf256`; no old evidence was rewritten.

Package and family validators pass. Updated stale test expectations for the
39-guide catalog, existing Flash-Next exact-GDN packet, new curated results,
and ratebar normalization. The combined 100-test publication/model suite and
four catalog UI tests pass. Repository link and manifest checks report zero
missing paths. Chromium at 1440 and 390 px verifies headlines and package
profiles, and JavaScript-disabled rendering retains measurements. A narrow
layout overflow in the new concurrency caption was fixed by wrapping the caption.
Screenshots: `/tmp/neural-home-{1440,390}.png` and
`/tmp/neural-package-{1440,390}.png` (local visual review, not research evidence).

Remote asset validation also passed for the affected INT4 publication manifest;
no published binary or source-build input was changed.

CI follow-up: the pre-existing FP8 9B Compose packet omitted the shared
launcher’s unconditional CLASSPAD=0 and CLASSPAD_MAXM=512 defaults. Synced
the anchor and both card-count services to those exact values; the classpad
feature stays off and the pinned R276 image/benchmark identity is unchanged.
Container packet checks and their regression suite now pass.
