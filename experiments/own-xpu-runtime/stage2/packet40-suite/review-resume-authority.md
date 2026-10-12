# Independent emitted-token authority review after resume

I re-read the current sources after the disk-full resume. I did not rely on the
previous review or execution receipts. No emitted-token authority violation was
found in this snapshot. The accompanying JSON binds this review to the exact
source SHA-256 values. This is source review only; I ran no binary or gate.

Both Python and native controllers emit only the confirmed rank-1 target HALF
result. Draft, script and n-gram predictions are speculative rank-0 inputs. A
hit requires equality with that target result; a miss restores banked recurrent
state, PLE history and position, then recomputes using the target token. Early
EOS rolls back pending speculation. Rank 1 refuses speculative HALF commands.
Native draft publications require the expected position and sequence, valid
flag, clear error and in-range token. Provider suppression cannot emit a token.

Draft nonlinear outputs are checked against the private mutable allocation
set. Matrix outputs, merge storage, attention/control scratch, prepared input
and output-head workspace use private draft allocations. The target output-head
weights and RoPE are shared read inputs. The hidden copy runs from target
streams into draft storage. Embedding lookup never calls target token
preparation or changes target PLE history. Prepared commands retain those same
bindings and their operation argument blocks include the added draft members.

The packet-37 scratch/capture hazard is addressed by retaining draft allocations
under the Engine owner until shutdown. Request reset changes bytes in place;
provider destruction does not release owner allocations. The invalidation test
contains a negative case that releases unrelated draft scratch and rejects the
stale target capture, plus a positive four-reset/provider-view-destruction case.
The latter is a mock ownership test. Actual resident Engine/provider reset and
controller equivalence gates are still necessary; this review does not assert
that their old receipts passed this session.

Suite exactness checking reads emitted tokens and retained fixtures after the
request; it cannot rewrite runtime output from oracle data. The actual mini
controller gate compares tokens, guesses, hit/miss sequences, complete state,
and fixtures for all ternary script patterns through length six and random
long patterns. Parent-run execution and device windows remain separate gates.

Follow-up: I re-read the guarded failure-record paths in pipeline.py, suite.py
and rank.hpp. They preserve token authority while ensuring failed diagnostic
writes cannot bypass cooperative cleanup. Source hashes were refreshed.

I also reviewed request_state_inventory.hpp and the suite raw-state retention
change. Inventory runs at quiescent request boundaries. Both RESET replies
precede retention and shared-mapping clearing. Hash and archive checks precede
raw-state deletion; emitted tokens and retained layer fixtures are unchanged.

Warmup follow-up: the excluded request now uses a synthetic five-token sequence
absent from all admitted prompt spans. Only that request disables EOS termination
to guarantee two target outputs and the draft decode head before measurement;
normal requests retain the original EOS and complete reset path. K2 picks one
class winner across its workloads (`k2_summary.py:268-272`), and prepared dispatch
uses label/op only (`dispatch.hpp:40`, `main.cpp:1074`). Active position cannot
select a new QSA kernel type later. Capture itself does not execute every
candidate; warmup exercises the selected types. Driver compilation/cache-hit
behavior remains a device-window observation. The separate no-rank warmup
regression is implementation evidence, not part of this independent source
review or a runtime/device exactness claim.
