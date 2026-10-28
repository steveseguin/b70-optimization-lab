Isolated native capture-ready candidate; canonical runtime remains unchanged.
Apply from engine/: git apply ../research/pp4-review-2026-10-28/dedicated-gate/capture-candidate/native.patch
Do not apply until coordinator releases active matched control pins.
Native patch: Options flag/parser/admission, optional Owner.run callback after
Sequence.admit, dedicated capture offset768 and status2Reply64/sharedmetadata128,
and actual CPU run_loop regression. Existing CaptureReady128 format reused.
Default unchanged; OP9 and controls never ACK; opt-in OP27 emits exactly one.
Native-receipt.json binds original/candidate sources, patch and CPU outcomes.
CPU overlay: /dev/shm/provider-capture-overlay-20261028 (not GPU-qualified).
Both wire and owner tests pass using taskset8-15 nice19. No DPCPP/model build.
Python transport/planner patch belongs to review_direction; pair it explicitly.
Canonical offline research comparer now validates the captured events strictly,
using dedicated_capture_ready plan flag;19adversarial tests pass. No arbitrary
provider trace events are ignored. Old no-ACK proof source hashes are retained.
