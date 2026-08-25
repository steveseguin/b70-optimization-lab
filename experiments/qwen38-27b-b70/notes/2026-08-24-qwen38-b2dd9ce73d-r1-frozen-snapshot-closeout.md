# b2dd TP1 r1 frozen-snapshot closeout

Date: 2026-08-24. Classification: **quality-clean measured evidence; original
packet failed incomplete because its continuous remote-upstream freshness rule
stopped after strict A.**

The literal b2dd/1e90 zero-overlay image completed a fresh diagnostic at
`30.282711567525514 tok/s`, above the unchanged `30.2178` diagnostic floor.
It then completed strict replay A at `30.280007107732555 tok/s`. Strict A passed
all seven exact cases, all eight repeat runs with one stable hash, the 8K
needle, all 24 baseline comparisons, and every cache-zero check.

During strict A, remote vLLM main advanced from b2dd to d3e for a frontend-only
Hugging Face token log-redaction change. The measured image, local source,
cache, model, benchmark, and quality inputs did not change. The old policy
nevertheless wrote `stale-before-promotion` and stopped before strict B. Its
fail-closed classification was correct for that preregistration; it is not the
policy for the frozen campaign going forward.

No historical speed value or floor changes. The strict-A median was
`0.0306679327974253 tok/s` below the protected strict floor, so it would not
replace the existing record even without the remote-head transition. It is
still useful measured, quality-clean snapshot evidence for website coverage.

The complete run evidence manifest verifies at
`974d752a9b5930c2430b359c4b93b42c6f535ed0d1168a2bd9699aea8546ad8d`.
The structured closeout is
[`2026-08-24-qwen38-b2dd9ce73d-r1-frozen-snapshot-closeout.json`](../data/2026-08-24-qwen38-b2dd9ce73d-r1-frozen-snapshot-closeout.json).

Forward policy: b2dd/1e90 is the stable campaign snapshot. Engine identity is
exact and immutable at launch; later remote-only upstream changes are logged
but do not invalidate an active TP/context/MTP campaign. Upstream refresh and
patch forward-porting are a separate scheduled lane.
