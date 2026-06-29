# Agent Notes

This repository is a reproducible lab notebook and deployment guide for Intel
XPU local AI work, centered on MiniMax M2.7 INT4 AutoRound on 4x Intel Arc Pro
B70.

## First Read

Read these in order before changing runtime behavior:

1. `README.md`
2. `docs/current-reproducibility-map.md`
3. `AGENT_HANDOFF.md`
4. `repro/minimax-m27-b70-110tps-ubuntu24-20260523/README.md`
5. `experiments/minimax_xpu_kv_offload/REPRODUCE.md`
6. [docs/localmaxxing.md](docs/localmaxxing.md) before submitting or editing LocalMaxxing payloads.
7. [docs/qwen36-research-map.md](docs/qwen36-research-map.md) before changing Qwen3.6 runtime behavior.
8. [docs/local-ops.md](docs/local-ops.md) before driver/runtime, service, sudo, or cross-agent orchestration work.

The model weights, secrets, and full raw `/mnt/fast-ai/bench-results` tree are
not in GitHub. The repo does include scripts, patch artifacts, summarized
results, payloads, and notes needed to rebuild or review the work.

## Repo Structure Pointers

Use the standard folders so future agents can find work quickly:

- [notes/](notes/) ([README](notes/README.md)): chronological experiment notes, including losses and inconclusive
  results.
- [patches/](patches/) ([README](patches/README.md)): patch snapshots, source deltas, and failed-patch records that
  should not be lost.
- [data/](data/) ([README](data/README.md)): structured run summaries, LocalMaxxing payloads/responses, small
  logs, and benchmark artifacts that are reasonable to track.
- [results/](results/): promoted or summarized result ledgers.
- [scripts/](scripts/): reusable harnesses, parsers, service helpers, and submission
  helpers.
- [experiments/](experiments/): active research lanes that are not production recipes yet.
- [repro/](repro/): promoted reproduction recipes that should be runnable by another
  person or agent.
- [docs/](docs/): human-facing maps, deployment docs, and policy pages.

For LocalMaxxing, use [docs/localmaxxing.md](docs/localmaxxing.md) as the credential/submission
source of truth. The API key is outside Git at
`/home/steve/.config/localmaxxing/api_key`; the helper also accepts
`LMX_API_KEY`. Never print, paste, or commit the key.

For privileged local operations, use [docs/local-ops.md](docs/local-ops.md).
The sudo password file is outside Git at `/home/steve/SUDOPASSWORD.txt`. Never
print, paste, or commit it. The repo and user global Git ignore files exclude
that filename and common password-file variants.

When Claude/OpenCode is managing work, prefer delegating bulky research,
audits, implementation, and validation loops to Codex/GPT through the Codex
CLI. Useful forms are `codex --cd /home/steve/llm-optimizations`,
`codex exec --cd /home/steve/llm-optimizations "<task>"`, `codex review --cd
/home/steve/llm-optimizations`, and `codex resume --last`. Codex should use
subagents whenever reasonable and available, especially for parallel source
audits, log/result classification, and independent review of risky changes.

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

## Benchmark Identity Rule

For Qwen 3.6 35B XPU work, never compare benchmark results until the complete
run identity is checked. A prior failure omitted
`COMPILATION_CONFIG='{"cudagraph_mode":"PIECEWISE"}'`; the launcher defaulted
to graph-none and produced `~15 tok/s`, which was wrongly interpreted as a
fast-lane regression. Before changing code or making conclusions, diff model,
quantization, TP/PP, graph mode, GDN mode, forced-comm flags, GPU memory
utilization, async scheduling, sampler fallbacks, and diagnostic flags against
the known-good baseline.

## Working Rules

- Keep c1 easy to restore.
- Record commands, logs, result paths, patches, and caveats.
- Put scripts and patches in GitHub whenever they are needed to reproduce a
  result.
- Keep experiment patches and their results together. Successful patches should
  be promoted after verification; failed patches should stay archived unless a
  clearly linked fix supersedes them.
- Commit focused, reproducible state regularly with explicit path staging. Do
  not use broad `git add -A` in mixed experiment worktrees.
- Do not claim c4, c8, TurboQuant, or CPU-paged attention is production-ready
  until the documented blockers are cleared.
