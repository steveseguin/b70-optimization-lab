# Qwen3.8 Flash-Next FP8 HC grouped-GEMM N336 preflight negative

Date: 2026-08-31
Status: closed harness-shape negative

The first frozen layer-0/down control completed at `40.17572 us` with one
stable consumed-output hash. The grouped candidate then failed closed before
timing because the Xe2 implementation requires output width `N` to be divisible
by 32, while the preregistered 324-output merge had only been padded to 336.
No candidate timing exists and this attempt has no speed or endpoint credit.

The host and all four B70s remained healthy with about 120 GiB available and
swap unused. No server, full model, reboot, or protected-result change occurred.
The incomplete raw evidence is retained under
`/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/hc-m1-grouped-eeee7d6-seed20260830`;
its exact file hashes are tracked in the
[structured result](../data/20260831-hc-m1-grouped-gemm-n336-preflight-negative.json).

The bounded successor pads the same ordered 324 real outputs with 28 zero rows
to `N=352`, compares only the first 324 outputs, checks `N % 32 == 0` before any
timed call, and uses a new evidence root. The layer-0/layer-47 weights, input,
runtime stage, loader, seed, repeat counts, exactness gates, and interpretation
remain unchanged.
