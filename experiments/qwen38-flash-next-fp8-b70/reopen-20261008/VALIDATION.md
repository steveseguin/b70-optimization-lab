# Screen 1b CPU validation — 2026-10-08

**67 tests passed. No GPU execution was performed.** The MTP1/4,352 candidate
is implemented but **refused by memory admission**, not certified as loadable.
All changes remain uncommitted for review on `main`.

No Docker run/pull/create, server launch or HTTP request, torch device import,
venv installation, credential access, host-setting change, branch or commit was
performed. LTX's server and port 8188 were not contacted. Existing run evidence
and concurrent LTX changes were preserved. The V30 source checkout and
`CURRENT.md` were left unchanged. Only small model metadata and bounded
safetensors headers were read, not tensor payloads.

## Executed checks

From the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
  -s experiments/qwen38-flash-next-fp8-b70/reopen-20261008 -p 'test_*.py' -v
bash -n experiments/qwen38-flash-next-fp8-b70/reopen-20261008/container-entrypoint.sh
git diff --check
```

| Suite | Tests | Coverage |
| --- | ---: | --- |
| `test_memory_plan.py` | 38 | Decimal GB/GiB arithmetic, exact ceiling/reserve boundaries, phase maxima, unknowns, no double counting, generic parameter order/overshoot, bounded header/index parsing, observed memory completeness, config/source/launch/overlay drift, final versus preliminary admission |
| `test_overlay_cpu.py` | 18 | Complete temporary V30 tree from pinned Git objects: apply, installed hashes, idempotence, drift refusal before writes; module imports and PLE local/global coverage, bounded copies, broadcast scales, cancellation, signal races, receipt failures |
| `test_watchdog.py` | 6 | 250 ms threaded polling, both trip points, next-allocation arithmetic, missing observations, receipt failure, one trip receipt |
| `test_cpu.py` | 5 | Existing controller contract, fault signatures, disk refusal, mocked failed-client cleanup, watchdog/cleanup sharing exactly one SIGINT |
| **Total** | **67** | **All passed** |

Also passed: AST parsing of **49 Python files** (40 overlay files plus nine
packet Python files), shell syntax, whitespace checks, and the final MTP1
`screen.py run --mode mtp1 --dry-run`. The dry run printed the prediction table
and command without executing Docker, connecting to any endpoint, inspecting
GPU processes or modifying files.

System Python has no `torch` module (`importlib.util.find_spec('torch')` returned
`None`). Import smoke tests load the actual ported `ngram_embedding.py`, common
PLE and UVA modules with explicit torch/vLLM/Triton stubs, and load the guard
with torch unavailable. They exercise coverage/copy contracts but cannot test
native XPU pointer, stream, allocator or kernel behavior. The LTX venv was not
imported or modified.

## Fit result and exactness boundary

The final [prediction receipt](host-memory-prediction.json) is bound to the
current launch and overlay manifest. MTP1, TP4+EP, maximum length 4,352:

- Final generic pins: **70,494,044,160 bytes** (PLE included once).
- Note-based planning peak: **92,237,316,096 bytes / 92.237316 GB**.
- Qualified `Hpred`: **unknown**, because runtime/lifetime bounds are unknown.
- Static VRAM lower bound: **28.040000 GiB/card**; complete peaks remain unknown.
- Status: **REFUSED**. Host ceiling is 90 GB; reserve is four GiB on every card.

The numerical peak uses the note's explicitly assumed 12+4+4 GiB overhead and
256 MiB bounded staging. It is neither measured RSS nor a certified upper
bound. The 25-cap arithmetic sweep from 12 to 18 GiB/rank finds no joint fit
under those allowances. Even ideal row placement needs at least 28.560915 GiB
per card under the host ceiling, before omitted runtime costs. **Final v5 is
therefore omitted: it cannot alone solve this total-memory conflict.** A lower,
evidenced overhead bound or another lossless reduction is still needed.

Fused GDN remains unchanged. Exact 2K/4K output pins, native UVA correctness,
actual load fit, cancellation latency, fresh-server determinism and speed were
not tested. Matching those pins later would qualify those fixture streams only;
a miss would not isolate GDN from other changed arithmetic. No quality pass,
performance improvement or community boost is claimed.

## Files for review

Changed packet files:

- [README.md](README.md), this `VALIDATION.md`, [runtime-notes.md](runtime-notes.md).
- [screen.py](screen.py), [container-entrypoint.sh](container-entrypoint.sh),
  [overlay-manifest.json](overlay-manifest.json), [test_cpu.py](test_cpu.py).

New packet files:

- [apply_overlay.py](apply_overlay.py).
- [memory_plan.py](memory_plan.py), [memory-bounds.json](memory-bounds.json),
  [host-memory-prediction.json](host-memory-prediction.json).
- [memory_watchdog.py](memory_watchdog.py).
- [test_memory_plan.py](test_memory_plan.py),
  [test_overlay_cpu.py](test_overlay_cpu.py), [test_watchdog.py](test_watchdog.py).

New `overlay/` tree: **40 pinned Python files**, exhaustively listed in
[overlay-manifest.json](overlay-manifest.json). Thirty preserve the existing
Screen 1 Lumnus bytes. These ten carry the lab port relative to that source:

```text
vllm/model_executor/model_loader/base_loader.py
vllm/model_executor/model_loader/default_loader.py
vllm/model_executor/model_loader/weight_utils.py
vllm/model_executor/offloader/uva.py
vllm/models/qwen4_exp/common/ple.py
vllm/models/qwen4_exp/nvidia/ngram_embedding.py
vllm/screen1b_guard.py
vllm/v1/engine/core.py
vllm/v1/executor/multiproc_executor.py
vllm/v1/utils.py
```

Attribution: wu1ff/Lumnus Python changes remain pinned at
`9d79d28d7e32f33bdbd115c85d116583ce679cb6`, official V30 base at
`ced6857afa0ea7b2e3f0846a62e1394e90f15607`. Direct PLE, coverage and loading
semantics derive from this lab's certified lossless-MTP1 patch series; the
current port and CPU tests are lab follow-up. The repository-local
[review-model-contribution skill](../../../.agents/skills/review-model-contribution/SKILL.md)
governed source/provenance review. No publication or external communication
was performed.
