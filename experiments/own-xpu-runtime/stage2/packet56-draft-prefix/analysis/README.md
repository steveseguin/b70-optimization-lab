# Draft time: retained receipts and conditional projection

CPU-only read of packet45 SPEED6 and packet49c receipts. No model weights or
devices were opened. [Reproducer](draft_budget.py) records hashes of all 36
request receipts and the K2 summary in [the result](draft-budget.json).
These benchmark timing receipts do not select the prefix. N=91392 was fixed
separately from independent repository text before this projection.

| Retained window | Draft wall median | Draft command median, positions ≥100 |
| --- | ---: | ---: |
| packet45 SPEED6 | 2.766610 ms | 2.808168 ms |
| packet49c WS128 | 2.775889 ms | 2.816540 ms |
| packet49c WS128x (instrumented exactness companion) | 2.775532 ms | 2.817076 ms |

Each wall row has 1,524 hit/miss-labeled draft observations; each command row
has 1,186 observations. The first excludes prefill; the second is an enclosing
rank command and uses the existing position≥100 steady subset. Their different
scopes must not be subtracted to infer an exact control overhead.

Packet49c K2's same selected `p33.dense.segment` head measures 1.416771 ms
repeated-buffer and 1.418021 ms rotated-buffer; the selected argmax proxy is
0.020624 ms. Each is the median of 200 operator repetitions. Head plus argmax
is therefore a **1.438645 ms proxy, 51.83% of draft wall time**. The remaining
1.337244 ms is a subtraction across scopes, covering the draft layer, merge,
final normalization/mix and overhead; it is not a directly measured layer time.
All four retained packet49c KD `sites`/`timings` gzip files decompress to zero
bytes; draft GPU timing is deferred and null in the suite receipts. A precise
production head-versus-layer profile cannot be recovered from these receipts.
The roughly-half premise is supported by the operator proxy, not proved by an
isolated production draft profile. The coordinator's prefix-head window must
measure the actual reduction before any speed claim.

The expanded Q6 head has 248,320 rows, each with a 3,380-byte stride. Its
839.3216 MB allocation includes trailing metadata; the fast lane reads 3,200
code/scale bytes per row, or **794.624 MB**, within the draft's 1,037.289472 MB
unique weight traffic. This distinction is already derived in
[the roofline note](../../../../../notes/2026-10-15-p45-roofline-and-structural-levers.md).
Prefixing changes addressed row count, not stride, allocation or kernel arithmetic.

With fixed N=91,392 and independent-text outside fraction 95/19,477, linear
head scaling predicts 0.896131 ms less D. No argmax saving is credited. Using
the measured hit/miss medians 19.163498/33.201684 ms and acceptance median
0.79133858 in `hit=D+max(S,B)`, `miss=max(D,R+A)+max(S,B)`, the projected hit
is **18.267367 ms** and miss remains **33.201684 ms** because rollback/redo
still exceeds D. The resulting simple weighted rate is **46.606–46.765 tok/s**,
versus its own weighted baseline 45.263767 tok/s (**2.97–3.32%**).

The low end assigns every outside-prefix occurrence to a previously accepted
proposal; the high end loses none. An independence illustration gives
46.639124 tok/s. These are conditional planning estimates, not measurements,
not confidence intervals, and not the class-balanced record metric. Calibration
text frequency is not a measured generated-token distribution or acceptance
rate. In-prefix misses can become hits, but receive no credit. Only the real
full chain establishes acceptance and end-to-end timing for this prefix.

Reproduce after N is sealed:

```sh
nice -n 19 taskset -c 4-15,20-31 python3 -B \
  experiments/own-xpu-runtime/stage2/packet56-draft-prefix/analysis/draft_budget.py
```
