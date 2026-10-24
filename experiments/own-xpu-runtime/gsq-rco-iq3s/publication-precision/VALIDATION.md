# Publication precision qualification

The exact two-card P195/P165 source audit establishes BF16 recurrent feedback.
The shared BF16-state CPU oracle does not establish reference-F32 fidelity, even
inside its first128-token scope. One-card header-to-object closure remains open.
This update preserves every measured numeric field, record ID, source/binary
identity and original receipt; package manifests remain draft/candidate.

Validation: package catalog and guide validation pass;16 guide tests pass; both
recipe manifests pass local and remote modes while explicitly remaining draft.
All three edited Markdown guides have valid relative links; diff whitespace
checks pass. Offline headless rendered views at390 and1280pixels show the
precision qualification in ordinary page text without clipping. Existing
graph/copy controls and measured values are unchanged. The changed text is
server-rendered and remains present without JavaScript. Screenshots are local
review artifacts under/tmp/own-runtime-precision-* and/tmp/ownrt-tp*-precision-*.
Deployment and cache-busted live verification remain pending.

Follow-up: the first publication CI browser test rejected the expanded visible
catalog status for exceeding700characters. The status was shortened while
retaining historical record scope and the BF16-oracle/FP32-fidelity limitation.
All19 browser tests now pass locally; detailed scopes and all numeric evidence
remain unchanged. No test limit was relaxed.

Cache-busted live checks now confirm the own-runtime precision note, both exact
current package records in the33-package catalog, the two-card rendered page,
and a byte-identical source-audit evidence link. See live-check-1346.json and
live-catalog-1347.json. The full latest-commit CI watch remains separate.
