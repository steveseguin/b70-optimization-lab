# Qwen3.8 Flash-Next FP8 A35 path-only successor preregistration

Date: 2026-09-01
Status: frozen before model load

A35 is the path-only successor to the audit-created A34 preflight artifact. It
changes attempt 34 to 35, port 19706 to 19707, and every dependent state, run,
cache, compile, RPC, request-ID, supervisor, and evidence path. It reuses the
exact A34 runtime verifier at SHA-256
`679512374ece0b5ee48d9f48185e2abd24e251fe6dfcceb6eb891e545ef28747`,
which itself SHA-binds A33's base verifier.

All model, source, stage, graph, placement, oneCCL, scheduler, request, quality,
authority-hash, interpretation, teardown, and promotion rules are A34-exact.
No reboot or one-load-per-boot rule is present. A pass remains candidate-only
until a separately started repeat.

## Frozen files

- successor rewriter: `037c4c7e4acdfa8ac621ff55bb114d027669598e7237a8699bd544f9d4f76375`;
- launcher: `8cea3b85a3aa332e46e35eacfdf2096e59a760343fb21d042f819442c4b8a11f`;
- client: `264c27d0fb014f6a7340f392b70df84e7250f04a71f91eab2570965ba4c10bf5`;
- supervisor: `2ff5ecb94d81f884aaa9db09c7fd50600aa83592d8d820b99fc5c61c5ebf93fb`;
- generated inner launcher: `6a21d4a751ff40299e772917447884c822fcff193bee6e23276db51ee2e045ca`.
