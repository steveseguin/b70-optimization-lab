# Qwen3.8 Flash-Next FP8 A45 lossless-2K full-graph preregistration

Date: 2026-09-01
Status: frozen before GPU launch

A45 converts the A44 diagnostic breakthrough into a supervised, trace-bound
qualification arm. It keeps the official FP8 checkpoint, TP4/EP4 MTP0,
synchronous PLE-only UVA placement, public oneCCL/kernel, full-decode-only
size-1 graph, compilation mode NONE, 128 MiB KV cache, short-output authority,
semantic battery, and 16-repeat gate. It uses fresh attempt-45/port-19717 paths
and explicitly exports `TORCH_TRACE` to the exact run-local trace directory.

Because A44 proved that exact 4K generation is not repeatable, A45 narrows the
certified service envelope to max model length 2,304 and changes the long gates
to exact 2K. The full quality suite uses the retained 2K filler setting `2157`
and must report exactly 2,048 prompt tokens with cache zero. Both exact-depth
rows use depth 2,048, capacity 2,304, 128 output tokens, and must match:

- prompt-token authority
  `a173e60e5047c0f080e0ea45680eecbb533d30946cfc2ae0e028c684bf18d1ba`;
- payload authority
  `3aa1bba4d0ade3c07e7cad10bb5ee01245dc194d28dc17359311ece3b4ab6f36`;
- retained eager output authority
  `5fd297f79da317b0741140cccb52fb710f89dfd1444effe9068b806b0300e57e`.

The eager authority came from the same official model revision and exact-depth
fixture but an older vLLM source identity; A45 therefore requires both A45 rows
to match it and one another. Any mismatch is a bounded negative, not evidence
that the authority should be changed.

Frozen tracked hashes:

- rewriter: `89dd542431e45a8c60a3d6f42f746558a01e52313f581cbe4f1ece1b6c03433c`;
- launcher: `952a339c02496f90a2cb1cb48caa1a548ffed4194a705d1925b014ab49eda8d6`;
- generated inner launcher: `0e23faf443d746fcbbe94b66747115b8c4dd28f53d31ee6a7540573fd97a0282`;
- client: `2646653e25e07dba4b846317902ba1eda3570b019d9cf2ff10534e37b64cf67f`;
- supervisor: `d1938ee999b51de2324248d2b449e9c7bbda8160d82ad285c55198f66ea292ca`.

Promotion requires recovery, the accepted semantic boundary, 16/16 repeat,
three protected short hashes, two exact and authority-matching 2K rows, runtime
trace/dispatch verification, and clean supervised teardown. The short speed
must not be promoted if any quality or identity gate fails. No reboot or
per-boot model-load rule applies.
