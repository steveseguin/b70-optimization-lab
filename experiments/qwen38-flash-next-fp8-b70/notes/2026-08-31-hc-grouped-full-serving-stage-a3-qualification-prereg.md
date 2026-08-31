# Qwen3.8 Flash-Next grouped serving stage A3 qualification preregistration

Date: 2026-08-31
Status: frozen after A2 procedural preflight exit, before device work

A3 is the exact recovery successor to the A2 qualification. The candidate
18-file serving package, vLLM/kernel commits, accepted comparison package,
model revision, M1 configuration, device tests, retained output hashes,
interpretations, and promotion boundary are unchanged from the
[A2 preregistration](2026-08-31-hc-grouped-full-serving-stage-a2-qualification-prereg.md).

Exactly two derived lines change:

1. `refuse_render_owners` explicitly returns success after checking every
   process descriptor and finding no render-node owner;
2. evidence is written to the fresh no-clobber directory
   `grouped-serving-stage-eeee7d6-a2-qualification-a3`.

The tracked A2 supervisor is authenticated at
`870529a3e9c37599f77f38460795a2651e9a3ff4701c1a46d7dac73f8b8152a2`.
The derived A3 source is authenticated at
`c24f66abe2c3b5fb997119d295ea6455bc531d1ce5a63a068001179358f8ae15`;
the A3 wrapper itself is
`9b3f618b1912589ce44063ea867d1c8e12521ee7e517af4a519de24d049a88f6`.
Syntax, normalized self-identity, derived-source identity, static identity,
stage closure, and validation-only/no-evidence behavior must pass before the
attended qualification. A3 still performs no server launch, full checkpoint
load, throughput measurement, reboot, or full-load boot-marker write. A full
pass authorizes only preparation of the separate A30 endpoint candidate.

