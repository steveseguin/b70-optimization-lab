# Qwen3.8 Flash-Next FP8 TP4 MTP0 active-16K fresh-server A4 result

Date: 2026-08-28
Status: quarantined; fresh-server request stopped before first output

A4 did not reproduce A3's correct first response. The separately started
attempt-5 server passed every model, source, staged-runtime, four-rank,
placement, fixed-cache, and served-identity gate. It loaded all 131 external
checkpoint shards in 565.20 seconds, retained the exact four-rank 12.22-GiB
offload receipt, and exposed 21,795 cache tokens under the unchanged
33-block/358,465,536-byte configuration.

The sole frozen request used the same prompt and suite hash as A3. After
400.014 seconds it returned an error-only stream with no text, token IDs,
usage, or first-token timestamp. The engine dump retained 1,600 computed
prompt tokens, 64 more scheduled tokens, zero output tokens, zero prefix-cache
hits, and an RPC sampling timeout while the coordinator waited for a worker.
The API then shut the engine down. No semantic, speed, context-quality,
deployment, curve, or headline credit is granted.

This changes the mechanism interpretation. A3 remains valid evidence that one
fresh request can complete correctly and that its identical same-server repeat
can return corrupted repeated text. A4 now proves that a distinct fresh server
can also stop during the same 16K task before first output. The active-16K
problem is therefore nondeterministic long-context runtime stability; it is
not isolated to stale state on request two. Deeper 24K/32K serving remains
blocked, and another unchanged 16K retry is not authorized.

Controlled cleanup removed every owned process, listener, compile path, and
RPC path. All four B70s re-enumerated at 42.90 MiB or less. The strict
postflight still failed: 20 seconds after engine shutdown, cleanup recorded
eight compute/copy engine resets and 61 unsuccessful card responses. The host
window separately retained two corrected local-NVMe APEI records and three
RxErr lines, with no I/O error.

The two immutable raw roots verify through canonical manifests:

- run tree: 47 entries, tree SHA-256
  `82c6fafa8483f44c31e5e58ca42d4c9ad91166b94bfb4d53663f2742a5cd8392`,
  manifest-file SHA-256
  `95264b0edd9b560ae5e682ed23082a999d3b1d15fab8ba9a982d5a295a3d0e87`;
- supervisor tree: 24 entries, tree SHA-256
  `c3d40fc7d417d5ad3a2769a280caffb7334efa484694d42a49e29d554bf2fe92`,
  manifest-file SHA-256
  `5c00523c264d2a9d39c560a03f8076deef72ef0bb12ee7e012ac8573db7b2274`.

The next admissible arm needs a material runtime treatment plus a fresh
four-card health gate. The narrowest candidate is request-boundary GDN state
instrumentation followed by explicit first-chunk state clearing, with the
known-good short/4K identity checked before any deeper-context repeat. No
protected throughput claim or runtime selector changed.
