# SC117 service: new text decoded 30% slower than the suite (2026-10-25)

## Finding

The 12-prompt suite reported 47.5 tok/s, but the **first** request with any new text decoded at about 33 tok/s. A repeat
of the same prompt ran at full speed with identical tokens and MTP hits. Every suite number so far was measured on
prompts the host had already seen.

Cause: every decoded token reads, on rank 0's critical path, its embedding row and 16 hashed per-layer-embedding (PLE)
rows. The PLE rows are 8 bigram and 8 trigram ids derived from the last three tokens. They come from
`per_layer_token_embd.weight`: 320,001,536 rows × 160 IQ4_NL values, 90 bytes per row, 28.8 GB. The file sits on the
USB disk behind ntfs-3g (FUSE).
- New text means new n-grams, which means cold reads.
- A slow request showed 4,839 major faults and `prepare_ms` 3,083 against 171 on its repeat, with about 65 MB/s of disk
  reads during decode.
- A bare `pread` measurement: 0.127 ms per cold row, about 2 ms per token. Threads did not help (the FUSE daemon
  serialises them). The engine's slice path paid about 10 ms per token.

A second, smaller effect: the rank output directories (per-token stream appends) were also on the FUSE mount. A 1 GiB
write to the USB disk during a request took decode from 49.5 to 40.9 tok/s.

## Fixes (both exact: same bytes, same outputs)

1. `Weights::copy_lookups` (engine `297b388764e9`): rank 0 copies the embedding and PLE tables into anonymous host
   memory at load. That is 29,137,853,440 bytes in 55 s; there is no swap on this host, so the copy stays resident.
   `read()` serves from the copy first.
   - Switch: `OWNRT_LOOKUP_COPY=0` turns it off.
   - The serving adapter admits exactly that many extra bytes in its anonymous-memory bound and checks the size the
     rank reports in `lookup-residency.json`.
   - MemAvailable with the service up: about 78 GB.
2. `SC117_EVIDENCE_PARENT=/dev/shm/sc117-lan-evidence`: rank output directories on a RAM disk, about 6 MB per run.
   Durable records (requests.jsonl, gate evidence) are unchanged.

## Results (300-token answers, greedy, MTP)

| Prompt (first run on the host) | before | after |
|---|---|---|
| star life cycle | 33.6 | 48.4 (same 228 hits) |
| lighthouse story / robot story | 32.9 | 43.7 (more misses) |
| TCP vs UDP / B-trees vs LSM | 34.2 | 45.6 |
| photosynthesis / vaccines | 35.3 | 48.4 |
| four-day week / nuclear power | 37.5 | 49.8 |

- The suite stays byte-identical (12/12), median 47.95.
- F32 oracle: zero differences.
- Prefill gate: 13/13.
- Continuation gate: passes.
- Under the same USB write load, decode now holds at 49.0 tok/s.

## Lessons

- Measure service speed on text the host has never seen, as well as on the fixed suite. A warm page cache hid a 30%
  loss for real users.
- Keep every per-token host read and write off the ntfs-3g mount.
- If a model's lookup tables ever exceed host RAM, the fallback is prefetching rows for the MTP draft's guessed token
  while the step runs (exact on hits). It was not built because the copy fits.
