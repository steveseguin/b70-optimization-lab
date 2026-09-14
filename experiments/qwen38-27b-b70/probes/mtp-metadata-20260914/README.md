# Native MTP metadata validation and paired endpoint screen

The target remains official FP8 with native MTP1 and unchanged verification,
activation/KV precision, full target vocabulary and accepted arithmetic. The only
candidate moves the unused query-length subtraction into its consumer branch.
This experiment cannot promote a one-process speed observation.

## Fixed execution order

The client is [run-mtp-metadata-client-campaign.py](../../scripts/run-mtp-metadata-client-campaign.py).
Before any request it validates the frozen strict/context references and writes
a hash-bound preregistration with the parent-verified immutable server identity.
The parent owns a dedicated localhost research endpoint on port 18129, admission
against other clients, startup, fault monitoring and any later service decisions.
The client never launches, stops, reloads or retries a server.

1. Require both workers to report the exact refreshed source identity and no
   installed research wrapper. Run the entire fixed strict suite at its natural
   512-token response cap, plus canaries. Require all 12 complete numeric outputs
   to match the frozen R304 reference. This qualifies the refreshed control
   independently of the metadata change.
2. Require two idle metrics samples with both running and waiting counts zero
   before every RPC. Install the same dispatch wrapper on both workers, initially
   selecting the original method. Source and candidate AST hashes must match.
3. Run the native differential gate inside the owning workers. Both ranks must
   pass all 36 scheduler/graph-metadata cases, all 24 fields, alias relationships,
   input preservation and three buffer refills with old returned views retained.
   There is no competing GPU process or modification of model state.
4. Run **control, candidate, control, candidate**, each with the full 12-prompt
   strict suite/canaries and the separately defined prefill continuation profile:
   exactly 512, 2,048 and 16,384 input tokens; prose/code/docs; two repeats;
   128 forced output tokens. Three warmups per arm remain outside timing totals.
   This is 18 measured continuation requests per arm. Every output must match
   the frozen complete numeric token arrays; every request must report cache zero.
5. Check unanimous worker mode, active wrapper and native-gate status before
   each arm, then verify both ranks actually executed the selected path and no
   calls occurred on the other path. Leave wrapped control selected on success.

Each transition stores the raw request/response and idle metric receipts. Strict
comparisons explicitly inspect all parity booleans and the 12/12 count; the
comparison tool's zero exit status alone is insufficient. Any mismatch, request
error, non-idle transition or fault latch halts subsequent requests. Failure
never triggers a recovery RPC or server cycling. The parent must inspect the
retained endpoint state before deciding what follows.

## Interpretation

The five full strict attempts comprise one independent refreshed-base check and
four matched wrapper arms. The latter share process/runtime/wrapper overhead.
The context client retains server prefill timing, HTTP first-token latency and
decode separately, including individual SSE events and histogram snapshots.
The short forced continuations are context screening, not the decode headline.

This campaign checks within-process exact repeats and paired performance. It
cannot supply independent-process confirmation. Metadata remains inactive by
default if its effect is within measured control drift; even a promising result
needs later independent-process qualification before recommendation. Preserve
all controls and negative results. No workload selection or quality relaxation
is permitted.

## Review-only validation

`--check-only` validates local references and emits the complete proposed
preregistration without HTTP or GPU actions. The nine CPU tests in
[test_mtp_metadata_client_campaign.py](../../scripts/test_mtp_metadata_client_campaign.py)
exercise missing/busy/nonfinite idle metrics, duplicate/disagreeing ranks,
partial native coverage, alias/lifetime failures and the comparator's zero-exit
mismatch trap.

The native module's factory creates private metadata fixtures with cache mode
`none`, while the actual unchanged helper functions perform native XPU work.
This covers current-stream metadata lifetime and graph-buffer staging, not
cross-stream safety, graph replay or target token quality; those boundaries stay
explicit in each receipt.
