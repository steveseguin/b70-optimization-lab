# P2 lever ladder for Qwen3.5-9B W4A16 on one B70 (2026-09-09)

Built from the launcher's actual env surface (about 90 knobs read by
`run-w8a16-mtp1-strict-server.sh` / `run-server.sh`), not from guesses, and pruned against what
the 2026-09-07/08 lane already closed. Every rung is gated on losslessness first and timed only as
a two-fresh-server pair on an otherwise quiet host.

## Tier A - untested speed levers

| # | Lever | Why it is expected to matter | Status |
| --- | --- | --- | --- |
| A1 | `VLLM_XPU_GDN_SPEC_GROUP` 8 / 16 / 32 | Pinned at 16 on every run of this lane and never swept, on any model. It groups the GDN hybrid's speculative work, so it sits directly on the verify step the whole headline depends on. | open |
| A2 | `VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH` | Persistent scratch across speculative steps; never exercised here. | open |
| A3 | `cudagraph_capture_sizes` matched to the real decode shape | The captured list `[1..64]` is inherited from the 27B lane. At depth `d` each sequence presents `d+1` rows, so the shapes actually executed may fall outside capture and silently run eager - the same class of error that made a 27B lane measure the wrong graph mode. | open |
| A4 | MTP depth re-swept **per context depth** | Depth 3 was chosen on the FP8 route at short context and inherited. W4A16 is lossless to depth 6, and acceptance changes with context. Largest untested lever. | open |
| A5 | `VLLM_XPU_DRAFT_LM_HEAD_INT4_GROUP_SIZE` / `_CHUNK_ROWS` / `_APPLY_ROWS` / `_SCALE_DTYPE` | The draft-only INT4 lm_head is already worth +27.6%, and none of its four internal knobs has been tuned. | open |
| A6 | `VLLM_XPU_MTP_DRAFT_EAGER` | Whether the draft pass belongs inside capture at all. | open |
| A7 | `MAX_NUM_BATCHED_TOKENS` / chunked-prefill split at 32K | 4096 is the 27B lane's number; a 9B with ~19 GiB spare for KV is a different balance point. | open |
| A8 | `GPU_MEMORY_UTILIZATION` / KV budget | Respect the headroom rule: never park a card within ~0.3 GiB of capacity or it pays whole-buffer PCIe migrations per cold touch. | open |

## Tier B - determinism reach (measured free, efficacy untested at TP1)

| # | Lever | Note |
| --- | --- | --- |
| B1 | `VLLM_XPU_RMSNORM_SERIAL_ROWS` at a threshold **above the top rung** | Measured free end to end at every rung (-0.2% to +0.6%) and it is the only formulation that reproduces the single-row result, so it needs no re-qualification. Its recorded negative is a **two-card** result: it does not close the TP2 collective gap (0.7031% -> 0.5469%, n.s. over 1280 requests/arm). That does not transfer to TP1, where the residue is the norm's row-count dependence rather than the collective. Note the value is a **row threshold**: at 64 it is inert above 64 rows, which is exactly where the TP1 route currently loses a request. Test at 128/256. |
| B2 | `VLLM_XPU_GDN_ROW_STABLE_RMSNORM` | Never tested on this model. |
| B3 | `VLLM_XPU_LM_HEAD_BATCH_INVARIANT` + `_BATCH_REPAIR_MARGIN` / `_BATCH_REPAIR_ROWS` | A near-tie repair path at the lm_head; the divergences are exact two-way ties, which is what this targets. |

## Tier C - closed, do not repeat

- `VLLM_XPU_W4A16_DETERMINISM_PAD`: inert below 128 rows and published off. Confirmed on this model.
- float32 accumulation in the norm reduction: makes row-invariance **worse**, not better (7.66% of
  rows differ at 128 rows against the float16 expression's 0%).
- The textbook row-invariant float16 norm: genuinely row-invariant, but not a drop-in - it differs
  by up to 3 ULP and changes most rows even at a single row, so it is a new authority, not a fix.
- Serialised norm as a **two-card** identity fix: not a fix (above).
- FP8-dynamic above MTP depth 3: not lossless (8/12 against the MTP0 oracle).
- Both interventions together on two cards: 0.7031% -> 0.3906%, still not a fix.
