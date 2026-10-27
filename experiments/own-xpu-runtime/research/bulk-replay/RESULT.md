# Bulk draft replay experiment — rejected

`OWNRT_DRAFT_REPLAY_BULK` attempted to remove one device drain per draft-replay token by reading the existing prefill
token/reverse arrays and issuing a whole 256-row chunk before the final drain. Scalar replay remained the default.

The implementation completed all 256 rows with correct position progression and reverse-row binding, but repeatedly
failed the following request transition with `draft confirmed position sequence`. The first attempt also exposed and
fixed the initial confirmed-position offset, reverse binding, and command-chain fallthrough. Those fixes were
insufficient to produce a passing startup gate. No speed result or exact-output claim is made.

The change was removed from canonical `engine/src`, its service switch was removed, and B24 was restored. A future
attempt needs a minimal driver-level reproduction of the transition before another full build cycle. The validated
prompt-speed win remains B24's independent multi-token GDN preparation, not this replay work.
