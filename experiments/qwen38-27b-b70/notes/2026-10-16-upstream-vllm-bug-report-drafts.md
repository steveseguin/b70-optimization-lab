# Upstream vLLM bug report drafts (2026-10-16)

> **DRAFTS, awaiting owner approval.** Nothing in this file has been filed, posted, commented or pushed anywhere.
> The owner decides, for each one, whether to file it, where (new issue or comment on an existing thread), and
> checks the links first.

Reporter hardware: two Intel Arc Pro B70 (32 GiB each), Qwen3.8-27B-FP8, MTP (`qwen3_next_mtp`) depth 5, TP 2.

## Source trees behind the line numbers (owner reference; trim before posting)

| Name used below | What it is | Local path |
|---|---|---|
| R314 | vLLM 0.29.0 (`_version.py` commit `98dff2a81` = upstream tag `v0.29.0`) as shipped in lab image R314 | `/mnt/fast-ai/src/vllm-r314-site-packages/vllm` |
| v0.29.0, main | upstream vLLM tag `v0.29.0` (`98dff2a81d74`) and `origin/main` `84bcbc626443` (2026-10-03) | `/home/steve/src/vllm-current-main` (partial clone) |
| kernels 0.1.14.1 | vllm-xpu-kernels `6d92b1bfbf32` (tag `0.1.14.1`), clean clone | `/home/steve/builds/rebase-v0290-kernels-cleanclone-20260913/vllm-xpu-kernels` |
| kernels main | vllm-xpu-kernels `efc85bc8a0eb` (2026-09-11) | `/home/steve/builds/mirrors-20260912/vllm-xpu-kernels.git` |

R314 against stock v0.29.0, checked by diff: `v1/spec_decode/utils.py`, `v1/worker/gpu_input_batch.py`,
`v1/worker/mamba_utils.py` and `v1/core/sched/scheduler.py` are byte-identical. `v1/worker/gpu_model_runner.py` is
identical up to line 3948; after that the PR #53059 hunk shifts lines by +15. `v1/attention/backends/gdn_attn.py`
carries the hunks of open PRs #51565 and #53542. `vllm/_xpu_ops.py` is a lab port, and its grouped spec path is lab
code. The three kernel files cited (`gdn_attn_interface.cpp`, `gated_delta_rule.hpp`, `causal_conv1d.hpp`) are
identical in kernels 0.1.14.1 and kernels main. The lab's r310/r313 kernel patches do not touch the lines cited.

Not checked: vLLM main after 2026-10-03; kernels main after 2026-09-11; the current GitHub status of PR #53542 and
kernels #593; the V2 model runner; CUDA or ROCm (anything said about them below comes from reading the source only).

---

## 1. GDN speculative state-index table read past its width when a step is narrower than the last acceptance

**Title:** `[Bug][XPU][GDN][Spec Decode] With per-step spec width (PR #53542), GDN spec kernels read the starting
state past the state-index row when a step is narrower than the previous step's accepted count`

**Projects:** the read and the width rule are in **vllm-xpu-kernels** (`csrc/xpu/gdn_attn/`). The narrowing is in
**vLLM** `vllm/v1/attention/backends/gdn_attn.py` (the metadata builder, the hunks of open PR #53542).
Possible venue: a follow-up comment on vllm#53542 and vllm-xpu-kernels#593.

**Affected, as observed:** vLLM 0.29.0 XPU fork (R304/R313 images = v0.29.0 + PR #53542 hunks) with
vllm-xpu-kernels 0.1.14.1. The 27B case below ran with synchronous scheduling; neither the builder nor the kernel
code involved depends on the scheduling mode. Stock v0.29.0 and main `84bcbc62` still slice the table
to the full `num_spec + 1` (v0.29.0 `gdn_attn.py:307-308`, `:328-329`; main `:366-367`, `:387-388`). There, the same
narrow step fails the kernel's width check instead (kernels #593, reproduced on stock v0.29.0 on 2026-09-12). The
out-of-range read appears once the table is narrowed to the step width.

**Mechanism:**
- After a verify step accepts `a` tokens, the next step's SSM spec kernel reads its starting state from column
  `a - 1` of `spec_state_indices_tensor`, with no bound check: kernels `gated_delta_rule.hpp:392-395`
  (`cache_indices[batch_id * cache_indices_stride_0 + init_col]`). The count comes from `num_accepted_tokens`
  (R314 `gdn_attn.py:396-397`).
- PR #53542 sets `active_spec_width` = the longest spec query in this step (R314 `gdn_attn.py:295-298`) and slices
  `block_table_tensor[spec_sequence_masks_cpu, :active_spec_width]` (`:338-340`, `:359-361`). It does the same in
  the full-graph buffer (`:471-478`). Boolean-mask indexing returns a contiguous copy, so the row stride equals the
  step width.
- If step N accepted `a` and step N+1 has width `w < a`, column `a - 1` falls in the next request's row or past
  the end of the tensor. The request then starts from the wrong state, with no error.
- The table cannot simply be made wider, because the kernels take the number of tokens per request from its width:
  `gdn_attn_interface.cpp:96` (`num_speculative_tokens = size(1) - 1`), the check at `:119`,
  `gated_delta_rule.hpp:705` and `causal_conv1d.hpp:1039`. They already address elements through `stride(0)`
  (`gated_delta_rule.hpp:395`, `:510-511`; `causal_conv1d.hpp:681`), but `gdn_attn_interface.cpp:82-84` requires
  `is_contiguous()`.
- From the source only: the shared Triton spec kernel indexes the same way (v0.29.0 `fused_sigmoid_gating.py:106-110`,
  called with `ssm_state_indices=spec_state_indices_tensor` at `qwen_gdn_linear_attn.py:1461-1476`), so a table
  narrowed in the shared builder would reach it too. Not run on CUDA.

**Reproduction:** a hybrid GDN model with MTP, where a request's step is narrower than what it accepted in the step
before. The trigger that stock vLLM can reach is the end of the context window: the scheduler clamps the last step
to `max_model_len` (scheduler.py:598-603) right after a fully accepted step. Lab case: Qwen3.5-4B on one B70, MTP
depth 3, `--max-model-len 256`, a 14-token prompt, `max_tokens 242`, greedy, `ignore_eos`. A lab-only trigger that
makes it frequent: the lab's copy-draft proposer, whose 6-9-token drafts alternate with 5-token MTP drafts
(9 verify slots).

**Symptom (lab numbers):**
- 4B case: the last token (index 241 of 242) differs from the no-spec output, in both repeats. At max-model-len 512
  the same request is byte-identical. The trace shows a width-3 last step right after `num_accepted = 4`.
- 27B FP8, TP2, sync scheduling, copy drafts up to 9 tokens: without the fix (R313), the answers equal to no-spec were
  11/12 strict, 5/8 long prompts and 55/64 short. The wrong answers came after a step that accepted six or more
  drafted tokens. With the fix (R314 + overlay): 12/12, 8/8, 64/64. The spec-kernel census was 74/74 identical to
  one-token decode. The shipped MTP5 recipe gave 12/12 twice at 90.30 / 90.34 tok/s, with no speed cost.

**Fix we used:**
- Kernel patch `experiments/qwen38-27b-b70/patches/vllm-xpu-kernels-gdn-spec-state-row-stride-r314-20261004.patch`.
  It replaces `is_contiguous()` at `gdn_attn_interface.cpp:82-84` with `stride(1) == 1 && stride(0) >= size(1)`.
  Every contiguous tensor still passes, with the same kernel arguments.
- vLLM overlay `experiments/qwen38-27b-b70/overlays/b70-gdn-state-width/b70_gdn_state_width.py` (0.1.0,
  `B70_GDN_STATE_WIDTH=1`). It wraps `GDNAttentionMetadataBuilder.build`. Only when a spec step is narrower than
  `num_spec + 1`, it returns `block_table_tensor[spec_mask, :num_spec + 1][:, :width]` instead. That view has the
  same shape and values, but its row stride is `num_spec + 1`, so column `a - 1` stays readable. In the full-graph
  branch it fills the persistent buffer's remaining columns. Full-width steps get the same tensor object back.
  (It also drops a `.contiguous()` in the lab's own grouped XPU path; that part is lab-only.)
  Tests: `experiments/qwen38-27b-b70/tests/test_b70_gdn_state_width.py`.

**Suggested upstream fix:**
- vllm-xpu-kernels: accept a row-strided `spec_state_indices_tensor` (the one-check change above), or take the number
  of tokens per request from `spec_query_start_loc` or an explicit argument instead of `size(1)`. Either way, check
  `num_accepted_tokens - 1` against the row capacity.
- vLLM (#53542): pass the narrowed table as a view of full-width rows (`rows[:, :num_spec + 1][:, :w]`) instead of a
  contiguous `:active_spec_width` copy, and do the same in the full-graph persistent buffer.

---

## 2. Accepted-draft count lost when a running request sits out one step (async spec decode, mamba_cache_mode "none")

**Title:** `[Bug][Spec Decode][Hybrid] Async spec decode on GDN/Mamba models: a running request that sits out one
step resumes with num_accepted_tokens = 1 and continues from the wrong recurrent state`

**Project:** vLLM (`vllm/v1/worker/gpu_model_runner.py`, `gpu_input_batch.py`, `spec_decode/utils.py`).

**Affected, as observed:** vLLM 0.29.0 XPU fork (R314). V1 GPU model runner (`VLLM_USE_V2_MODEL_RUNNER=0`), async
scheduling on, `qwen3_next_mtp` with 5 tokens, prefix caching off (`mamba_cache_mode` "none"), TP2, 4 concurrent
requests. Other lab overlays were loaded too (pure-step scheduler, per-sequence decode attention, the bug-1 fix).
The code involved is not XPU-specific. It is textually unchanged in main `84bcbc62`: all 43
`num_accepted` lines in `gpu_model_runner.py` match v0.29.0. Not run on main or on CUDA.

**Mechanism (R314 lines, which are identical in v0.29.0):**
- The GDN spec kernels keep one state per verify row. The next step starts from slot `a - 1`, chosen by
  `num_accepted_tokens` (R314 `gdn_attn.py:396-397`, v0.29.0 `:366`).
- With async scheduling and mode "none", `_prepare_inputs` sets every count to 1 (`gpu_model_runner.py:2153-2157`;
  the branch is chosen at `:2127-2129`). `update_num_computed_tokens_for_batch_change` (called at `:2172-2189`)
  then writes back the device `valid_sampled_token_count`, but only where `prev_positions >= 0`
  (`spec_decode/utils.py:586`, `:593-595`).
- `prev_positions` comes from `input_batch.prev_req_id_to_index` (`gpu_model_runner.py:1784-1792`). It is -1 for a
  request that was not in the immediately previous step.
- When the scheduler leaves a running request out of a step without preempting it, `_update_states` removes the
  request from the persistent batch (`gpu_model_runner.py:1257-1263`). `remove_request` also drops it from
  `prev_req_id_to_index` (`gpu_input_batch.py:573-574`). When it is scheduled again it is re-added
  (`gpu_model_runner.py:1464-1475`, `:1521-1523`), and `add_request` sets `num_accepted_tokens_cpu = 1`
  (`gpu_input_batch.py:484`).
- So on its first step back the count is 1, and the kernels start from slot 0. That is the state after only the first
  verify row of its last step, missing `a - 1` accepted tokens. The correct state is still in slot `a - 1`, but
  nothing reads it. From the source (not run), the sync path loses the count the same way, through the
  `add_request` reset and `:2146-2150`.
- The same code in main: `gpu_model_runner.py:1245-1251`, `:1448-1459`, `:2085-2115`, `:2121-2138`;
  `spec_decode/utils.py:816`, `:836-845`; `gpu_input_batch.py:481`, `:571-572`.

**Reproduction:** use the config above with two or more concurrent greedy requests. While request A decodes and
accepts two or more tokens per step, run one step that schedules other work but not A (without preempting A). Then
compare A's output with A run alone. We produced the skip with a lab scheduler overlay (`b70-exclusive-prefill`). It
runs each prompt chunk in a step of its own through the stock `Request.next_decode_eligible_step` check
(scheduler.py:573-577), so decoding requests sit out every prompt step. In stock 0.29.0 a running request is also
left out, without preemption, when the token budget runs out before the loop reaches it (scheduler.py:552-555,
`:727-728`) or when `num_new_tokens == 0` (`:635-653`). We have not reproduced the bug with stock scheduling alone.

**Symptom (lab numbers, R314, TP2, MTP5, 4 users):** answers equal to the solo answers were 12/64 and 17/64 on long
prompts (two passes) and 7/64 and 5/64 on the 64-prompt short ladder. Every one of the 215 wrong answers had, at or
before its first wrong token, a skipped step right after a step that accepted two or more tokens. With the fix (the
only change): 64/64 and 64/64 on long prompts, 64/64 and 64/64 on the short ladder, exact against the frozen
single-user reference. Speed was unchanged: 55.0 / 55.4 tok/s (was 55.0 / 54.7) and 226 / 228 tok/s (was 225 / 222).

**Fix we used:** overlay `experiments/qwen38-27b-b70/overlays/b70-spec-resume-accepted/b70_spec_resume_accepted.py`
(0.2.0, lab commit `114b850f9`, kept in 0.3.0; `B70_SPEC_RESUME_ACCEPTED=1`). It is host-side bookkeeping and adds no
host sync.
- Before the stock `_update_states`: for each request in `prev_req_id_to_index` that this step does not schedule and
  that has not finished, it stores a device copy of `valid_sampled_token_count_gpu[previous row]`, at least 1. This
  has to happen before `_update_states`. Version 0.1.0 stored it in `_prepare_inputs`, after the request had already
  been dropped from the map, so it never acted.
- After the stock `_prepare_inputs`: for each row whose request was not in the previous step and has a stored count,
  it writes that count into `num_accepted_tokens.gpu[row]`. Finished requests and requests resumed after preemption
  drop their stored count.
- A returning request's placeholder `-1` drafts are set to 0 in `input_ids`. They are all rejected, so that step
  yields one token, as in stock.
  Tests: `experiments/qwen38-27b-b70/tests/test_b70_spec_resume_accepted.py`.

**Suggested upstream fix:** keep the count with the request instead of with the previous step's row. When
`_update_states` removes a request that is unscheduled but not finished or preempted, save its last count on its
`CachedRequestState`: the device `valid_sampled_token_count` under async scheduling, `num_accepted_tokens_cpu`
otherwise. Use the saved count instead of the default 1 when the request is re-added, and clear it on preemption or
finish. A related cost, not a correctness issue: on that first step back the request also loses its drafts, because
the placeholder drafts are all rejected.

---

## 3. The same loss in mamba_cache_mode "align" (prefix caching), where the count lives in num_accepted_tokens_cpu

**Title:** `[Bug][Spec Decode][Prefix Caching] mamba_cache_mode="align": a request that sits out one step resumes
with num_accepted_tokens_cpu = 1 (wrong block-crossing copy and starting state; garbage with MTP + 2 sequences)`

**Project:** vLLM (`vllm/v1/worker/gpu_model_runner.py`, `vllm/v1/worker/mamba_utils.py`).

**Affected, as observed:** vLLM 0.29.0 XPU fork (R314), V1 runner, async scheduling,
`--enable-prefix-caching --mamba-cache-mode align`, `--block-size 64`, MTP 5, TP2, `--max-num-seqs 2`,
`--max-num-batched-tokens 832`, `--max-model-len 262144`. The same lab overlays as in bug 2 were loaded, plus a lab
prefix-cache overlay. The same code is in v0.29.0 and main `84bcbc62` (lines below). Not run on main or on CUDA.
This is separate from bug 2: a GPU-side restore, which fixes bug 2, is overwritten in this mode.

**Mechanism (R314 lines; v0.29.0 the same except where noted):**
- In align mode, the count comes from the CPU array `input_batch.num_accepted_tokens_cpu`. After each step,
  `postprocess_mamba_align_gpu` (called at `gpu_model_runner.py:1598-1617`) copies its per-request result into that
  array (`mamba_utils.py:1634-1640`). The result is 1 for requests whose state it already moved to the block-aligned
  slot.
- Under async scheduling, align mode takes the CPU branch (`gpu_model_runner.py:2127-2132`). Counts are gathered
  through `prev_positions`, and rows that were not in the previous step get 1 (`:2134-2145`). A request that sat out
  is one of those rows (see bug 2; `add_request` also resets it, `gpu_input_batch.py:484`).
- `preprocess_mamba` uses `num_accepted_tokens_cpu[i] - 1` as the accepted-token offset when the request's state moves
  to a new block (`mamba_utils.py:1505-1523`). For a returning request, it therefore copies the state of the wrong
  verify row.
- Then the GPU count is rewritten from the CPU array (`gpu_model_runner.py:4437-4444`; v0.29.0 `:4422-4429`). That
  undoes any GPU-side restore made in `_prepare_inputs`, and the kernels start from slot 0. The call order is
  `_update_states` (`:4303`), `_prepare_inputs` (`:4346`), `preprocess_mamba` (`:4425`), the model forward, then
  `_update_states_after_model_execute` (`:4681`).
- The same code in main: `gpu_model_runner.py:1580-1601`, `:2085-2103`, `:4293-4300`;
  `mamba_utils.py:1503-1521`, `:1538`, `:1589`.

**Reproduction:** use the config above with two greedy chat requests that overlap. The second request's long prompt
(two of the four requests share a long prefix, served from the prefix cache) is read in steps the first request sits
out, and then both decode together. Compare each reply with the same request run alone. The skip comes from the same
lab pure-step overlay as in bug 2.

**Symptom (lab numbers, 36 overlapped replies over 3 rounds; every arm has the bug-1 and bug-2 fixes):**

| Server | Overlapped replies vs solo |
|---|---|
| prefix caching (align), 262K window, 832-token steps | **2 garbage, 27 of 36 different** |
| same, no prefix caching | 0 garbage, 0 different |
| prefix caching (align), 33K window, 4,096-token steps | 0 garbage, 27 different |
| no prefix caching, 33K, 4,096-token steps | 0 garbage, 0 different |
| prefix caching (align), 262K, 832, **with the fix below** | **0 garbage, 0 of 36 different** |

Solo replies matched a no-MTP reference (4/4) on the first and last servers. The failures are deterministic. The same
pair came back with the same garbage in rounds 0 and 2: `moved the mostitems, we need to counttheenumber000...`.

**Fix we used:** the align branch of the same overlay, version 0.3.0 (lab commit `eb1a8ecd9`).
- Before `_update_states`, for each request from the previous step that this step leaves out (and that has not
  finished), it waits on `num_accepted_tokens_event`, which the stock code waits on in the same step anyway
  (`:2131-2132`). Then it stores `max(1, num_accepted_tokens_cpu[previous row])`.
- After the stock `_prepare_inputs` and before `preprocess_mamba`, for a returning row with a stored count, it writes
  the count into `input_batch.num_accepted_tokens_cpu[row]`, `num_accepted_tokens.np[row]` and
  `num_accepted_tokens.gpu[row]`.
- 23 unit tests, 7 of them new, using a stub of the align bookkeeping; 0.2.0 fails 3 of the new ones.

**Suggested upstream fix:** the same per-request carry as in bug 2, but in align mode the saved count must be written
into `num_accepted_tokens_cpu` before `preprocess_mamba`. That array is both the block-crossing offset and the source
of the later GPU copy. One request-level field restored into both the CPU array and the GPU buffer covers both modes.

---

## 4. Align mode: a request that starts right after every earlier request finished inherits the last accepted count

**Title:** `[Bug][Spec Decode][Prefix Caching] mamba_cache_mode="align" + async scheduling: when every request of
the previous step has finished, the next new request reads a stale num_accepted_tokens_cpu (its prefix-cache hit
starts from the wrong state)`

**Project:** vLLM (`vllm/v1/worker/gpu_model_runner.py`, `vllm/v1/worker/gpu_input_batch.py`,
`vllm/v1/worker/mamba_utils.py`).

**Affected, as observed:** vLLM 0.29.0 XPU fork (R314), V1 runner, async scheduling,
`--enable-prefix-caching --mamba-cache-mode align`, MTP 5, TP2, `--max-num-seqs 1`, `--max-num-batched-tokens 832`,
`--max-model-len 33024`. Lab overlays as in bugs 2 and 3 (with the bug-3 fix). The same code is in v0.29.0 and main
`84bcbc62` (lines below). Not run on main or on CUDA. Separate from bug 3: it needs no request to sit out a step,
only a new request handed the engine in the step right after the last running request finished.

**Mechanism (R314 lines; main in brackets):**
- After each step the align post-process copies the per-request accepted counts into
  `input_batch.num_accepted_tokens_cpu` without waiting (`mamba_utils.py:1638-1640` [`:1589`]).
- In the next step `_update_states` removes the finished request, which also drops it from `prev_req_id_to_index`
  (`gpu_input_batch.py:573-574` [`:572`]), and `add_request` puts the new request in the freed row and writes 1
  there (`gpu_input_batch.py:484` [`:481`]). Under async scheduling the previous step's device-to-host copy can
  still be in flight at that point; it lands in the same row when `_prepare_inputs` waits on
  `num_accepted_tokens_event` (`gpu_model_runner.py:2131-2132` [`:2089-2090`]), replacing the 1 with the finished
  request's last count.
- `_prepare_inputs` repairs new rows only through the `prev_positions` branch, which runs only if
  `prev_req_id_to_index` is non-empty (`gpu_model_runner.py:2134-2146` [`:2092-2104`]). When every request of the
  previous step has finished the dictionary is empty, the "non-async" branch copies the CPU array as it is
  (`:2147-2150` [`:2105-2108`]), and the stale count goes to the GPU too.
- `preprocess_mamba` uses `num_accepted_tokens_cpu[i] - 1` as the offset of the state it copies into the new
  request's block (`mamba_utils.py:1505-1523` [`:1503-1521`]). For a request that starts from a prefix-cache hit,
  the starting recurrent state is read that many slots past the hit block: in our trace, slot 5 of the hit, which
  is a block the previous request used for a draft position.
- It needs all of: drafting, align-mode prefix caching, async scheduling, a request already waiting when the last
  running one finishes (a client that waits for each reply and then sends the next one did not trigger it in our
  tests: the engine is idle and the copy has landed before the request arrives), and a cache hit for the new
  request. With more than one sequence it needs every running request to finish in the same step.

**Reproduction:** one-sequence server as above; 64 long prompts (2K-8K tokens, 7 of 8 families share an 832-token
aligned prefix with an earlier prompt), greedy, 128 tokens. Pass 1: one at a time with a 1 s pause. Pass 2: all
submitted 30 ms apart, so each one waits in the queue and starts in the step after the previous one finishes.

**Symptom (lab numbers; every arm has the bug-1, 2 and 3 fixes):**

| Server and order | Answers equal to the paused pass |
|---|---|
| paused, suite order, repeated | 64/64 |
| paused, shuffled order | 64/64 |
| queued, suite order (two fresh servers) | **40/64** and **34/64** (all differing answers are cache hits) |
| queued, suite order, with the fix below (another fresh server) | **64/64** |
| queued, shuffled, with the fix | **64/64** |

Traced on both TP ranks (second server): of the 56 hits, the 30 whose first step read a stale count on at least one
rank all differ, and the 26 with count 1 on both ranks are all equal. The two ranks disagree in 10 of the 30: each
rank races its own copy, so one rank can start from the right state and the other from the wrong one.

**Fix we used:** overlay 0.5.0 (lab commit `54747d7d6`). After the stock `_prepare_inputs`, for rows whose request
was not in the previous step and has no stored count (new requests), when align mode is on, it writes 1 into
`num_accepted_tokens_cpu[row]`, `num_accepted_tokens.np[row]` and `num_accepted_tokens.gpu[row]` before
`preprocess_mamba`. Unit tests with a stub that lands the pending copy at the event wait: the stock code gives the
new row 4, the fix gives 1.

**Suggested upstream fix:** apply the new-row reset whatever `prev_req_id_to_index` holds (for example, take the
`prev_positions` branch whenever async scheduling is on, or set `new_mask` rows to 1 in both branches), or write the
1 of `add_request` after the event wait.

---

## Owner notes (not for posting)

- Earlier upstream posts by the lab: kernels issue #593 (filed 2026-09-12) and an evidence comment on vLLM PR #53542
  saying its hunks remove the width crash. Bug 1 qualifies that comment, so it may fit best as a follow-up on those
  two threads.
- The paths above are relative to github.com/steveseguin/b70-optimization-lab. Before posting, confirm the repo is
  public and switch to commit permalinks: `aa3cc5f00` for the bug-1 patch, overlay and tests; `114b850f9` and
  `eb1a8ecd9` for the overlay in bugs 2 and 3.
- Bugs 1-3 cite the committed overlay 0.2.0 and 0.3.0 only (a 0.4.0 with optional draft keeping is being
  tested separately and is not part of any report); bug 4 cites 0.5.0 (`54747d7d6`).
- Bug 3 residual, 2026-10-16 16:36: with 0.3.0 a 2-user drafting + prefix-caching server flipped one long answer out
  of 128 at a near tie (`notes/2026-10-04-fp8-multiuser-prereg.md`, 16:29 result). 19:35 update: the probable cause
  is bug 4 (added below, found the same evening); the two-user re-check with the bug-4 fix (arm C2) decides it.
  Settle it before filing bug 3 with a "0 of 36" claim.
- Bug 4 (2026-10-16 evening): fully explained by the both-ranks trace (prereg note, part D). Lab data:
  `experiments/qwen38-27b-b70/data/2026-10-16-r314-pcorder/`.
- Related but not drafted: R307 "Defect 3" (`docker/rebase-v0290/r307-gdn-state-handoff.py`). A one-token step right
  after a step that accepted several tokens goes to the non-spec kernels, which read slot 0. R314 is built from R304,
  not R307, so it does not carry R307's fix. Whether R314 is still affected was not checked here.
