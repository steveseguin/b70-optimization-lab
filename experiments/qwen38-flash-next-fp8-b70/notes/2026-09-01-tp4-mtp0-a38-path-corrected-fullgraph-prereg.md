# Qwen3.8 Flash-Next FP8 A38 path-corrected full-graph preregistration

Date: 2026-09-01
Status: frozen before model load

A38 is the fresh path-only successor to A37. It changes attempt 37/port 19709
to attempt 38/port 19710 across supervisor, client, run, cache, compile, RPC,
trace, and evidence identities, and fixes the inner server launch from the
incorrect `ATTEMPT=36` to `ATTEMPT=38`. All model, source, staged runtime,
placement, graph, oneCCL, trace policy, request, quality, authority-hash,
teardown, and interpretation fields are unchanged.

Frozen files:

- rewriter: `1bf85dd7198d709e1925671dbaa507c330ce5f353e748a32cb4c3784bf1959a1`;
- launcher: `c4cf7f8e9a5edfd52f6624668503899ca0b60f52acc4ea93f4d153900f0a3915`;
- client: `33a43865033539c699f73ecabdfee41a9bb2ea17e5ad4ffdc0088678d02c5a81`;
- supervisor: `7fcd149ea7d9dc43b2debd1adb5bb571bdad358597e9ca175ee68651c139547e`;
- generated inner launcher: `74413cb6784f47328b923fefd2a7fc523d943140eba2a5fca8161372e86c2c31`;
- reused audited A37 verifier:
  `be7aef4a7d0c533ae4dde7eef4d89f19af9c7d807782cf50a12e08367490b92a`.

No speed receives credit without the complete battery, actual size-1 FULL
dispatch receipt, and later trace-off fresh-start repeat. No reboot or per-boot
rule applies.
