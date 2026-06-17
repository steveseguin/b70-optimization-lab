# Plan: >150 tok/s Single-Session Decode, No Quality Loss

Date: 2026-06-17
Target model: `nameistoken/Qwen3.6-35B-A3B-Quark-W8A8-INT8` on 4x Intel Arc Pro B70
Goal: **>150 tok/s single-session decode (prefer >200), zero quality loss.**
Current validated safe base: **93.55 tok/s** (10.69 ms/token), PIECEWISE forced-comm graph lane.

This plan is the output of an exhaustive 2026-06-17 investigation. Every
faster-looking alternative has been measured and ruled out (see
`notes/2026-06-16-qwen36-current-handoff.md` 2026-06-17 addenda). The only
remaining architecture with a real >150 ceiling is **EAGLE speculative
decoding with a lightweight trained draft**, plus a required verifier
correctness fix.

## Why EAGLE (and why everything else is closed)

Measured evidence on this exact machine:

| Lever | Result | Mechanism that closes it |
|---|---|---|
| Fused-prologue MoE | device-lost at capture | systemic PIECEWISE capture failure (any enabled layer) |
| Shared-expert stream overlap | 73.77 tok/s (-21%) | no XPU multi-stream concurrency; fork/join overhead unhidden |
| Fused-act-quant | 91.85 tok/s + canary fail | fused kernel is bit-exact correct but path is slower + replay-nondeterministic |
| n-gram spec | 48 tok/s on diverse prompts | 0% acceptance on non-repetitive text |
| MTP hybrid spec | 83 tok/s (k=3), canaries fail | draft is a full MoE+GDN layer (~10ms/step); bonus/parity bug unfixed |
| **EAGLE (thin draft)** | **not yet built** | **only path with a real >150 ceiling** |

Validated positive: a learned draft matched to this target already achieves
**60-88% acceptance** (hybrid MTP, k=1). So the prediction problem is
solvable here; the only issue is that the MTP draft is too heavy. EAGLE
replaces it with a 1-2 layer, no-MoE draft (~10-20x cheaper per step).

Speed math (from measured forward costs): with a ~1ms EAGLE draft and the
~20ms amortized 6-token verifier forward (measured on the n-gram k=5
graph-none run), acceptance length 3-4 at k=3-5 yields **~150-200 tok/s**.

## Architecture decision

- **EAGLE-1 first** (simpler), EAGLE-3 as a later upgrade.
- EAGLE-1 draft = shared target embedding + **1 lightweight decoder layer
  (standard attention, no MoE, no GDN)** + shared target lm_head. Input is
  the target's last hidden state + last token; output is next-token logits.
- Train on XPU with **plain PyTorch (no DeepSpeed)** - the SafeAILab/EAGLE
  trainer is CUDA/DeepSpeed-only; the draft is tiny so single-device plain
  training is sufficient and avoids the DeepSpeed-XPU blocker.
- The draft must be trained on the **Quark INT8 target's** hidden states
  (not the official FP8's) so it matches the production verifier.

---

## Phase 0 - Fix the verifier bonus/parity bug (REQUIRED, parallel track)

Needed for **any** spec method to be quality-clean (EAGLE included). The
verifier's packed spec rows produce tokens that diverge from the no-spec
baseline. Disabling the bonus token did NOT fix it (k=3 no-bonus: both
canaries still fail), so the bug is deeper than the bonus row.

**Root cause (per `2026-06-14-qwen36-recovery-implementation.md:4584-4857`):**
the packed target+bonus row uses a different effective GDN recurrent/conv
state than the next ordinary decode row. First natural divergence is at
output index 17 (no-spec emits 11436, spec emits 321).

**Steps:**
1. Capture per-layer GDN state for both no-spec and spec at the first
   divergent verifier row, using the existing trace infra:
   `VLLM_XPU_GDN_TRACE_FILE=...jsonl`, `VLLM_XPU_GDN_TRACE_LAYER_REGEX`,
   and the oracle harness (`scripts/run-qwen36-oracle-parity-gate.sh`,
   `scripts/launch-qwen36-quark-int8-oracle-trace.sh`) which feeds a
   perfect draft so only the verifier is exercised.
2. Compare `conv_state` / `ssm_state` slots for the bonus row vs the
   matching no-spec decode row at the divergent layer (layer 0 trace
   already exists: `data/qwen36-oracle-k1-smallcap-gdntrace-*`).
3. Identify the off-by-one / wrong-base-state in the spec row state
   propagation in `vllm/model_executor/layers/mamba/gdn_linear_attn.py`
   (spec path ~lines 1179-1463: `spec_state_indices_tensor`,
   `accepted_state_indices`, the serial-spec-decode loops gated by
   `VLLM_XPU_GDN_SERIAL_SPEC_*`). Prior serial-state-copy attempts
   (m18-m26) moved the divergence later but did not fix it - the fix must
   be at the state transaction, not another preempt/margin heuristic.
4. Validate with `scripts/run-qwen36-oracle-parity-gate.sh` until
   `check-qwen36-oracle-fixture.py --mode exact` passes (token-identical
   to no-spec).

**Done when:** oracle k=1 (and k=2) is token-identical to the no-spec
baseline on the parity fixture.

---

## Phase 1 - Custom hidden-state extractor (GDN target -> EAGLE training data)

vLLM's `extract_hidden_states` method is a runtime KV-cache proposer, not a
data exporter, so a custom extractor is required. vLLM (not HF
transformers) must run the target, because only vLLM supports the Qwen3.5
GDN arch.

**Steps:**
1. Write `scripts/extract-qwen36-eagle-data.py` that:
   - Loads the Quark INT8 target via the vLLM `LLM` class (TP=4, same
     identity as the 93.55 base: PIECEWISE not required for data-gen, but
     `VLLM_XPU_QUARK_W8A8_MOE=1`, GDN fallbacks, etc. must match so the
     hidden states reflect the production model).
   - Registers a forward hook on the target's **final hidden state**
     (input to `lm_head`) to capture per-token hidden states.
   - Runs the corpus (Phase 1.5) with **greedy** decoding.
   - For each sequence, saves `(hidden_states[num_tokens, hidden],
     input_ids[num_tokens], next_token_ids[num_tokens])` in EAGLE's
     expected `.bin`/torch format (see `EAGLE/eagle/data/` and
     `EAGLE/eagle/traineagle3/configs.py` for the exact layout).
2. Validate the extractor on a tiny corpus (10 samples): confirm saved
   hidden-state shapes/dtypes and that
   `lm_head(hidden_state[i])` argmax == `next_token_ids[i]` (the target's
   own greedy token). This guarantees the labels are self-consistent.

**Phase 1.5 - Corpus:** EAGLE ships corpora under `EAGLE/eagle/data/`
(alpaca, gsm8k, humaneval, mt_bench, qa, sum). Use a mix weighted toward
the intended deployment distribution; ~10k-50k samples is typical for
EAGLE-1 convergence.

**Done when:** a training dataset of (hidden_state, token, next_token)
tuples is saved on disk and passes the self-consistency check.

---

## Phase 2 - Train the EAGLE-1 draft on XPU (plain PyTorch, no DeepSpeed)

**Steps:**
1. Port `EAGLE/eagle/traineagle3/main.py` (or the simpler
   `EAGLE/eagle/train/main.py`) to a single-device plain-PyTorch XPU
   trainer:
   - Replace `deepspeed` init with a plain `torch.optim.AdamW` loop.
   - Replace every `.cuda()` / `torch.cuda.*` with `.xpu()` / `torch.xpu.*`
     (mechanical; the draft is small so memory fits on one B70).
   - Keep the EAGLE-1 loss (feature + token prediction) and the draft
     architecture (`eagle/model/cnets.py`, `modeling_eagle.py`): embedding
     + 1 decoder layer + lm_head, all lightweight.
   - Share the target's embedding and lm_head weights with the draft
     (vLLM does this at load time too, so train with them shared/frozen
     per EAGLE convention).
2. Train on the Phase-1 dataset. EAGLE-1 typically converges in a few
   hours on a single device for a 1-layer draft.
3. Save the trained draft in vLLM's EAGLE format: an `EConfig`
   (`eagle/model/cnets.py` `EConfig`) + the draft `safetensors`, matching
   how vLLM's `EagleProposer` loads via `--speculative-config
   {"method":"eagle","model":"<draft-path>"}`.

**Done when:** a draft checkpoint loads in vLLM via `method:eagle` without
error and produces non-trivial acceptance (>30%) on a smoke prompt.

---

## Phase 3 - Integrate + load the EAGLE draft in vLLM

**Steps:**
1. Confirm vLLM's EAGLE proposer is target-arch-agnostic (it is: it passes
   the target's final hidden state to the draft via
   `pass_hidden_states_to_model=True`). The GDN target is handled by vLLM;
   the draft only consumes hidden states.
2. Launch with the full safe identity + EAGLE:
   ```
   MODEL_PATH=<Quark INT8 target>
   --speculative-config '{"method":"eagle","model":"<draft-path>","num_speculative_tokens":3}'
   --compilation-config '{"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":128}'
   ```
   plus the standard XPU graph + GDN fallback flags (see the "Current Safe
   Fast Identity" in the handoff) and `VLLM_XPU_HOLD_SPEC_DECODE_WHEN_WAITING=1`.
3. Use `scripts/run-qwen36-ablation-candidate.sh` with `SERVER_LAUNCHER`
   pointing at an eagle-aware launcher (mirror of
   `launch-qwen36-quark-int8-ngram-trace.sh` but `method:eagle`).

**Gotchas already solved (apply):**
- Always set `COMPILATION_CONFIG` to PIECEWISE+cg128 explicitly; the
  accepted launcher defaults to graph-NONE (~15 tok/s trap; see
  `AGENTS.md` identity rule).
- Quote `--speculative-config` JSON through `VLLM_EXTRA_ARGS` directly
  (the hybrid-mtp launcher's `SPEC_CONFIG` path double-appends a brace).
- `VLLM_XPU_GRAPH_NO_EMPTY_CACHE=1` if any aux stream is used (capture
  fix committed this session, `897bcfe81`).

**Done when:** the EAGLE server reaches readiness and the canaries run.

---

## Phase 4 - Tune k and validate against the goal

**Steps:**
1. Sweep `num_speculative_tokens` k = 2, 3, 4, 5. For each, run the full
   `run-qwen36-ablation-candidate.sh` pipeline (metrics + json/color
   canaries + quality suite with `ABLATION_RUN_QUALITY=1`).
2. Pick the k that maximizes speed subject to **all gates passing**
   (json 96/96, color 96/96, quality `pass_all` + `baseline_match_all`).
   Phase 0 must be complete or no spec run will pass canaries.
3. Confirm acceptance length and per-position acceptance from the server
   `SpecDecoding metrics` log line (target: acceptance length >= 3 for
   >150 with a cheap draft).

**Success criteria (the goal):**
- `tok_s_out_corrected_mean >= 150` (prefer >200) on the standard
  `natural-chat` p512/o512 metric.
- json-canary 96/96, color-canary 96/96.
- quality-suite `pass_all=true`, `baseline_match_all=true` (incl. 8K
  long-context).
- Full benchmark identity recorded in the summary (model/quant/TP,
  COMPILATION_CONFIG, graph flags, GDN flags, speculative-config,
  draft-model path/revision, k).

**Promotion rule (from `AGENTS.md`):** only promote if it beats 93.55 AND
passes all gates; first diff run identity + launcher logs against the safe
base if speed changes unexpectedly.

---

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| GDN hidden-state extraction is awkward in vLLM | Forward hook on `lm_head` input; validate with the self-consistency check (Phase 1.2) before scaling |
| EAGLE trainer XPU port has subtle bugs | Start from the simpler `eagle/train/main.py` (EAGLE-1); unit-test the draft forward on XPU before training |
| Draft acceptance too low (FP8/INT8 hidden-state mismatch is irrelevant here - draft trained on INT8 states directly) | Train on the INT8 target's own states; raise k or add a 2nd draft layer if acceptance <50% |
| Parity bug (Phase 0) resists fixing | This is the prior author's stuck point; budget real time, use the GDN trace infra, fix the state transaction not heuristics |
| Higher k triggers the k>=2 MTP-style slowdown | That slowdown was MTP-draft-cost; EAGLE's thin draft should not exhibit it - validate per-k forward cost early |
| vLLM EAGLE + GDN capture interaction | `VLLM_XPU_GRAPH_NO_EMPTY_CACHE=1`; fall back to cg128 / smaller k if capture fails |

## Effort estimate

- Phase 0 (parity fix): the hard, uncertain-duration item; days.
- Phase 1 (extractor): ~0.5-1 day code + hours of target data-gen.
- Phase 2 (training): ~0.5 day code + hours of training.
- Phase 3/4 (integrate + tune): ~1 day.

This is a multi-day build. It is feasible on this machine (XPU training via
plain torch; GitHub + corpora reachable; vLLM EAGLE proposer present) and
is the only measured-viable route to >150 with no quality loss.

## Concrete identity reference (copy from the 93.55 base + spec)

```bash
COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE","max_cudagraph_capture_size":128}'
XPU_GRAPH=1
VLLM_XPU_ENABLE_XPU_GRAPH=1
VLLM_XPU_FORCE_GRAPH_WITH_COMM=1
VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1
VLLM_XPU_GDN_NATIVE_FALLBACK=prefill
VLLM_XPU_GDN_PREFILL_RECURRENT_FALLBACK=1
VLLM_XPU_DISABLE_PREFILL_CUDAGRAPH_REPLAY=1
VLLM_XPU_GREEDY_SAMPLE_TOPK_FALLBACK=1
VLLM_XPU_INT8_MOE_MIXED_WORKSPACE=1
GPU_MEMORY_UTILIZATION=0.95
VLLM_XPU_HOLD_SPEC_DECODE_WHEN_WAITING=1
VLLM_EXTRA_ARGS='--speculative-config {"method":"eagle","model":"<draft-path>","num_speculative_tokens":3}'
```

## Session artifacts already delivered (committed)

- `llm-optimizations 9e6d70e`: `SERVER_LAUNCHER` runner option, identity
  recorder, full investigation findings in the handoff.
- `vllm 897bcfe81`: `VLLM_XPU_GRAPH_NO_EMPTY_CACHE` capture bug-fix.
- Hybrid MTP checkpoint built at `/mnt/fast-ai/qwen36-quark-int8-fp8-mtp-hybrid`
  (validated 60-88% acceptance; useful as a draft-quality reference).
- EAGLE training repo cloned at `/home/steve/src/EAGLE` (untracked).

## 2026-06-17 verifier repair update

Current blocker narrowed:

- Native XPU GDN prefill now mirrors the running prefill state into speculative
  state slots after `torch.ops._xpu_C.gdn_attention`. This fixed the earlier
  zero-state first speculative row.
- Remaining divergence is not just a scheduler/accounting issue. A no-spec run
  forced through the Python/Triton GDN decode fallback diverged from native
  GDN at output token 25. This means the speculative verifier path was using a
  recurrent decode kernel that is not token-equivalent to the native safe
  baseline.

Patch in progress:

- `/home/steve/src/vllm/vllm/_xpu_ops.py` now has an env-gated
  `VLLM_XPU_GDN_NATIVE_SPEC_DECODE=1` path.
- The path serializes decode-only speculative GDN slots through the native
  `_xpu_C.gdn_attention` kernel, copying conv/SSM state rows between speculative
  slots so k=1 verifier rows use the same native recurrent math as ordinary
  decode.
- This is correctness-first and expected to be slow until it passes oracle
  parity. If it passes, optimize by collapsing the per-slot native calls or
  adding native multi-slot speculative support.

Next gate:

- Run oracle k=1 exact parity against
  `data/qwen36-nospec-current-eager-tp2-20260617i-candidate.json` with
  `VLLM_XPU_GDN_NATIVE_SPEC_DECODE=1`.
- If exact parity fails, compare the new `post_native_spec_decode` row trace
  against native no-spec `forward_post_core` for the first divergent layer and
  fix the remaining state-slot/promotion mismatch.

## 2026-06-17 verifier repair update 2

Important bug found:

- The first `VLLM_XPU_GDN_NATIVE_SPEC_DECODE=1` implementation was unreachable.
  `_xpu_ops.py` had an earlier unconditional
  `if attn_metadata.spec_sequence_masks is not None: self._forward_core(...);
  return` before the native-spec branch.
- This produced misleading repeated failures where the env flag was present
  but the generic Python/Triton spec path still ran.
- Fix: only take that early return when native spec decode is not requested.

New candidate runs:

- `qwen36-oracle-k1-native-specdecode-eager-tp2-20260617v/w`
  still used the unreachable path; first diff stayed at output index 22
  (`198` expected, `271` actual).
- `qwen36-oracle-k1-native-specdecode-singlestate-eager-tp2-20260617y`
  reached the native branch. Full 32 tokens returned, first diff still index
  22. Layer-0 state after a two-token verifier row matched no-spec after only
  the first token, proving the serial native decode path emitted the bonus row
  but did not advance GDN state for it.
- `qwen36-oracle-k1-native-specdecode-singlestate-sync-eager-tp2-20260617z`
  added `torch.xpu.synchronize()` between native serial spec steps. No change;
  first diff stayed index 22. The issue is not simple host-visible ordering.
- `qwen36-oracle-k1-serialgdn-sourcezero-eager-tp2-20260617aa` tested the
  generic Python serial conv+recurrent path with source-offset-zero. Worse:
  first diff index 7. Do not pursue that combination for this fixture.
- `qwen36-oracle-k1-native-specprefillseq-eager-tp2-20260617ab` submitted the
  verifier target+bonus row to native GDN as a two-token prefill-style sequence
  with initial state. This is the best result so far: first diff moved to
  output index 25 (`63520` expected, `3074` actual). It fixes the immediate
  bad bonus at index 22, but still corrupts later state/promotion.

Current best repair candidate:

- Continue from `VLLM_XPU_GDN_NATIVE_SPEC_PREFILL_SEQUENCE=1`.
- The first remaining divergence is no longer the immediate verifier bonus;
  it appears after several accepted/full-bonus rows and subsequent normal
  decode. Inspect layer traces at output index 25, especially promotion from
  the final spec slot back into the running slot (`running_state_source_indices_tensor=[2]`).
- Likely next fix: the prefill-sequence path mirrors final state from slot 1
  to slot 2 after each verifier row, but normal decode promotion may still use
  wrong conv/SSM timing or the wrong source after full-bonus emission.
- Do not promote any speed result until oracle k=1 exact parity passes.
