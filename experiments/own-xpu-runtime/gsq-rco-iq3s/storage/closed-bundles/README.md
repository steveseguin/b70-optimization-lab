# Closed bundle payload archival

Source preparation only. Root operates explicit phases after independent review;
this adapter performs no work on import. Twelve independently audited closed
`state.bundle` payloads from `gsq-state-bundle-a` and `gsq-current-class-a` are
eligible, one file per batch. Total raw bytes: 1,330,459,008. Their indices,
seals, state JSON, draft files, logs and all other paths remain untouched.
Attribution-a is excluded completely pending micro-fixture extraction release
and a separately reviewed, source-bound amendment.

The frozen `closed_baseline_bins.py` Job methods remain byte-identical. Its
private module receives one explicit boundary replacement: `relative()` checks
canonical relative components and membership in the fixed bundle-name allowlist,
in place of the original `.bin` suffix check. Each Job additionally has exactly
one immutable index-bound member and its fixed source root. No arbitrary suffix,
profile, source path or destination can be supplied. Generic inherited receipts
mention `.bin`; the authority's `restore` field and exact tar member name are the
bundle-specific restore instructions.

Each batch uses a 128 MiB archive cap. The largest raw payload125,561,972B plus
8,192B container allowance and1MiB margin is126,618,740B. Admission keeps the
27,000,000,000B root floor plus64MiB reserve, requiring27,201,326,592B free before
archive. USB reserve remains2GiB. Quotas/floors are never lowered on refusal.
Compressed savings are unknown until actual verified archival.

Invoke the fixed script with `--plan`, then root explicitly performs
`--archive --batch N`, `--prune-verified --batch N`,
`--offload-verified --batch N`, and `--release-local-verified --batch N` under
nice19/helper cores8–15,24–31. A later archive requires the preceding local-release
receipt. There is no loop or retry. Existing Job verifies all archive members,
full archive SHA, held source identity/hash before unlink, external filesystem
device and remote readback before removing the NVMe archive. Source trees are
never recursively removed.

To restore, locate the batch receipt's exact original root/member path, verify
archive SHA and member hash/length against the pinned independent index, and
restore only the missing `state.bundle`. Retained seal/index/JSON then permit the
original bundle reader to validate every range again. A seal with archived
payload is intentionally not an immediately readable capture; archive receipts
are the durable restore map. Do not overwrite an existing file without review.

The focused tests exercise actual metadata authorities, fixed counts/quotas and
path rejection. They do not re-run the already reviewed Job filesystem tests,
archive, prune, or read payloads. Evidence recipes and pinned authorities are
retained in `evidence/preparation.json` and `evidence/plan.json`.
