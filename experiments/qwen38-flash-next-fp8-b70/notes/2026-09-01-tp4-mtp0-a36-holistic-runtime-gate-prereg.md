# Qwen3.8 Flash-Next FP8 A36 holistic runtime-gate preregistration

Date: 2026-09-01
Status: frozen before model load

A36 retains A35's complete inference and quality identity on fresh attempt 36,
port 19708, and dependent no-clobber paths. Its sole behavioral change is the
runtime evidence rule:

- every collective process must still map only the exact public libccl and its
  digest must match;
- exact public libccl and oneCCL-kernel files are hashed before verification;
- server configuration, completed all-rank graph capture, and actual size-1
  FULL dispatch remain mandatory;
- any retained `LD_PRELOAD`, `CCL_KERNEL_PATH`, 4096-byte threshold, or graph
  selector that contradicts the frozen identity is rejected;
- absence of a launch-only environment string after subprocess exec is not a
  failure once the stronger mapped/artifact/configuration checks pass.

The A36 verifier SHA-binds the A34 verifier, which SHA-binds A33. Model,
placement, graph, oneCCL, scheduler, request battery, exact hashes, teardown,
and promotion rules are unchanged. No reboot or per-boot rule exists.

## Frozen files

- successor rewriter: `9de1393fe33bc618d2965e1f0f346f1a44565c2aefde6613ab6574822fb68d69`;
- runtime verifier: `256de72996103f284635c7402ceaa3d41ac8af877aabe773a1af10a84f09ae16`;
- verifier tests: `76c209f3ba87aa1305c0348aa6afb47ab9703737d4f9cbcc9751d8e0c6cf9a44`;
- launcher: `ce86f0f784b505d7ce123cc4f38a7ccb0cb812cc17387ed87ceb8f0fd6145286`;
- client: `1949bbc71a62847525156d05f73851a3c9b4dab058bc7b4931e2a3dba8604b5f`;
- supervisor: `5d9a2a142aad06b81081ccae4bb63f5676c2fa0e8aca879fd0d7eef78b2aad3a`;
- generated inner launcher: `770fd21fab94a38481b2cf0c9372539e911eab6b07c38e968586655fd6f70f9b`.
