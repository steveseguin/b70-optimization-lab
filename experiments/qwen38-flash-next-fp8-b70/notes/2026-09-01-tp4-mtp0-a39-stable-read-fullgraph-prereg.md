# Qwen3.8 Flash-Next FP8 A39 stable-read full-graph preregistration

Date: 2026-09-01
Status: frozen before model load

A39 changes A38 only to fresh attempt 39/port 19711 paths and three consecutive
outer reads of the frozen graph-safe oneCCL digest before the unchanged inner
launcher checks. Every read must match; no retry converts a mismatch into a
pass. The official FP8 model, TP4/EP4 placement, synchronous PLE, compilation
mode NONE, full-decode graph, trace allowlist, full request/quality battery,
authority hashes, and teardown are unchanged.

Frozen files:

- rewriter: `232ef59296c75da4b27c9b7ac1779ea7d89751edacad7743f6f2c035fc4d86d6`;
- launcher: `e3f88d5d4b898e50724ad6cd83986c571fdb7293c23788a26bb29fc50a7aa6f3`;
- client: `d7599824c4a31bf33e1de17e6f99312e3f7f98711f544716ed9614e99ab4dffb`;
- supervisor: `28d5da00cc5331ad0793c584658846f628d9df4cfdfe8597723628465f491a51`;
- generated inner launcher: `761fad8e8f7d7c2977178b21053a5013f293e282656eb6cdf22365c3f8b195cd`;
- reused A37 verifier:
  `be7aef4a7d0c533ae4dde7eef4d89f19af9c7d807782cf50a12e08367490b92a`.

No reboot or per-boot rule applies. Promotion still requires the complete
battery, actual FULL dispatch, and a later trace-off fresh-start repeat.
