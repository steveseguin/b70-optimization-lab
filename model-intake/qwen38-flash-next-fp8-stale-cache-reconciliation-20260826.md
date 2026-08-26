# Qwen3.8 Flash-Next FP8 stale-cache reconciliation — 2026-08-26

## Scope

- Repository: `Qwen/Qwen3.8-Flash-Next-FP8`
- Pinned revision: `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`
- Materialized model root:
  `/mnt/usb-models/llm-models/Qwen3.8-Flash-Next-FP8`
- Cache quarantine:
  `/mnt/usb-models/quarantine/qwen38-flash-next-fp8-stale-incomplete-20260826T2118Z`

The pinned downloader exited successfully at 2026-08-26 17:15:40 EDT. The
materialized root then matched the pinned name-and-size inventory exactly:

- 144/144 root files and 185,563,783,127/185,563,783,127 bytes;
- 131/131 safetensor shards and 185,523,317,458/185,523,317,458 shard bytes;
- 144 completion metadata entries;
- no active downloader process.

Four `.incomplete` cache files remained even though the corresponding root
shards were present with completion metadata and their pinned sizes. They were
moved intact into the quarantine above; none was deleted:

| Cache artifact | Bytes |
|---|---:|
| `A2I9ZHzUfL6-7982vwUZqkG-kjY=.591f488ab5cd5f0bd4fe28266099523761b9b9339137800734c34ffd84595538.2e2ab241.incomplete` | 0 |
| `RcBJYVugXC9XxIikvFZO-T4ZOSQ=.774f0ceeadb40d165f2b3ff397d5f3840e6ca8fcb8f3d39d8acb4fea9e52c941.e8c67f91.incomplete` | 56,500 |
| `cSYNcFwDl4IAfoC0EjewA9-zicE=.974a2a2ab551f8f1405a4955ab32a8721c68c73dd85b382491d9f0e6a34ee752.f0a6e2c7.incomplete` | 0 |
| `o8zzDEwRCl4J1WgJ5aOjaIt4tKc=.6841fe21fa8a8a7a693c585efe65cd2732889095b696da88bda0cb287366910b.059a8a54.incomplete` | 0 |

`SHA256SUMS.before-move` in the quarantine (1,032 bytes) binds the four files
as found before the move. After the move, the cache had zero `.incomplete`
files and the materialized root retained the exact counts and byte totals
above.

## Evidence boundary

This action reconciles stale cache residue only. Name-and-size agreement and
completion metadata do **not** establish payload integrity. The authoritative
promotion gate is the pinned sequential hash, tokenless Hugging Face dry-run,
safetensors-header, and index-closure validator in
`scripts/validate-20260826-pinned-hf-downloads.py`. Until that validator emits
a passing final receipt, the model is downloaded but not fully validated and
must not be exposed to a GPU launch.
