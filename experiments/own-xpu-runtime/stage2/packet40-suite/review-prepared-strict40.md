# Prepared-launch structural gate after strict rollback

The inherited gate failed because it still required inline history/token restore
and cache clearing in `rank.hpp::undo`. Strict rollback now delegates exact state
restoration to `SpeculativeImage`; clearing derived host caches is no longer the
correct postcondition. The failed cheap attempt is retained, and the original
failure log plus preceding receipt are archived at
`evidence/prior-prepared-review-failure-1791839048129392326.jsonl.gz`.

The updated gate retains the existing prepared-bank, command identity, owner
generation, per-launch cancellation, publication and hot-path checks. Undo must
drain, reject sticky failure, reverse a completed bank swap, and then restore the
image. Snapshot checks require capture before guessed writes; explicit token,
position and token-history coverage; every plan output; exact host histories,
lookup/routing/layer/FP32 metadata; original bank parity; and live saved FP32
allocations. Copy completion precedes restored host metadata. Committed active
banks and valid QSA prefixes remain outside the rollback image. Private backup
retirement requires resolved speculation and a drained owner.

The focused CPU source/mutation gate passes 29 structural checks and rejects
43 mutations: the original 14 negative cases plus 29 strict-image cases. Mutated
bodies are scoped to the named helper, so a similar check elsewhere cannot hide
a removed guarantee. No runtime binary, model or compiler was executed. This
structural check complements the separately recorded full-state execution gates;
it is not a replacement for token, fixture, allocation-byte or sanitizer proof.
The strict-image implementation's independent review remains attributed to the
cancellation reviewer in `review-p40-strict-rollback.json`.

Only the gate producer and its result changed. The cheap campaign must rerun
against the current producer before final sealing; previous failed ledgers are
not amended or upgraded.
