# First class diagnostic: storage-accounting refusal

Class-a completed its excluded8-output warmup, then refused before the measured
prompt. The guard reused the whole-run828,545,228B forecast after already-written
captures had consumed space. The original source, plan, test evidence and failed
run remain unchanged. Warmup timings are not used as the requested diagnostic.

[Metadata closure review](evidence/device-a/incident-review.json)
`3eab0f771749e30eba51df472d27a17932614812f91a05a60ebc051a1baf159e`
records91.631seconds elapsed, zero measured requests, both positive physical
contacts and drained descriptors. Processes cooperatively exited1; each backend
teardown completed with exit_code0, zero live/inflight and safe_to_exit. No new
kernel fault, vision/queue change or retry occurred. This is a failed run and a
metadata closure review, not a full successful payload audit.

Source review/mocks and root's capacity admission missed the repeated forecast
charge. [Independent diagnosis](evidence/independent-storage-diagnosis.json)
tracks exact target/draft write boundaries: before request2,2*T+D is already
written, leavingT+2*D=241,141,832B plus128MiB metadata and2GiB reserve. Draft
state is written at RESET/FINISH, not by target DUMP. An additive launch-b must
exercise those stateful boundaries from exact-threshold and one-byte-short
capacity. Existing floors, binary, prompts and full-state gates stay unchanged.
