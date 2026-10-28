Immutable startup suite and staged prompt authority — isolated prerequisite

Status: source and bounded CPU gate prepared; not enabled in the native runtime.
The live seven-request target-only diagnostic and canonical sources are unchanged.

This composes the existing strict v2 reset descriptor, production ReadOnlyMap,
and production bulk::Prompt. An explicit startup capability authenticates one
bounded, immutable manifest containing exactly 12 fixed prompt paths, token
counts and SHA-256 values, context, max_new=512, model identity and policy identity.
It retains source mappings and refuses identity, geometry, schema or file changes.
No expected output token is accepted by the manifest or transition.

A reset transition selects only the startup-authenticated prompt, validates the
existing owner/sequence/epoch/destination descriptor, then constructs its Prompt
using the next request and epoch. Installation requires a matching actual owner
context after the existing owner reset succeeds. This check proves authority
ordering only: it cannot prove that a caller really reset device state.

Meaningful CPU gate: actual production parser/mapping/Prompt, 12 entries, target
and provider owner binding, wrong sequence, capability, count, hashes, model and
context; authenticated invalid vocabulary; source replacement/mutation; early and
double installation. No model, device or reset execution is involved.

Build from experiments/own-xpu-runtime after CPU release:
  nice -n 19 taskset -c 8-15 g++-13 -O2 -std=c++20 -Iresearch/pp4-review-2026-10-28/dedicated-reset-candidate/immutable-suite-prerequisite/overlay -Iengine/src -Iengine/src/pipeline/ring research/pp4-review-2026-10-28/dedicated-reset-candidate/immutable-suite-prerequisite/test_suite.cpp -lcrypto -o /dev/shm/sc117-dedicated-suite-authority-20261028-r1
  nice -n 19 taskset -c 8-15 /dev/shm/sc117-dedicated-suite-authority-20261028-r1 /dev/shm/sc117-dedicated-suite-authority-fixture-20261028-r1
The fixture requires a fresh nonexistent output directory; it never retries.

Remaining concrete integration: authenticate these startup identities in actual
native arguments; stage replacement Prompt for every target and provider; retain
all-owner quiescence; reset device/private state and all publication slots; only
then clear bulk_used/bulk_closed, install prompts and rotate traces. Existing
Owner::reset bulk guard remains essential until those steps are implemented.
Real cold-byte/allocation receipts and A→B→A qualification precede 12-task use.
No Python lifecycle change, owner-reset implementation, cold-proof claim or
runtime admission is included. candidate.patch is unapplied.
