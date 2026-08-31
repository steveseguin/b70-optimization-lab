# Qwen3.8 Flash-Next grouped full-serving stage A2 finalizer result

Date: 2026-08-31
Status: assembly-only pass; qualification pending

A2 consumed the exact successful A1 build closure without configuring or
recompiling. It produced the exclusive 18-file candidate at
`/mnt/fast-ai/qwen38-build/runtime-serving-hcgrouped-eeee7d6-a2`, retained byte
identity for all 15 untreated files, replaced the exact matched native/GDN/
grouped files, and passed its external manifest and loader closure.

The external runtime-manifest SHA-256 is
`a4e83ec34d91b70a666dc170fcc3bda75562592c58fce198f29cfa4d25755d0d`;
the finalizer-evidence manifest SHA-256 is
`2c049273bfc9e8dd429e2f74969cb9c4917a6e23833fcb8e8584ba8944a62aee`.
The native, staged GDN, and staged grouped hashes are respectively
`8d6d41a2...`, `6c9ba1f1...`, and `c8ba41d4...`.

This pass authorizes only the separately frozen A2 stage qualification. No GPU
qualification, model load, endpoint, quality test, or speed measurement ran.

Structured result:
[`20260831-grouped-serving-stage-a2-finalizer-positive.json`](../data/20260831-grouped-serving-stage-a2-finalizer-positive.json).
