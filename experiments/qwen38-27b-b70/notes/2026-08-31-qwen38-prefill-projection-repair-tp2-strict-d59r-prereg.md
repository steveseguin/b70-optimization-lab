# D59r preregistration: bounded-profile repaired TP2/MTP0

Date: 2026-08-31

D59 loaded both TP ranks and the model without host OOM or GPU reset, then
failed during vLLM's 2,048-token startup profile. TP1 rank 1 reported
`UR_RESULT_ERROR_OUT_OF_RESOURCES` from AutoRound gate/up GEMM. No request was
served. The failure occurred outside the repair branch (`M >= 512`) and is
consistent with the oversized profile shape used by the first local TP2
attempt.

D59r changes only `max-num-batched-tokens` from 2,048 to 256, matching the
bounded local TP2 operating style. Model length remains 2,048 and longer inputs
may be chunk-prefilled. All D59 quality, cache, token-identity, canary, shutdown,
and fault gates remain unchanged. Host memory stays capped at 13 GiB with the
existing 36 GiB memory+swap ceiling. Any further startup failure is captured
with complete container logs and is not retried by silently raising resources.
