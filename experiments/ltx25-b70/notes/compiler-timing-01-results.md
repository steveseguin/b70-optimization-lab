# Retained one-block compiler: paired timing loss

September 14, 2026. All 18 requests passed the original four-output byte oracle,
with no additional compilation or application reload. The same PID 17769 and
qualified block24 candidate were reused for two rounds of restored/compiled/
restored triples across boat, marble and bird. Source, device placement, original
model owner, candidate owner, strict mode and graph coverage remained bound.

For each triple, compare the compiled duration with the arithmetic mean of its
two adjacent restored-control durations. The median compiled-minus-control
preview difference was +99.797ms; compiled was faster in only 2/6 triples. The
median control/compiled ratio was 0.984780. For the two sampler node intervals,
the median difference was +17.977ms and compiled was faster in 1/6 triples. These
node intervals are approximate client-received wall intervals, not synchronized
kernel timings. This is a negative speed screen, not a promoted optimization.

The result preserves the exactness achievement: together with screen04, 27 clips
passed on this same application, including 11 compiled clips. It does not show
that the generated kernels themselves are slower; the current route also adds
lifecycle scans, census and diagnostic receipts. Isolated kernel benefit remains
unmeasured and cannot be inferred by subtracting estimated overhead.

Postflight found the queue empty, the server present, no FAULT latch and no
kernel-fault detector matches. Last dispatch is restored. The compiled candidate
can still be selected in this process; do not reload the application for another
request using its existing modes. No real-time/continuous-stream claim is made.

Evidence: data/compiler-timing-01/ and data/compiler-timing-01-paired-result.json.
Source: scripts/run-compiler-timing-v1.py, SHA
9edfffc72dc0bbd35053aa96bf4dc2853c281f4b251698f1cb0ab523ca6acf41.
Its prior qualification replay and schedule were independently source-reviewed.
The 18-request schedule check passed, including unique names, qualified stages,
and six exact restored/compiled/restored triples. The fixed raw-oracle and
bounded-retention helpers remain unchanged; three campaign previews remain.

Next: reduce demonstrated duplicate validation work, measure with matched
controls and then implement bounded multi-block selection in one sealed runtime.
The separately prepared registry-binding reuse patch retains all validations
and passed the native CPU lifecycle rejection gate; it has no GPU speed result.
