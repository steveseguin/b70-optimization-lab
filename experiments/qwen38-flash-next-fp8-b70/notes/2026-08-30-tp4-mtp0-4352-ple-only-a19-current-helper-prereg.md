# Qwen3.8 Flash-Next FP8 A19 current-helper trace preregistration

Date: 2026-08-30
Status: frozen before GPU launch

A19 is the new-path successor to A18. It changes attempt 18/port 19690 to
attempt 19/port 19691 and accepts quality-helper SHA-256
`268f6de4a3e4353191d4f75c48b6b0f243ca30196fcb4c582e1db2e2935db656`.
Review of `c2d4c525a` confirms the ten added lines are dormant for this client:
the optional argument defaults to `None`, and A19 supplies none. Model,
runtime, placement, selectors, seeds, requests, interpretation, trace, and all
other helper/fixture hashes remain A18-exact.

The A16/A19 149-digest comparison remains the sole diagnostic decision. Timing
receives no credit and ordinary output assertions remain fail-closed. Host
memory and swap must match the fresh condition before the single load. No
protected result changes.

Frozen artifacts:

- launcher wrapper `e93510a3e6b21ec9f0782783653d502ab4c3c7cad98f072f473a849c4b70ce5f`,
  generated source `4226fcdec049ce0601c729438bba0449206919ee67f5d68820cd427d493a7c73`;
- client wrapper `b2fc8181b4877c0c05e0aca9dc52800aec866e44be25054657e107338bd8f5ef`,
  generated source `66799bd475c32c3a10b287bca21970260c6213774a337202fe98eb408b1e7a0a`;
- supervisor wrapper `76be34e4bd6198ae9183c79d458dd09ded9c8071ac5a50214308d29a1938e76b`,
  generated source `2cdd2bad1d80c7fc2b8694f7598fc613414d6b5e5eabd47c1e3bdd24252ce4c5`.
