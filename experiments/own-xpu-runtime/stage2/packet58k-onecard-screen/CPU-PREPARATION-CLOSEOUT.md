# CPU preparation closeout: packet58k

Question: can the 58j one-card kernel port be screened in a realistic host gap
without three complete seven-window queues?

Identity: copied sealed 58j native binaries and production/port selections;
card 0, all 48 target layers, unchanged IQ3 packet49 arithmetic, full BF16 KV,
no draft. Native binaries are byte-identical to the parent. Parent source,
byte-gate and startup-gate evidence is retained and hash-checked, not rerun.

Outcome: prepared three proposed jobs with one full-model launch apiece.
Two bounded K1 fixtures precede each load. All twelve prompts run at 128
output tokens and every token must match the original oracle. Plan 33–39
minutes including drain gaps, with 118.31 GB available-memory admission.
The build is 39,526,592 bytes. All 76 CPU tests and three temporary queue
plans pass. No GPU, service, live queue, host setting or frozen packet changed.

Useful mechanisms: the original K1-selected misses and refusal/drain path,
whole-host lane admission, card mask and complete post-load memory census;
the native persistent suite already supports exactly the screen needed.
No new native kernel or compilation was necessary.

Limitations: planned wall time and memory bound are not new measurements.
Device quality/speed remain pending. One port launch cannot establish a speed
verdict, and no retained layer-byte or fresh-port-repeat gate runs here. The
screen never qualifies a submission. Full 58j chain work remains separate.

Evidence: [CPU receipt](evidence/python-cpu-gates.json),
[queue plans](evidence/queue-plans.json), [native/source seal](build-receipt.json),
[parent snapshot](parent-build-receipt.json), [copied inputs](copy-manifest.json),
[commands and decision policy](README.md).

Revisit after the coordinator runs the complete bracket in a whole-host gap.
Only an exact candidate beating both stable controls and the saved record
qualifies for consideration of the fresh 58j chain. A loss is recorded once;
no alternative choice or retry is launched automatically.
