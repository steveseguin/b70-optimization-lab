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

The model weights, secrets, and full raw `/mnt/fast-ai/bench-results` tree are
not in GitHub. The repo does include scripts, patch artifacts, summarized
results, payloads, and notes needed to rebuild or review the work.

## Current Stable Mode

Production/default service mode is still:

```bash
cd /home/steve/llm-optimizations
experiments/minimax_xpu_kv_offload/scripts/switch_session_cache_profile.sh c1
```

Expected endpoint:

```text
http://0.0.0.0:8000/v1
max_model_len=32768
max_num_seqs=1
KV dtype=auto / FP16-family
```

Do not leave c2/c4/c8/TurboQuant running unless the user explicitly wants an
experiment instead of the stable endpoint.

## Current Experimental State

- c2 session-cache profile is the current known-good RAM-backed juggling mode.
  It can park/reload two long sessions that individually fit in GPU KV.
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

## Working Rules

- Keep c1 easy to restore.
- Record commands, logs, result paths, patches, and caveats.
- Put scripts and patches in GitHub whenever they are needed to reproduce a
  result.
- Do not claim c4, c8, TurboQuant, or CPU-paged attention is production-ready
  until the documented blockers are cleared.
