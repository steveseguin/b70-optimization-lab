# Independent request reset review

The kernel-integration reviewer inspected request_reset.hpp, mtp.hpp, rank.hpp,
suite.py and the Engine allocation/bank/cache inventory independently of their
authors. One receipt defect was fixed: draft reset uploads previously happened
after request counters were cleared, charging reset work to the next request.
Counters now clear after all maintenance; scheduling scalars also reset.

Both ranks acknowledge reset only after draining, canonicalizing bank parity,
zeroing every live mutable allocation, restoring constants and clearing target
and draft host state. No allocation is released, so prepared target/draft
captures retain their owner generation and pointer identities. Immutable model
weights and lookup tables remain resident. Shared publications/mailbox bytes
are cleared only after both reset acknowledgements, while ranks await socket
commands. Socket sequence numbers remain monotonically increasing; they are
transport framing, not request state. Sticky target errors are rejected instead
of cleared. A new controller/provider instance resets the Python-side token
history, n-gram history, script cursor and counters for every request.

Source review passes. The separate suite order gate must run three prompts in
two orders for both controllers and none/MTP modes, comparing tokens, all eight
layer-fixture steps, all target buffer/bank hashes and draft temporal hashes.
This review does not claim that pending device request resets have run.

Final CPU order gate passed with resident prepared owners and independent
argument auditing: both controllers, draft none/MTP, three prompts in two
orders. Each request matched all32 retained mini layer fixtures and208 target
state files (214 with draft state, including the hash inventory of every
mutable draft allocation and draft host position/disabled state). Per-order
canonical hashes are in suite-gate-results.json. The independent reviewer
checked the completed ROLLBACK.md inventory against reset code. No remaining
source-review finding; real-model/device reset remains coordinator evidence.
