# 2026-07-05 - ReplaySSM S=4/cache=8 native kernel screen

## Summary

We extended the native XPU ReplaySSM spec-decode dispatch to cover the Qwen27
MTP3 shape (`max_spec_len=4`, `max_cache_len=8`). This fixes the immediate
performance cliff where MTP3 ReplaySSM fell through to the torch fallback at
about `5 tok/s`, but the endpoint path is still not correct or fast enough to
promote.

Classification: useful lower-level milestone, **not a valid result**, **do not
submit to LocalMaxxing**.

## Patch / Build Artifacts

- XPU kernel patch:
  `patches/qwen36-27b-autoround-int4-b70/vllm-xpu-kernels-replayssm-s4-cache8-native-20260705.patch`
- vLLM dispatch / metadata patch:
  `patches/qwen36-27b-autoround-int4-b70/vllm-replayssm-s4-cache8-python-dispatch-and-metadata-20260705.patch`
- Rebuilt runtime library:
  `/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/_xpu_C.abi3.so`
- Rebuilt library sha256:
  `8546859eaa840de83240ad836a9259af4e2f054512ce15eb17c7304fe5c35dfa`
- Previous runtime library backup:
  `/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/_xpu_C.abi3.so.backup-before-replayssm-s4-20260705T0916Z`

The narrow build command used the existing `_xpu_C` loop:

```bash
KERNELS_DIR=/home/steve/src/vllm-xpu-kernels \
VENV_DIR=/home/steve/.venvs/vllm-xpu \
ONEAPI_VARS=/opt/intel/oneapi/compiler/2025.3/env/vars.sh \
AOT_DEVICES=bmg-g21-a0 \
JOBS=4 \
GDN_KERNELS=ON \
INSTALL_PREFIX=/tmp/vllm-xpu-xpu-c-only-20260705-replayssm-s4 \
/home/steve/llm-optimizations/scripts/build-vllm-xpu-kernels-xpu-c-only.sh
```

The full editable `pip install -e .` path failed before compiling because
`setup.py` looked for `/home/steve/.venvs/vllm-xpu/bin/icpx`; the actual oneAPI
compiler is under `/opt/intel/oneapi/compiler/2025.3/bin/icpx` and
`/opt/intel/oneapi/compiler/2026.0/bin/icpx`. Use the existing build script
instead of the full editable path for this kernel.

## Op-level Smoke

A direct XPU op-level comparison of native S=4/cache=8 against the torch
fallback matched:

- `out`: max abs diff `0.0`
- `checkpoint_state`: `0.0`
- `d_cache`: `0.0`
- `k_cache`: `0.0`
- `g_cache`: `1.1920928955078125e-07`

This proves the new native template dispatch is buildable and agrees with the
current torch reference on a small controlled shape.

## Same-window Endpoint Screen

All rows used:

- `webhie/Qwen3.6-27B-int4-AutoRound`
- runtime INT8 LM-head with BF16 scales
- MTP3 / `max_cudagraph_capture_size=8`
- `VLLM_XPU_GDN_REPLAYSSM_SPEC=1`
- `VLLM_XPU_GDN_REPLAYSSM_SPEC_CACHE_LEN=8`
- `VLLM_XPU_GDN_REPLAYSSM_TORCH_FALLBACK=0`
- fixed Qwen realistic suite, each prompt once, `cached_tokens=0`
- short quality screen: repeat8, long-context skipped for speed

Results:

| Label | Median tok/s | Gate | Quality | Main failure |
| --- | ---: | --- | --- | --- |
| `qwen27-exactdraft-replayssm-s4native-promote0post1` | `23.839` | pass | fail | arithmetic `67. . of 60`; JSON `{"answer": 42` |
| `qwen27-exactdraft-replayssm-s4native-promote1post0` | `24.358` on 11 rows | fail | fail | one prompt too short for metric; same arithmetic/JSON failures |
| `qwen27-draftint4-replayssm-s4native-promote0post1` | `25.795` on 9 rows | fail | fail | JSON `{"answer": 42, "unit: "widgets"}`; repeat failed |
| `qwen27-draftint4-replayssm-s4native-promote1post0` | `26.561` on 11 rows | fail | fail | JSON `{"answer": 42, "unit: "widgets"}`; repeat failed |

Artifacts:

- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-exactdraft-replayssm-s4native-promote0post1-candidate-summary-20260705T0925S4NATIVE.json`
- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-exactdraft-replayssm-s4native-promote1post0-candidate-summary-20260705T0925S4NATIVE.json`
- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-draftint4-replayssm-s4native-promote0post1-candidate-summary-20260705T0925S4NATIVE.json`
- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-draftint4-replayssm-s4native-promote1post0-candidate-summary-20260705T0925S4NATIVE.json`

## Interpretation

The native S=4/cache=8 path removes the torch fallback bottleneck:

- previous ReplaySSM MTP3 fallback rows: about `4.6-5.2 tok/s`;
- native S=4/cache=8 rows: about `24-27 tok/s`.

That is a real 5x local improvement for this experimental path, but it is far
below the current valid `65.276 tok/s` record and the quality failures show the
ReplaySSM transaction is still wrong for endpoint use.

The exact-draft controls failing is the important signal: this is not just
draft-INT4 approximation error. The target-owned MTP draft itself falls to very
low effective acceptance under ReplaySSM and fails arithmetic/JSON canaries.
The problem is therefore in GDN/ReplaySSM transaction semantics or metadata,
not merely the approximate draft head.

## Follow-up: native stage-conv window fix

The deterministic exact-draft failures were isolated to the native
`gdn_replayssm_stage_conv` op, not recurrent ReplaySSM, graph capture, or
post-verify commit. A four-way fallback matrix showed:

| stage conv | recurrent ReplaySSM | Result |
| --- | --- | --- |
| native | native | failed arithmetic / JSON |
| torch fallback | native | passed short quality |
| native | torch fallback | failed the same way |
| torch fallback | torch fallback | passed short quality |

Root cause: the native stage-conv kernel read negative-relative-position
history from the physical tail of `conv_state` (`state_len + rel_pos`). Qwen
GDN conv state can have one extra physical column, while the Python fallback
and pending-state commit both treat the active causal-conv history as the first
`Width - 1` columns. The fix changes native stage conv to read
`(Width - 1) + rel_pos`.

Patch artifact:

- `patches/qwen36-27b-autoround-int4-b70/vllm-xpu-kernels-replayssm-s4-cache8-stageconv-window-fix-20260705.patch`

Rebuilt installed `_xpu_C.abi3.so`:

- sha256 `9dde12dbcfe30cf6439590f9e32da93d22e83c9d8bbfb7a07c2b84c88c6058f3`
- previous S4 build backup:
  `/home/steve/src/vllm-xpu-kernels/vllm_xpu_kernels/_xpu_C.abi3.so.backup-before-stageconv-window-fix-20260705T135909Z`

Direct op microcheck with `state_len=5`, `Width=4`, and valid slot `1`
matched the first-window reference within BF16 rounding:

- `q_max_abs=0.0068888664`
- `k_max_abs=0.01491642`
- `v_max_abs=0.002262473`
- pending/a/b exact (`0.0`)

Endpoint validation after the patch:

| Label | Flags | Quality | Strict fresh median | Gate | Interpretation |
| --- | --- | --- | ---: | --- | --- |
| `qwen27-replayssm-s4-stagefix-native-nograph` | graph off, promote0/post1 | short pass | not run | n/a | proves deterministic bug is fixed without graph |
| `qwen27-replayssm-s4-stagefix-graph` | graph on, promote0/post1 | short pass | `57.794 tok/s` | pass, cached-zero | correct but below record |
| `qwen27-replayssm-s4-stagefix-promote-graph` | graph on, promote1/post0 | short pass | `58.405 tok/s` | pass, cached-zero | correct but below record |

Artifacts:

- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-replayssm-s4-stagefix-native-nograph-quality-20260705T140231Z.json`
- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-replayssm-s4-stagefix-native-graph-quality-20260705T140422Z.json`
- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-replayssm-s4-stagefix-native-graph-realistic128-chat-tokenids-qwensuite-20260705T140457Z.json`
- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-replayssm-s4-stagefix-promote-graph-quality-20260705T140849Z.json`
- `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-replayssm-s4-stagefix-promote-graph-realistic128-chat-tokenids-qwensuite-20260705T140909Z.json`

Final classification: the stage-conv patch is a real correctness fix for the
experimental ReplaySSM S4/cache8 native path and should be preserved, but the
lane is not a Qwen27 record candidate. It remains `~7 tok/s` below the current
`65.276 tok/s` webhie/BF16-scale INT8-LM-head MTP3/cg8 record even after the
quality fix. Do not submit these rows to LocalMaxxing. Future ReplaySSM work
should start from this patch, but the current route to `100+ tok/s` must attack
verifier cost and/or accepted tokens per target step rather than more
ReplaySSM endpoint sweeps.
