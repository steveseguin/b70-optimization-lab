# Qwen3.8 Flash-Next FP8 A24 local inner-trace result

Date: 2026-08-30
Status: bounded reliability negative; local-load and same-server stability positive

A24 proved that the active local checkpoint can load and serve without the
583-second external path. All 131 shards loaded in about 84.38 seconds, each
rank reported the expected 31.57 GiB device footprint, the 4,747-token cache
was created, and the endpoint completed the full frozen battery. The host did
not freeze or reset, all four GPUs remained discoverable, and teardown returned
`MemAvailable` to 126576760 KiB with 8289384 KiB swap free.

Quality remained at the inherited accepted boundary: six of seven exact cases
passed, the known code case remained the sole failure, the repeat case was
bit-identical for 16/16 runs, the 4K needle passed, and all reported prompt
cache counts were zero. The three short rows retained the protected output hash
at 5.457624 / 5.529259 / 5.515783 tok/s, median 5.515783 tok/s.

Both exact-4K rows passed transport with the same output hash
`090d980c84ffd0ea743491d39b5618264e9257dbbcc7f5271e40c97b0c7eb3a6`
at 5.394570 / 5.347805 tok/s and 116.758 / 113.871-second TTFT. This is a
same-server stability improvement over A15's two different hashes, but it does
not match the retained authority
`1d833e5f463366223a669aa15495840d1337b173e675a9ea04f00a5ae339d5cc`.
The client therefore failed closed exactly as preregistered. Diagnostic timings
receive no performance credit and no protected result changed.

The rank-0 trace contains 64 ordered records and 171 tensor digests, including
raw/dequantized PLE embedding, projection, gate, convolution input/output, PLE
output, post-PLE, attention, MLP, and later-layer boundaries. A16 and A21 have
only the older 149-digest outer trace, so they cannot identify the first
internal difference. One identically configured fresh-start trace is still
required; comparing its 171 ordered digests to A24 will answer the registered
question directly.

Although the launcher requested rank mode `all`, only the rank-0 trace file was
emitted. The all-rank receipt is therefore not claimed. Rank 0 remains enough
for the planned cross-start comparison because the previously observed A16/A21
divergence was on rank 0, but the reporting discrepancy must remain explicit.

Five Samsung-NVMe PCIe events appeared during local load/warmup: one mixed
status event, one corrected data-link event, and three corrected receive
events. There was no NVMe reset, OOM, GPU fault, or host reboot. This reinforces
the storage-link correlation without proving it caused the earlier resets. Do
not perform another local full load in this boot; use the recovered host only
to freeze the next trace replica, then run it as the first local load after an
explicitly authorized reboot.

Structured result:
[`20260830-tp4-mtp0-4352-ple-only-a24-local-inner-trace.json`](../data/20260830-tp4-mtp0-4352-ple-only-a24-local-inner-trace.json)

