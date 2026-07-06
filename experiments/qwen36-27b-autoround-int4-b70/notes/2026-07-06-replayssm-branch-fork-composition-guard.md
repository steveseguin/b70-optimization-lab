# ReplaySSM branch-fork composition guard

Date: 2026-07-06

Status: **state-transaction infrastructure; no throughput claim; no LocalMaxxing submission**.

Current strict Qwen27 headline remains `68.23626314761921 tok/s` for the webhie AutoRound INT4 + target INT8 BF16-scale + draft INT4 BF16-scale ReplaySSM recipe.

## What was tested

Branch/regenerate cannot safely proceed until a branch slot can be forked from a source GDN/ReplaySSM slot and advanced to an accepted draft prefix without corrupting source state or unrelated destination slots.

Added guard:

- `/home/steve/llm-optimizations/scripts/check-gdn-replayssm-fork-commit-slots.py`

The guard validates this composition:

1. copy the normal GDN conv state from `src` slot to `dst` slot;
2. call native `torch.ops._xpu_C.gdn_replayssm_copy_slots` to copy ReplaySSM ring/metadata and `conv_pending`;
3. compact to valid `(src, dst)` branch rows;
4. call native `torch.ops._xpu_C.gdn_replayssm_commit_pending` on the compacted destination slots with the accepted-prefix counts.

It covers:

- active source rows;
- inactive source rows (`pending == 0`);
- null source row `0`;
- negative source row;
- out-of-range source row;
- accepted count larger than `pending_len`;
- source-slot immutability after fork/commit.

## Key finding

Do **not** commit the raw destination list after `copy_slots`.

`copy_slots` safely ignores invalid/null/out-of-range source rows, but if the next commit uses the unfiltered destination list, `commit_pending` sees a perfectly valid destination slot and can mutate unrelated stale/pending state there. The correct branch transaction must compact to rows where both source and destination are valid before commit.

The first version of the guard intentionally exposed this mistake:

- BF16/FP16/FP32 all failed;
- `d_cache`, `k_cache`, `g_cache`, `conv_pending`, `cache_base`, and `pending_len` matched;
- `conv_state`, `write_pos`, `is_flush`, and `pending` mismatched because invalid-source rows still triggered commit on destination rows.

After compacting valid branch rows before commit, the guard passes.

## Validation

Runtime prefix:

```bash
cd /home/steve/llm-optimizations
export VLLM_TARGET_DEVICE=xpu
export PYTHONPATH=/home/steve/src/vllm-xpu-kernels:/home/steve/src/vllm${PYTHONPATH:+:$PYTHONPATH}
export LD_LIBRARY_PATH=/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels:/home/steve/.venvs/vllm-xpu/lib:/home/steve/.venvs/vllm-xpu/lib/python3.12/site-packages/torch/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
PY=/home/steve/.venvs/vllm-xpu/bin/python
```

Commands:

```bash
$PY -m py_compile scripts/check-gdn-replayssm-fork-commit-slots.py
$PY scripts/check-gdn-replayssm-fork-commit-slots.py --device xpu:0 --dtype bf16 --json-out /tmp/gdn-replayssm-fork-commit-bf16-20260706.json
$PY scripts/check-gdn-replayssm-fork-commit-slots.py --device xpu:0 --dtype fp16 --json-out /tmp/gdn-replayssm-fork-commit-fp16-20260706.json
$PY scripts/check-gdn-replayssm-fork-commit-slots.py --device xpu:0 --dtype fp32 --json-out /tmp/gdn-replayssm-fork-commit-fp32-20260706.json
```

Results:

- BF16: pass, all equality fields true, all max diffs `0.0`;
- FP16: pass, all equality fields true, all max diffs `0.0`;
- FP32: pass, all equality fields true, all max diffs `0.0`;
- source slots `1` and `2` unchanged for conv state, ReplaySSM rings, metadata, and pending buffers.

Tracked JSON:

- `/home/steve/llm-optimizations/experiments/qwen36-27b-autoround-int4-b70/diagnostics/gdn-replayssm-branch-fork-composition-bf16-20260706.json`
- `/home/steve/llm-optimizations/experiments/qwen36-27b-autoround-int4-b70/diagnostics/gdn-replayssm-branch-fork-composition-fp16-20260706.json`
- `/home/steve/llm-optimizations/experiments/qwen36-27b-autoround-int4-b70/diagnostics/gdn-replayssm-branch-fork-composition-fp32-20260706.json`

## Failed monolithic-kernel attempt

I briefly tried a single native `gdn_replayssm_fork_commit_slots` op that would copy conv state, copy ReplaySSM ring/metadata, and commit the accepted prefix in one kernel. It compiled the host side, but the targeted `_xpu_C` link entered `ocloc` device compilation for more than 14 minutes without producing a module. I interrupted it and removed the op before committing.

Conclusion: the monolithic all-cache/all-conv fork+commit shape is too compile-heavy for useful iteration. Keep the smaller validated composition for now. If a fused native op is needed later, split it into smaller primitives, likely:

- metadata + commit only;
- conv-state copy/commit only;
- ReplaySSM ring copy as the existing `copy_slots`.

## Next implementation point

The lowest-blast-radius endpoint insertion point is in `GPUModelRunner.propose_draft_token_ids()` after `prepare_next_token_ids_padded()` computes `next_token_ids` and `valid_sampled_tokens_count`, but before `prepare_inputs_padded()` / `drafter.propose()`.

For any branch/regenerate prototype:

- derive accepted **draft prefix** count, not raw visible count;
- compact to valid branch rows before any commit;
- fork GDN/ReplaySSM branch state with this guard's composition;
- do not let invalid/null/out-of-range branch rows reach commit;
- run `scripts/check-gdn-replayssm-commit-pending.py`, `scripts/check-gdn-replayssm-fork-commit-slots.py`, `scripts/check-gdn-native-spec-prefix.py`, and `scripts/check-gdn-spec-recurrent-exact.py` before endpoint gates.
