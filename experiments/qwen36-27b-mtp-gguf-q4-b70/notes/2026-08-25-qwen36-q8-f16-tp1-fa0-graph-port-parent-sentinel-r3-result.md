# Qwen target-Q8/F16 TP1 fa0 graph-port parent sentinel R3 result

State: **failed in the graph-on candidate; cleanup passed**.

R3 repaired the R2 receipt-schema abort and ran both GPU arms. The graph-off
control passed with the same 1,290-byte output and all graph counters at zero.
The graph-on candidate successfully recorded and replayed two distinct graphs.
It did **not** reproduce the original R1 exception about waiting on a queue while
recording.

The third graph required a 78,336-byte Q8 memo buffer after all 320 bounded
pointer-stable slots had been populated by smaller geometries. The repair
correctly aborted instead of resizing or freeing a buffer whose address might
be retained by an executable graph:

```text
persistent SYCL graph Q8 memo exhausted 320 pointer-stable slots for 78336 bytes
```

This is one door forward: pointer-unsafe reuse is gone, and the remaining
failure is the fixed storage bound/geometry policy. The next repair must remain
bounded, retain exact graph-off behavior, and provide enough stable capacity for
all cache-eight graph geometries. The R3 root is immutable. No partial output is
promotable, and no curve, site, speed, quality, record, or protected graph-off
replacement authority was earned.
