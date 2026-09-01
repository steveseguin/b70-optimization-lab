# Qwen3.8 Flash-Next FP8 A51 memory-floor negative

Date: 2026-09-01
Status: bounded guard-policy negative; zero quality or speed credit

A51 validated and loaded the complete external 131-shard checkpoint on all four
ranks. Loading took `568.58`-`569.01` seconds and consumed the expected
`31.57 GiB` per card. It then initialized the exact 3,456-token KV cache and
entered full-graph capture.

The supervisor stopped the arm during graph capture when `MemAvailable` reached
`31,789,856 KiB`, only `210,144 KiB` below the inherited `32,000,000 KiB`
runtime floor. This was not memory exhaustion: disk-backed swap remained
disabled, memory PSI was `0.00`, I/O PSI was `0.09`, and the host recovered to
more than 124 million KiB after clean teardown. The local NVMe remained within
the preregistered bounds: corrected endpoint count rose from `73` to `98`, the
root-port count stayed zero, and local read sectors stayed below the 4 GiB cap.

No endpoint became healthy and no client request ran, so A51 receives no
quality or performance credit. Its evidence is preserved under:

`/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-fullgraph-mtp0-2304-ple-only-r1-attempt51`

and the corresponding `-supervisor` directory.

The exact successor lowers only the live supervisor floor to
`28,000,000 KiB`. The initial launch floor remains `120,000,000 KiB`; swap-off,
PSI, storage, link, process, listener, and four-B70 gates remain unchanged.
