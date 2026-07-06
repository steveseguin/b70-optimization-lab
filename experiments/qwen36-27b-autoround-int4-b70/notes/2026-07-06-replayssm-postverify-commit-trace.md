# Qwen27 ReplaySSM commit trace hooks

Date: 2026-07-06

Classification: diagnostic instrumentation, no endpoint speed result.

## Purpose

After the synchronized MTP timing correction, the remaining credible
Qwen27/GDN lane is not another MTP-next dispatch or accepted-count offset
sweep. The useful question is whether live endpoint rows commit ReplaySSM state
with the intended draft-owned prefix count, or whether target-owned
replacement/bonus rows leak into the rolling ReplaySSM transaction.

The first hook extends the existing `commit_gdn_replayssm_after_verify()`
default-off Mamba copy trace entry, which previously only wrote
`mamba_group_id`, row count, and state slots. It adds:

- input row;
- request id;
- running state slot;
- scheduled speculative draft length and first draft ids;
- ReplaySSM `commit_count` actually passed to the per-layer pending commit.

Patch snapshot:

```text
patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-replayssm-postverify-commit-trace-20260706.patch
```

That was not enough for the current record recipe because
`VLLM_XPU_GDN_REPLAYSSM_COMMIT_IN_FORWARD=1` means active rows are committed
inside the next GDN forward, not in the post-verify helper. A second default-off
hook was therefore added around `GatedDeltaNetAttention._commit_gdn_replayssm_pending()`
to trace the ReplaySSM ring state before and after the in-forward commit:

```text
patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-replayssm-inforward-commit-trace-20260706.patch
```

## Safety

The hook only runs when the existing Mamba copy trace is enabled. Normal
benchmark and serving behavior are unchanged.

Local compile checks:

```bash
cd /home/steve/src/vllm
/home/steve/.venvs/vllm-xpu/bin/python -m py_compile \
  vllm/v1/worker/mamba_utils.py \
  vllm/model_executor/layers/mamba/gdn_linear_attn.py
```

## Trace runs

Post-verify trace:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/traces/qwen27-replayssm-postverify-trace-20260706T154920Z
```

- `VLLM_XPU_MAMBA_COPY_TRACE_FILE` produced zero lines.
- `VLLM_XPU_COW_WORKER_TRACE_FILE` produced 465 lines.
- Quality trace covered 13 cases; color/order outputs were correct in that
  small trace.
- Conclusion: current Qwen27 record path does not use the post-verify commit
  helper for live rows; it commits ReplaySSM in forward.

In-forward trace, all GDN layers:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/traces/qwen27-replayssm-inforward-commit-trace-20260706T160020Z
```

- `VLLM_XPU_GDN_ROW_TRACE_FILE` produced 300 lines:
  150 `replayssm_commit_pending_before` and 150
  `replayssm_commit_pending_after`.
- Early rows include graph warmup / dummy rows with `state_indices=[0]`.
- Live rows showed nonzero state slots and pending ring commits.

In-forward trace, layer 0 only:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/traces/qwen27-replayssm-layer0-commit-trace-20260706T160220Z
```

- 104 trace lines, 52 before/after pairs.
- Before commit accepted-count distribution:
  - `[4,1,1,1]`: 31 pairs;
  - `[1,1,1,1]`: 13 pairs;
  - `[2,1,1,1]`: 8 pairs.
- Pending-before distribution:
  - `[1]`: 37 pairs;
  - `[0]`: 13 pairs;
  - `[]`: 2 warmup/dummy pairs.
- Full accepts commit the pending length 4 and advance `write_pos` /
  `cache_base` deterministically.
- Partial rows with visible count 2 commit count 2 and advance `write_pos` to 2.

The trace command used the existing row trace surface:

```text
VLLM_XPU_GDN_ROW_TRACE_FILE=<path>
VLLM_XPU_GDN_ROW_TRACE_STAGES=replayssm_commit_pending_before,replayssm_commit_pending_after
VLLM_XPU_GDN_ROW_TRACE_LAYERS=0
```

## Current conclusion

The current 68.236 tok/s strict Qwen27 recipe commits ReplaySSM in the GDN
forward path. The in-forward ring transaction is cheap and deterministic. The
important unresolved question is whether raw visible count 2 means "two
draft-owned tokens" or "one draft-owned token plus a target-owned replacement /
bonus row". If target-owned rows are included, the active path can still
double-advance GDN state in partial/replacement cases, and the next fix should
carry an explicit draft-prefix transaction count instead of reusing the visible
output count.

This is evidence-gathering for a fixed-shape graph-safe transaction/tape; it is
not itself a speed candidate.

## Next diagnostic

Add trace-only fields around `_update_states_after_model_execute()` after the
final accepted-count correction:

- raw visible accepted count;
- final accepted count written to `self.num_accepted_tokens.gpu`;
- output token ids for the row;
- suppressed replacement / bonus masks when present;
- a derived draft-prefix count candidate.

Do not change behavior until that trace proves whether count 2 is leaking
target-owned rows into ReplaySSM commit.

## Follow-up: rich accepted-count trace closed the leak hypothesis

Patch snapshot:

```text
patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-rich-count-trace-20260706.patch
```

Run:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/traces/qwen27-replayssm-rich-count-trace-20260706T160507Z
```

The trace added default-off fields to `mamba_state_update_counts_final`:

- raw accepted count;
- final accepted count;
- output token ids;
- scheduled spec length / ids;
- suppressed replacement / bonus masks;
- trace-only draft-prefix-count candidate.

Result:

- 63 final-count rows;
- raw/final/mask distribution:
  - `(4, 4, false, false)`: 30;
  - `(1, 1, false, false)`: 24;
  - `(2, 2, false, false)`: 9.
- Every raw-count-2 row had `suppressed_replacement=false` and
  `suppressed_bonus=false`; the common row was ordinary visible color-output
  token ids `[11,5983]` (`, green`), not a target-owned replacement row.
- Layer-0 ReplaySSM in-forward commit had the same distribution as the earlier
  trace: 52 pairs, with `[4,1,1,1]` x31, `[1,1,1,1]` x13, `[2,1,1,1]` x8.
- Quality outputs were correct. `baseline_match_all=false` only because this
  diagnostic used a 128-token long-context prompt while the saved baseline was
  keyed for 1024-token long context, so the long-context baseline entry was not
  considered present.

Conclusion: the visible-count-2 ReplaySSM commits observed in layer 0 are not
evidence of target-owned replacement/bonus rows leaking into the ring
transaction. Do **not** implement a behavior change that subtracts one from
these rows. The next speed work should move back to the larger surfaces:
acceptance/tokens per verifier step, verifier/LM-head cost, or a stronger
fresh-request drafter such as DFlash if its acceptance oracle justifies the
engineering cost.
