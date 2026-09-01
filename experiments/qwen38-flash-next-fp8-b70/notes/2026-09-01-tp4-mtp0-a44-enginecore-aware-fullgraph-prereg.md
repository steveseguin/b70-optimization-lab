# Qwen3.8 Flash-Next FP8 A44 EngineCore-aware full-graph preregistration

Date: 2026-09-01
Status: frozen before GPU launch

A44 is the fresh attempt-44/port-19716 successor to the pre-load A43
interruption. It changes only isolated attempt, port, request, cache, trace,
and evidence paths. Model revision, TP4/EP4 MTP0, 4,352-token limit, PLE-only
UVA placement, synchronous PLE, 128 MiB KV cache, full-decode-only size-1 XPU
graph, compilation mode NONE, oneCCL/kernel identities, prompts, output
authorities, complete quality battery, and teardown contract are unchanged.

The client continues to bind the audited A43 runtime verifier
`c7748c0316de5cddf3366c28bea419294d51cad92ad14bad893d4c8234099888`.
Direct generated A44 sources were compared with direct A43 sources and differ
only by the declared path identities, port, inner attempt, and bound wrapper
hashes. Those audited sources were then promoted as standalone tracked scripts,
removing the accumulated recursive validation cost. The exact tracked hashes
are:

- launcher: `981d50ff49bcd605ce6c0792fffc64c5e72b1a3700c2bbcda240d85635056c6b`;
- client: `431ebd4547150668610b9ed0d46574725202a279eedf7412b3d51c7ea1ce2904`;
- supervisor: `5439e66e88ba0ffeb540f60d8578987e7e5a6621ec6063e383d7656f2e65241f`.

One legitimate inner-source digest happens to contain the characters `a44`.
It is an exact hash field, not an attempt path. A44 is flattened, and any later
successor must protect that field explicitly or rewrite named fields rather
than applying a broad attempt-name substitution. A44 receives no credit unless the unchanged recovery,
semantic, repeat, short-output, exact-4K, and runtime-trace gates all pass. A
trace-off fresh repeat remains mandatory before promotion. No reboot or
per-boot load rule applies.
