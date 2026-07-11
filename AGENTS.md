# Agent Notes

This repository is a reproducible lab notebook and deployment guide for Intel
XPU local AI work across multiple B70 model efforts: MiniMax, Qwen, Gemma, and
future lanes.

## First Read

Read these in order before changing runtime behavior:

1. `CURRENT.md`
2. Current lane `HANDOFF.md` and result packet linked from `CURRENT.md`
3. `README.md`
4. `docs/current-reproducibility-map.md`
5. `docs/model-optimization-guide.md`
6. `AGENT_HANDOFF.md`
7. `docs/model-effort-index.md`
8. `docs/local-ops.md`
9. `docs/localmaxxing.md`
10. A model packet, for example
   `results/gemma4-26b-a4b-q8-b70/HANDOFF.md`,
   `results/gemma4-26b-a4b-q8-b70/README.md` and
   `results/gemma4-26b-a4b-q8-b70/reproduce.md`.

The model weights, secrets, and full raw `/mnt/fast-ai/bench-results` tree are
not in GitHub. The repo does include scripts, patch artifacts, summarized
results, payloads, and notes needed to rebuild or review the work.

Use these common folders consistently:

- `notes/` for chronological experiment notes, including negative results.
- `patches/` for patch snapshots and source-level deltas.
- `data/` for structured run summaries, payloads, responses, and logs that are
  reasonable to track.
- `results/` for promoted or summarized model result packets.
- `scripts/` for reusable harnesses and submission helpers.
- `experiments/` for active research lanes that are not production recipes.
- `repro/` for runnable promoted reproduction recipes.

## Local Secrets

Never print, paste, or commit local credentials. The Hugging Face access token
for model downloads is stored outside the repo at:

```text
/home/steve/.config/huggingface/token
```

Scripts that need faster Hugging Face downloads should read this file into
`HF_TOKEN` locally. The token file is covered by repo and global Git ignores.

LocalMaxxing credential guidance is in `docs/localmaxxing.md`; the key itself
is outside Git at `/home/steve/.config/localmaxxing/api_key` or supplied as
`LMX_API_KEY`. Never print or commit it.

The local sudo password file is `/home/steve/SUDOPASSWORD.txt`; local privileged
operations guidance is in `docs/local-ops.md`. Use it only for local driver,
runtime, service, or recovery tasks that truly require sudo. Never print or
commit the password or a copy of the file.

## Live State Authority

`CURRENT.md` is the sole cross-repository authority for the loaded service,
active optimization lane, protected work, and immediate next actions. Detailed
evidence remains in the lane handoff and result packet linked from that file.

Do not infer what is live from a deployable recipe, old handoff, service unit,
historical note, or result packet. Verify Git status, relevant processes, and
the actual endpoint before operational changes. Preserve any paths marked
active or protected in `CURRENT.md`; do not disturb shared runtime trees or GPU
work merely because another lane has a runnable recipe.

## Quality Rules

Never promote a speed or context result unless quality is labeled and tested.

Use exact-token, semantic, arithmetic, and practical task gates where relevant.
Compressed KV modes such as FP8 KV or TurboQuant must be labeled separately
from the FP16-family baseline.

For Gemma/Qwen speculative-decoding results, diagnostic sweeps may use
synthetic or repetitive prompts, but promotion and LocalMaxxing submissions now
require the fixed realistic final gate:

- use the fixed realistic prompt suite;
- run each prompt once as a cold first response;
- require `cached_tokens=0` for every request;
- disable prompt/KV cache reuse, context checkpoints, response reuse,
  n-gram/history acceleration, and warmed repeated prompts;
- keep the target model and quantization unchanged;
- allow speculative decoding/MTP only when accepted tokens are verified by the
  declared target model;
- report median tok/s for generated tokens 1-100 after TTFT across the suite as
  the primary metric, plus p10, mean, TTFT, wall tok/s, full 512-token tok/s,
  prompt/output hashes, model identity, runtime commit, env vars, flags, and
  logs.

The current Gemma 4 26B A4B Q8 one-B70 realistic-suite best is:

- result packet: `results/gemma4-26b-a4b-q8-b70/README.md`;
- reproduction: `results/gemma4-26b-a4b-q8-b70/reproduce.md`;
- standalone current repro:
  `repro/gemma4-26b-a4b-q8-b70-125tps-20260701/README.md`;
- realistic suite: `repro/gemma4-26b-a4b-q8-b70/realistic-suite-v1.json`;
- best strict cold-suite result:
  `124.97714084813418 tok/s` median generated-token throughput for tokens
  1-100 after TTFT, `cached_tokens=0` on every prompt,
  `realistic_final_gate.passed=true`;
- evidence:
  `data/gemma4-q8-gpu0-finalpostnorm-reproexact-full512-20260701T084728Z/summary.json`;
- latest same-recipe doc-pass rerun:
  `data/gemma4-q8-gpu0-125repro-docpass-20260702T231635Z/summary.json`
  at `120.92334534956485 tok/s`, valid/fresh/cached-zero with `512/512`
  canary rows; support only, not a new record;
- config:
  llama.cpp `c926ad098`, reordered-Q8 VDR2, Q4_0 MTP draft,
  `FLASH_ATTN=on`, `CTX_SIZE=32768`, `GGML_SYCL_ENABLE_VMM=1`,
  `n_max=3`, `n_min=2`, `p_min=0.0475`, `UBATCH_SIZE=1024`,
  `LLAMA_SYCL_F16_P021_SMALL_NCOLS=1`,
  `LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1`,
  `LLAMA_GEMMA4_MOE_FUSED_DOWN_WEIGHTED_SUM_REORDER_VDR2=1`,
  `LLAMA_GEMMA4_FUSED_FINAL_POST_NORM_RESIDUAL=1`;
- representative / submitted status:
  the VDR2 selected-down fused weighted-sum path plus FA-on 32K/VMM plus final
  post-norm residual fusion is the current policy-compliant LocalMaxxing
  submission, approved as `cmr1u77na01k2ld01kalwzs1e`. Same-family support
  includes the prior `123.67689864739785 tok/s` row
  (`cmr01nnet000mld01x2tt6qds`), the prior `121.41411987308553 tok/s` row
  (`cmqztiqdn02vnoe01egox6q3f`) and
  `data/gemma4-q8-gpu2-baseline-recordconfirm-full512-20260629T225215Z/summary.json`
  at `119.94842631460949 tok/s`. The prior selected-down repeat
  `cmqyrpox4021dqk01co5o4fcw`, initial selected-down confirmation
  `cmqyo0jyt08ippk01vhiobdnm`, VDR2/F16-p021 row
  `cmqxchyra03xmqr01b963gmi1`, F16-p021 small-ncols submission
  `cmqx3687103v4qr01ace1ft3m`, earlier VDR2 rows, and prior VDR4 rows are
  superseded;
- current clean no-spec control:
  `data/gemma4-q8-gpu0-vdr4default-nospec-realistic-gate-v2-20260627T165335Z/summary.json`
  at `74.29709476830473 tok/s` median. Use it as the simplest target-side
  quality/control reference.

The previous Gemma 4 26B A4B Q8 one-B70 diagnostic best is:

- result packet: `results/gemma4-26b-a4b-q8-b70/README.md`;
- reproduction: `results/gemma4-26b-a4b-q8-b70/reproduce.md`;
- synthetic filled-long row0: `176.21623213048554 tok/s` after TTFT,
  `176.40259133127742` support mean, 1536 canary repeats / 6144 rows,
  LocalMaxxing `cmqwkedg303jeqr013z753j62`, now classified as diagnostic until
  the fixed realistic prompt suite passes with that configuration;
- target/verifier: UD-Q8_K_XL, Q4_0 MTP draft only; do not promote lower
  precision/QAT/Q4XL side-lane results as this Q8 headline.

## Working Rules

- Keep c1 easy to restore.
- Record commands, logs, result paths, patches, and caveats.
- Put scripts and patches in GitHub whenever they are needed to reproduce a
  result.
- Do not claim c4, c8, TurboQuant, or CPU-paged attention is production-ready
  until the documented blockers are cleared.
- Preserve experiment patches and their results, including failed patches, so
  future agents do not rediscover the same dead ends. Promote successful
  patches only after verification, while keeping the experiment record linked.
- Commit regularly with focused commits and explicit paths. Do not use broad
  `git add -A` in mixed experiment worktrees.
- When a verified realistic-suite run breaks a real LocalMaxxing record for a
  matching 1/2/3/4 GPU configuration, submit it with model, quantization, GPU
  count, mode, run identity, throughput, correctness status, prompt/output
  hashes, and supporting artifact links. Do not submit warmed/history,
  synthetic-only, or lower-precision side-lane results as the Q8/INT8 headline.

## Cross-Agent Delegation

When Claude/OpenCode is orchestrating work, prefer delegating concrete research,
audit, patch, and validation tasks to Codex/GPT through the CLI. GPT token use
is less constrained here, so Claude/OpenCode should manage/review and ask Codex
to do bulky searches, source reading, and iteration-heavy implementation where
practical.

Useful forms:

```bash
codex --cd /home/steve/llm-optimizations
codex exec --cd /home/steve/llm-optimizations "audit the Gemma docs and propose focused cleanup"
codex review --cd /home/steve/llm-optimizations
codex resume --last
```

Codex should use subagents whenever reasonable and available, especially for
parallel source audits, independent review of risky changes, log/result
classification, and research synthesis. The main Codex agent still owns final
edits, verification, and safety around active experiment processes.
