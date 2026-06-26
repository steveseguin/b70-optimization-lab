# Agent Notes

This repository is a reproducible lab notebook and deployment guide for Intel
XPU local AI work across multiple B70 model efforts: MiniMax, Qwen, Gemma, and
future lanes.

## First Read

Read these in order before changing runtime behavior:

1. `README.md`
2. `docs/current-reproducibility-map.md`
3. `AGENT_HANDOFF.md`
4. `docs/model-effort-index.md`
5. `docs/local-ops.md`
6. `docs/localmaxxing.md`
7. Current lane packet, for example
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

## Current Stable Mode

Production/default service mode is still:

```bash
cd /home/steve/llm-optimizations
systemctl status minimax-vllm.service --no-pager
scripts/minimax-prod-health.py
```

Expected endpoint:

```text
http://0.0.0.0:8000/v1
frontdoor auth=none
backend=http://127.0.0.1:18080
max_model_len=32768
max_num_seqs=1
KV dtype=auto / FP16-family
```

The newer generic service shape is a single active model slot:

```bash
scripts/switch-vllm-model-slot.sh list
scripts/switch-vllm-model-slot.sh status
scripts/switch-vllm-model-slot.sh switch minimax-m27-c1
```

It keeps the same public LAN endpoint, but changes which backend model is
loaded. Do not run two large model services at once. See
`docs/model-slot-switching.md`.

Tracked service/install files:

- `deploy/systemd/minimax-vllm.service`
- `deploy/systemd/minimax-openai-frontdoor.service`
- `deploy/systemd/b70-vllm-slot.service`
- `deploy/systemd/b70-openai-frontdoor.service`
- `scripts/install-minimax-vllm-service.sh`
- `scripts/install-vllm-model-slot-service.sh`
- `scripts/switch-vllm-model-slot.sh`
- `scripts/serve-vllm-profile.sh`
- `scripts/run-openai-frontdoor-profile.sh`
- `scripts/openai-lan-frontdoor.py`
- `scripts/minimax-prod-health.py`
- `scripts/minimax-prod-benchmark.py`

Do not leave c2/c4/c8/TurboQuant running unless the user explicitly wants an
experiment instead of the stable endpoint.

## Current Experimental State

- c2 session-cache profile is the current known-good RAM-backed juggling mode.
  Treat it as two parked `32768`-token window sessions. The `22.5K` fact-word
  run is only an operations smoke; the near-full strict ladder passed two
  `32474`-prompt-token sessions.
- c4/c8 are research profiles. They produced useful ladder results, but live
  c4 service switching later hit a waiting/deferred stall and a Level Zero
  `UR_RESULT_ERROR_DEVICE_LOST`.
- TurboQuant is mechanically past the first XPU workspace crash with the local
  patch, but it is much slower and not production-quality-equivalent yet.
- None of these modes provide one true `196608` active context. Full active
  context requires the CPU-paged attention path documented in the experiment
  notes.

## Quality Rules

Never promote a speed or context result unless quality is labeled and tested.

Use exact-token, semantic, arithmetic, and practical task gates where relevant.
Compressed KV modes such as FP8 KV or TurboQuant must be labeled separately
from the FP16-family baseline.

For Gemma/Qwen speculative-decoding results, headline throughput must be a
fresh response: no usable prior generated continuation, repeated-output
history, prefix/cache reuse, response reuse, context checkpoint reuse, or
warmed n-gram memory from earlier benchmark repeats. Report first-request
fresh throughput separately from warmed/cached throughput. Draft-model,
MTP, verifier-based speculation, and n-gram speculation are acceptable only
when the draft source can operate on a fresh request without already seeing the
target continuation.

The current Gemma 4 26B A4B Q8 one-B70 record is:

- result packet: `results/gemma4-26b-a4b-q8-b70/README.md`;
- reproduction: `results/gemma4-26b-a4b-q8-b70/reproduce.md`;
- fresh row0: `103.2992004295621 tok/s` after TTFT, `102.19335537277364`
  support mean, 1536/1536 canary, LocalMaxxing `cmqsylo2l011nqr011yydjvne`;
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
- When a verified fresh run breaks a real LocalMaxxing record for a matching
  1/2/3/4 GPU configuration, submit it with model, quantization, GPU count,
  mode, run identity, throughput, correctness status, and supporting artifact
  links. Do not submit warmed/history or lower-precision side-lane results as
  the Q8/INT8 headline.

## Cross-Agent Delegation

When Claude/OpenCode is orchestrating work, prefer delegating concrete research,
audit, patch, and validation tasks to Codex/GPT through the CLI. GPT token use
is less constrained here, so Claude/OpenCode should manage/review and ask Codex
to do bulky searches, source reading, and iteration-heavy implementation where
practical.

Useful forms:

```bash
codex --cd /home/steve/qwen36-results-main
codex exec --cd /home/steve/qwen36-results-main "audit the Gemma docs and propose focused cleanup"
codex review --cd /home/steve/qwen36-results-main
codex resume --last
```

Codex should use subagents whenever reasonable and available, especially for
parallel source audits, independent review of risky changes, log/result
classification, and research synthesis. The main Codex agent still owns final
edits, verification, and safety around active experiment processes.
