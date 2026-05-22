# Codex Agent Handoff

Last updated: 2026-05-22

This file is the first thing a new Codex agent should read when continuing the
Intel Arc Pro B70 LLM optimization work.

## Current Objective

Primary target:

- MiniMax M2.7 INT4 AutoRound on 4x Intel Arc Pro B70 32GB.
- Preserve answer quality while improving single-session decode, context,
  prefill, and eventually concurrent-session throughput.
- Do not use power-limit or overclocking changes as optimization paths.

Secondary targets:

- Qwen3.6 27B Q4_0 GGUF and FP8 on B70.
- MiniMax M2.7 GGUF remains useful as a capacity/quality comparison but is not
  the current speed path.

## Current Promoted MiniMax State

Current validated structured-output fast lane:

- Model: `Lasimeri/MiniMax-M2.7-int4-AutoRound`
- Hardware: 4x Intel Arc Pro B70 32GB
- Engine: local vLLM/XPU `0.20.1-local`, TP4
- Backend stack: Level Zero/XPU, llm-scaler INT4 MoE kernels, forced XPU graph
  with communicator capture no-op
- Task: constrained simple HTML, `skeleton_status_html`
- Result: `94.406 tok/s` effective accepted output, `94.692 tok/s` post-first
- Quality gate: `30/30` accepted, `0` rejects, `100%` first-attempt pass
- LocalMaxxing: `cmphg048s00mppc0192sahyug`
- Note: `notes/2026-05-22-minimax-structured-fast-lane-regex2.md`
- Payload: `data/localmaxxing-minimax-m27-autoround-structured-regex2-20260522.payload.json`

Important caveat:

- This is a constrained structured-output lane. It does not prove unconstrained
  free-form website generation is clean on the forced XPU graph path.
- Structured JSON cross-check passed `9/9` with `0` rejects at `87.956 tok/s`
  and stable parsed JSON hashes.

Current older strict long-run MiniMax baseline:

- p512/n1536, ctx2048, batch 1
- Result: `89.314195 tok/s` output, `119.085594 tok/s` total
- LocalMaxxing: `cmpct6t4m007fnw01yjdtlcs4`
- Repro folder: `repro/minimax-m27-b70-89tps-20260520/`

## Quality Rules

Do not promote a speed result unless quality is preserved.

For low-level MiniMax performance changes, use the strict gates already in the
repo:

- raw145 exact token hashes at n64 and n256
- semantic canaries
- arithmetic repeat
- extended sixpack

For practical task lanes:

- validate generated output structurally, not just token speed
- count rejected attempts against effective throughput
- keep raw outputs and result JSON under `/home/steve/bench-results/...`
- label constrained-output results as constrained; do not present them as
  unconstrained general generation quality

## Key Repro Paths

Start here on a fresh machine:

- `repro/minimax-m27-b70-89tps-20260520/README.md`
- `repro/minimax-m27-b70-89tps-20260520/scripts/00-install-system-deps.sh`
- `repro/minimax-m27-b70-89tps-20260520/scripts/01-download-model.sh`
- `repro/minimax-m27-b70-89tps-20260520/scripts/02-build-stack.sh`
- `repro/minimax-m27-b70-89tps-20260520/configs/promoted-env.sh`
- `repro/minimax-m27-b70-89tps-20260520/patches/`

Important notes:

- The repro folder is for the `89 tok/s` strict baseline, not the latest
  `94 tok/s` constrained HTML lane.
- The latest structured regex2 fix is recorded as a patch in
  `patches/minimax-website-structured-regex2-20260522.patch`.
- The active local lab checkout still contains a richer current website-quality
  harness at
  `/home/steve/llm-optimizations-publish/scripts/run-minimax-website-task-quality.py`.
  If cloning elsewhere, verify the repo copy of that script has the same
  feature set before trying the regex2 command.

## Known Good Runtime Shape

Typical promoted environment flags include:

```bash
source repro/minimax-m27-b70-89tps-20260520/configs/promoted-env.sh
unset VLLM_XPU_CUDAGRAPH_PARTITION_COLLECTIVES || true
unset VLLM_XPU_CUDAGRAPH_STATIC_INPUT_COPY || true
```

For the structured HTML fast lane:

```bash
python scripts/run-minimax-website-task-quality.py \
  --mode graph \
  --prompt-format chat \
  --assistant-prefill skeleton_open \
  --task skeleton_status_html \
  --warmup-runs 1 \
  --repeat 30 \
  --retry-until-pass 5 \
  --max-tokens 96 \
  --max-model-len 4096 \
  --max-num-batched-tokens 512 \
  --enable-prefix-caching \
  --structured-skeleton-regex
```

Expected regex2 result class:

- `30/30` accepted
- `0` rejected attempts
- output throughput around `94 tok/s` after warmup on matching hardware

## What Is Not Fully Solved

- Unconstrained free-form website output on the forced XPU graph path can still
  corrupt or degrade. Keep validating practical tasks.
- JSON structured lanes are better than free-form but can run below the HTML
  fast lane; use parsed JSON validation and count retries.
- Concurrency 2 is not ready. Prior c2 graph/no-graph attempts hit stalls or
  Torch XPU indexing assertions.
- Larger prefill chunks such as 1024 tokens can trigger Intel `ocloc`/IGC
  compiler failures on this stack; keep `max_num_batched_tokens=512` unless
  testing that specifically.
- Generic in-place allreduce thresholds were usually slower. Favor exact
  shape/dtype fusion with quality proof.

## Optimization Directions

Best next work:

- Expand validated practical tasks while keeping the 90+ tok/s lane.
- Build reliable prefill/context measurements without lowering decode quality.
- Debug c2/concurrency failures with small two-request repros.
- Continue lower-level fusion only where math is exactly preserved:
  Q/K variance allreduce plus RMS apply, hidden allreduce plus residual/RMSNorm,
  MoE output plus epilogue, and final projection/lm-head boundaries.
- Mine llm-scaler for ideas, but require strict quality gates before promotion.

Avoid:

- claiming constrained decode as unconstrained quality
- comparing AutoRound INT4 as equivalent to Q4_0/FP8 without separate quality
  checks
- disabling clones/allreduces broadly without exact shape and quality proof
- power tuning as the explanation for speed

## GitHub And LocalMaxxing

Use the GitHub connector path for publishing, not local shell auth.

Significant benchmark results should be submitted to LocalMaxxing with payloads
and responses recorded under `data/`.

Recent important LocalMaxxing IDs:

- MiniMax structured regex2: `cmphg048s00mppc0192sahyug`
- MiniMax strict p512/n1536 high: `cmpct6t4m007fnw01yjdtlcs4`
- JSON gated c1 practical task: `cmpgv9p9j007qpc01oq5zqhdg`
- JSON c1 2k-context follow-up: `cmpgx0yrb009fpc0183xjri4j`

## Models Expected On Disk

Main models of interest:

- `Lasimeri/MiniMax-M2.7-int4-AutoRound`
- Qwen3.6 27B Q4_0 GGUF
- Qwen3.6 27B FP8
- MiniMax M2.7 GGUF/UD-IQ4_XS for comparison

The model weights themselves are not in GitHub. Use the repro download scripts
and local Hugging Face cache conventions from the repro folder.
