# Independent CPU suite export and full64 seal review

The draft-runtime reviewer independently read the suite-metrics changes in
`suite_export.py`, `seal.py`, `cpu_campaign.py`, and their focused tests, plus
the unchanged suite oracle checker. No unresolved source issue was found.
The reviewer ran no tests, compilers, native owners, or device code.

The campaign explicitly requests 64 generated tokens, preserving the inherited
three-prompt CPU scope: 192 tokens and 1,152 early layer fixtures. The exporter
can also describe a deliberately shortened diagnostic, but the seal first
requires requested cap64, oracle cap64, prefix_only=false, and
full_oracle_generation=true. The archived summary, each request, and both rank
launch arguments must independently agree with that cap. Forging only the
full-generation flags cannot qualify an eight-token result.

Before checking a requested prefix, the exporter invokes the unchanged checker
on the complete oracle against itself with its manifest entry. That binds the
oracle receipt, result, validation, input bundle, and full fixture inventory.
The exporter then requires exact requested-prefix tokens, the complete early
retention set, exact candidate fixture coverage/hashes, and actual byte equality
for every retained layer fixture. The real checker enforces step and layer
names, 48 layer records per step, shapes, dtype, lengths, and recorded hashes.
The seal independently authenticates the full oracle again and checks the
archived fixture hashes and token stream. Prefix completeness and prompt-set
completeness are reported separately.

Rank teardown precedes export and scratch archival follows successful export;
this change introduces no new asynchronous owner or deletion path. Export
rechecks the qualified Intel binary before and after its work. The seal binds
the archived receipts, launch identities, request caps, warm-up, state evidence,
and qualification plan. Failed or changed evidence cannot become qualification
through a copied passed flag.

The implementation agent's provided receipts pass 27 synthetic export/retention
checks and 10 compiler-selection checks. Their source hashes, including both
test modules, match the files reviewed. These are provided test results, not
executions by this reviewer. They cover full64 admission, diagnostic8 refusal,
truncated/extra/changed tokens, malformed/mismatched launch caps, fixture hash
and byte mismatches, false full-generation flags, wrong compiler/binary
identity, teardown and verified archive behavior. Actual inherited three-prompt
full64 execution remains a separate required gate; this review makes no device
or performance claim.
