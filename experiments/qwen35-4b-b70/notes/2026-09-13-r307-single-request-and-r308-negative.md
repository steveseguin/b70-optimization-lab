# R307 single-request qualification and R308 negative diagnostic

R307 failed the combined 4B/9B qualification even with one active request,
TP1, MTP depth 3, and `max_num_seqs=1`. R308 instrumentation reproduced the
selected 9B failures and did not fix them. Neither campaign promotes a runtime.

The [captured summary](../data/2026-09-13-r307-r308-negative-qualification/summary.json)
recomputes numeric output-ID equality against the saved same-image MTP0 oracle,
checks exact token-ID prefixes, and verifies the referenced oracle file hashes.
All returned arrays were complete, and cache metadata was zero.

| Stage | Exact requests | Result |
| --- | ---: | --- |
| R307 4B MTP0 oracle capture/repeats | 60/60 | Internal oracle stable |
| R307 4B MTP3 fresh server A | 52/52 | Boundary gate passed |
| R307 4B MTP3 fresh server B | 52/52 | Boundary gate passed |
| R307 9B MTP0 oracle capture/repeats | 60/60 | Internal oracle stable |
| R307 9B MTP3 fresh server A | 42/52 | Qualification failed |
| R308 9B MTP0 selected control | 6/6 | Selected control passed |
| R308 9B MTP3 acceptance trace | 0/6 | Diagnostic reproduced failures |

The ten R307 9B mismatches are two repeats each of L13, L14, L16, L17,
and L14-tail238. Each first difference is the final generated token at absolute
position 255 (zero based): completion indices 242, 241, 239, 238, and 3,
respectively. R308 selected L14, L16, and L14-tail238 twice; all six traced
outputs differ at the same final positions while all six MTP0 controls match.
The second fresh 9B speculative server and strict 9B qualification were never
reached after the nonzero probe exit propagated correctly.

The saved R308 trace contains partial query lengths of three with accepted GPU
counts of four in some calls, and one-token runner steps at computed position
254. These are diagnostic observations, not proof of a root cause. The trace
changes execution and cannot be assumed observation-neutral.

Every captured completed postflight, including R307's failure cleanup, records
two normal devices, two successful compute smokes, both allreduce ranks passing,
and no new fault signatures. The failure is output identity, not an observed
GPU health fault. Full server logs preserve the image-contract checks and trace.
R308's `DONE` marks diagnostic completion, not a quality pass.

Raw receipts are copied byte-for-byte under
[evidence](../data/2026-09-13-r307-r308-negative-qualification/evidence/), with a
[source manifest](../data/2026-09-13-r307-r308-negative-qualification/source-manifest.json).
The [capture script](../data/2026-09-13-r307-r308-negative-qualification/capture.py)
reads only the two named completed source roots and independently recalculates
the comparisons. Successful 4B screening does not erase the failed 9B or earlier
c4 qualification, and these artifacts make no performance or publication claim.
