# Qwen3.8 FP8 dynamic MTP6 R12: closed negative

The preregistered MTP6-at-one/MTP1-at-load treatment improved the eligible
single-user result but missed its frozen promotion screen. The replicated
MTP5 profile remains promoted.

| Shape | promoted MTP5 median | MTP6 R12 | frozen gate | decision |
| --- | ---: | ---: | ---: | --- |
| one user, fresh after-TTFT decode | 128.428318 | **130.473213** | 130.996884 | fail |

MTP6 was 1.59% faster than the promoted MTP5 median, but the preregistration
required at least 2%. It missed by 0.524 tok/s, or 0.40% of the gate. The
ordered script therefore stopped before the declared c64 and 512-request
quality stages. Their absence is the specified outcome, not missing evidence,
and no aggregate value is inferred from MTP5 or from the excluded c2 canary.

Before the speed gate, the same service passed c2 output isolation, 7/7
sequential exact cases, 8/8 repeat stability, exact frozen-baseline
comparison, complete token IDs, and zero reported cached tokens. The eligible
single row returned all 128 requested tokens. Its first row is the declared
measurement; the later repeated-prompt rows remain support-only.

After a healthy final endpoint check, both workers reported cleanup complete.
The five-second shutdown grace then expired and vLLM force-killed the
already-idle EngineCore. There was no `EngineDeadError`, failed measured
request, OOM kill, or nonzero container exit. That receipt is preserved.

Raw evidence is in
[`../data/qwen38-fp8-w8a16-mtp6-dynamic-mtp1-20260827-r12/`](../data/qwen38-fp8-w8a16-mtp6-dynamic-mtp1-20260827-r12/),
and the structured decision is
[`../data/2026-08-27-qwen38-fp8-w8a16-mtp6-dynamic-mtp1-r12-summary.json`](../data/2026-08-27-qwen38-fp8-w8a16-mtp6-dynamic-mtp1-r12-summary.json).
This closes the exact MTP6 treatment. It does not change the published MTP5
package, and it does not extrapolate any unmeasured context, concurrency, or
speculative depth.
