# Split 23 at context 65536: rank-1 storage that fits, exactly (2026-10-26)

Rank 1 alone on card 27, the service environment (including `OWNRT_DENSE_RAW=1`), and 256-row prefill chunks. The
reference is the live service binary `0efa50e4c5ee` (canonical). Lab copy only; the canonical tree is untouched.

**Verdict: split 23 now fits on rank 1 at context 65536 with 256-row chunks, and it is exact.** Two default-off,
rank-1-only storage changes do it:
- `OWNRT_QSA_RAW_RING=1`: −233 MB at split 23;
- `OWNRT_PREFILL_SHADOW_PACK=1`: −149.5 MB.

No arithmetic changes. Every gate is bitwise exact, including a 30,000-row prompt. The draft-head lever for rank 0 is
`OWNRT_DRAFT_HEAD_RAW=1` (default off). It saves 117 MB, is CPU-proven, and its only device check is the service's
startup gates.

| rank 1 (cap 32,212,254,720 B) | reference | ring + pack |
|---|---|---|
| plan, split 24 | 30,959,631,492 | 30,759,877,764 |
| plan, split 23 | 32,356,767,340 (refused, 144.5 MB over) | **32,123,721,324** (88.5 MB headroom) |
| runtime census, split 24 (measured) | 31,177,563,332 | 30,828,309,700 |
| runtime census, split 23, context 65536 (measured) | ≈32,574,699,180 (362 MB over) | **32,192,153,260 (20.1 MB headroom; loads and runs)** |
| runtime census, split 23, context 32768 (measured) | 31,488,374,444 | 31,223,269,036 |
| prefill shadows, 256 rows | 217,802,752 | 68,302,848 (12 shared slots) |
| QSA raw buffers, split 23 | 234,881,024 (7 × 33.5 MB) | 1,835,008 (7 × 256 KB) |

**Rank 1 alone, context 65536, 4096-row prompt (3 interleaved runs each, ring+pack build):**

| | decode half | prompt time |
|---|---|---|
| split 24 | 12.932 / 12.942 / 12.936 → **12.936 ms** | 16.93 s |
| split 23 | 13.407 / 13.407 / 13.411 → **13.407 ms** | 17.37 s |

- Layer 23 costs rank 1 0.47 ms per half (and 0.44 s of prefill per 4096 rows).
- With the service's numbers (rank 0: 12.28 ms half + 0.66 ms draft wait; rank 1: 11.64 ms), moving it should give
  about rank 0 ≈ 12.45, rank 1 ≈ 12.11 ms per position: −0.5 ms (≈ −4%) on the slower rank. Only the service suite can
  confirm this, because rank 0 cannot run in the lab.
- The ring and the packing cost nothing at split 24:
  - half: 12.93 vs 12.93 ms (switch off: 12.929);
  - prompt: 16.92 vs 16.94 s.

## Exactness
**Gates** (`compare_ring.py`):
- Every buffer of the state dump must equal the reference bitwise.
- Each rank-1 `blk.N.qsa.raw` (now a ring) must equal, slot by slot, the newest reference row with that slot index.
- Across contexts, KV and pooled buffers must match over the written rows and be zero after them.

| gate | result |
|---|---|
| split 24, 64K, 4096 rows: ring+pack vs reference | 1032 buffers equal (6 rings reconstructed), tokens equal |
| split 24, 64K, 300 rows (44-row last chunk) | 1032 equal (6 rings), tokens equal |
| split 23, 32K, 4096 rows: ring+pack vs reference | 1079 equal (7 rings), tokens equal |
| split 23 at 64K vs the 32K reference, 4096 rows | 1079 equal (7 rings, 21 KV prefixes), tokens equal |
| split 23 at 64K vs the 32K reference, 30,000 rows (118 chunks; the ring wraps 58 times) | 1079 equal (7 rings, 21 KV prefixes), tokens equal |
| final build `fccabd41b653` with all three switches, split 24 | 1032 equal (6 rings), tokens equal |
| switches off (builds a and b) vs reference | 1032/1032 equal, tokens equal |

- Every run held only renderD131.
- No kernel fault, reset, hang or timeout lines appeared before or after any run.
- No device microbenchmarks were run.

**Raw ring (why it is exact; `qsa_ring.hpp`).**
- `qsa_append_pool` is the only reader and writer of `qsa.raw` (plan.hpp).
- A launch of T ≤ 256 rows at position `pos` writes raw rows `pos..pos+T-1`, and reads raw only for the earlier rows of
  the pools it completes: rows `[4*(pos/4), pos)`, at most 3.
- So the at most T+3 rows one launch touches are distinct modulo 512. Every row it reads was written by an earlier
  launch and not overwritten since.
- Reads return the same bytes, and every output is unchanged. Only rows that are never read again are dropped.
- All three pool implementations index the ring under one shape flag: ng/packet18 (the one in use), specialised and
  p42. The adapter sets the flag only when the bound raw allocation is ring-sized.
- **CPU check** (`cputest/test_qsa_ring.cpp`): runs the engine's own `ng::cpu` pool code for 76 launches (256-row chunks,
  a partial chunk, single rows, odd sizes), with the full buffer and with the ring.
  - keys, values and pooled are bitwise equal after every launch;
  - all 512 ring slots equal the newest full-buffer rows;
  - a negative control (one corrupted ring row) is detected.

**Shadow packing (why it is exact; `prefill_engine.hpp`).**
- A chunk runs `prefill_sites` in order (all rows of a site before the next), and only `prefill_chunk` reaches the
  shadows.
- A role's value lives from the site that writes it to its last reader before the next write. The input stream role,
  and every non-layer role, lives for the whole chunk.
- Roles share an allocation only when none of their live ranges intersect. So two roles of the same site never share,
  and every read sees its own role's last write.
- Packing is largest-first, best-fit. The engine writes the slot assignment to `prefill-shadow-pack.json`; the offline
  estimate is `cputest/shadow_live.py`.

**Draft head raw (rank 0; `OWNRT_DRAFT_HEAD_RAW=1`).**
- The draft's 91392-row head prefix is uploaded as raw rows (the dense-raw layout). The BF16-activation raw kernel
  `dense_rows_bf16` reads it, keeping `Kernel<0,Q6_K,2560,1,false>`'s per-output sequence:
  - value (bit-identical);
  - input = float(bf16 << 16);
  - product, then add, in lane order;
  - adjacent-pair tree;
  - `bf16_bits` output.
- Proof:
  - the dense-raw CPU proof already covers every element of `output.weight`, which includes these rows;
  - the loader re-checks every element against the expanded rows (on by default) and refuses to start on a mismatch;
  - the CPU-device test `cputest/test_draft_head_bf16.cpp` passes 6/6 cases: rows 0–36 and 91355–91391, three inputs,
    bitwise against a host copy of the production kernel.
- It saves 116,981,760 B on rank 0. The projected time saving is about 0.19 ms per draft step (309 → 192 MB read), not
  measured.
- **Not device-run.** The service's startup gates (F32 oracle on both ranks, prefill gate, suite) are its device check.

## Rank-1 audit at split 23, context 65536 (runtime census, ring+pack)

| what | bytes | exact saving possible? |
|---|---|---|
| routed experts (75 tensors, raw GGUF, resident) | 27,525,120,000 | no |
| other weights (560: dense blocks, BF16 HC/router, norms; all at GGUF size) | 2,014,770,432 | no (nothing widened) |
| logits head (raw since dense-raw) | 521,472,000 | done |
| QSA keys + values, F32 at 65536 (7 layers) | 1,879,048,192 | no (F32 KV, position-major) |
| QSA pooled (select reads every pool) | 58,720,256 | no |
| GDN recurrent state (one bank on rank 1) + histories | 58,834,944 | no |
| prefill shadows | 217.8 → **68.3 MB** | **done (pack)** |
| QSA raw | 234.9 → **1.8 MB** | **done (ring)** |
| rope-f32 16.8 MB, rope-v2 8.4 MB | 25,165,824 | maybe 8.4 MB, if rope-v2 is unused in F32 mode (not checked) |
| gemv-workspace / operator-scratch | 2 × 8,388,608 | gemv-workspace is unused by the raw F32 head, but p28 validation requires 7.9 MB (possible 8 MB) |
| per-layer decode intermediates (25 layers) | ≈19 MB | aliasing them changes the dumped state; not done |

Nothing in the plan is stored wider than its GGUF bytes any more. The two optional items would add about 16 MB of
margin to the current 20.1 MB.

## Service path: what must change before split 23
1. **`adapter6.py` whitelist (line 57):** add `OWNRT_QSA_RAW_RING`, `OWNRT_PREFILL_SHADOW_PACK` and
   `OWNRT_DRAFT_HEAD_RAW`. Rank 0 ignores the first two; rank 1 ignores the third.
2. **`sc117-lan.service`:** set `SC117_TARGET_SPLIT=23` and the three environment lines. Update the comment "use 23
   only with SC117_CONTEXT<=32768".
3. **`service.py` F32 oracle check (startup).**
   - With the ring, each rank-1 `blk.N.qsa.raw.bin` is 512 rows (256 KB) instead of the oracle's 4096-context buffer
     (2 MB). Its hash cannot match `f32-state-oracle.json` as is, so the check would refuse to start.
   - The self-test writes 87 + 32 = 119 < 512 positions. The ring therefore holds exactly the oracle buffer's first
     512 rows, and everything after is zero in both.
   - Exact fix: in `cross_context_state` / `grown_prefix_hashes`, hash a ring buffer's bytes zero-extended to the
     oracle extent (4096 × 512 B) before comparing.
   - This also covers `split_differences`: at split 23, the moved layer 23's raw buffer is compared with the rank-0
     oracle entry.
   - Alternatively, record a ring-keyed oracle.
4. **Prefill gate:** its marker name includes all `OWNRT_*` variables, so the one-time batched-vs-token gate re-runs
   automatically. Both of its runs use the ring, so it compares like with like.
5. **Session checkpoints (ctxkeeper):**
   - The rank-1 raw ring is saved whole (new rule `raw_ring_rule`), and the packed shadows are classified as before
     (`card0:prefill:` labels, transaction lifetime).
   - The coverage changes, so checkpoints taken without the ring are refused (fail closed), not mis-applied.
   - Checkpoint STAGE/VERIFY/APPLY were not run in the lab; the driver has no checkpoint ops.
6. **Native controller / prefill wire header:** no change. The wire header's rows must still equal `--prefill-rows`
   (256), and packing is internal to `prefill_chunk`.
7. **Receipt:** a new build, so a new receipt and unit before any restart.
8. **Rank 0 never runs in this lab.**
   - Ring and pack are rank-1-only by construction: rank 0's speculative image captures KV rows by position.
   - The draft head raw path is rank-0-only and covered only by the service gates.

## Files
- **`split23.patch`:** against canonical `engine/src`, 13 files (one new: `qsa_ring.hpp`). Applied to a fresh copy, it
  reproduces the final lab source (build `fccabd41b653`). It also carries the `OWNRT_PLAN_ONLY` diagnostic.
- **`results.json`:** builds, every run (identity, timing, plan and runtime bytes, shadow allocation), gates and the
  owned-bytes table.
- **`cputest/`:**
  - `test_qsa_ring.cpp`
  - `test_draft_head_bf16.cpp`
  - `shadow_live.py`
- **`evidence/`:**
  - `compare_ring.py` and the run scripts (`run.sh` and the gate scripts);
  - run logs and per-run summaries, logs, censuses, plans and pack files;
  - CPU test outputs.
- **Binaries:**
  - `/dev/shm/engine-build-lab-s23-b/sc117-engine` (final);
  - `/dev/shm/engine-build-lab-s23-a/sc117-engine` (gates and timing).

  The binaries need the lab tree `/dev/shm/ownrt-lab-s23/engine`.

## Next steps (decode tok/s)
1. Deploy split 23 with ring+pack: the whitelist, the unit and the oracle zero-extension above. Expected: about
   −0.5 ms per position on rank 0, the bottleneck, with rank 1 at about 12.1 ms.
2. Turn on `OWNRT_DRAFT_HEAD_RAW=1` with it (rank 0: −117 MB, about −0.19 ms per draft step, projected) and let the
   startup gates and the suite check it.
3. If rank 1 becomes the bottleneck after the move, its dense-raw head and expert work are the next levers.
   The extra margin items above (rope-v2, gemv workspace) are only needed for split 22.
