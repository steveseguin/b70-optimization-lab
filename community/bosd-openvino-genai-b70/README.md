# OpenVINO GenAI on Intel Arc Pro B70 (Battlemage)

> **Maintainer note (2026-10-23).** The reference lab re-ran this entry on one
> of its own B70s: OpenVINO GenAI 114.7 tok/s and a fresh llama.cpp-SYCL 99.5
> tok/s, both within 2% of the numbers below, so the throughput claims are
> `B70-verified`. One addition the contributor did not report: the first greedy
> generation of a fresh OpenVINO pipeline decodes differently from every later
> one, deterministically. Status and the lab's own records are in
> [`STATUS.md`](STATUS.md) and [`validation/`](validation/).

---

> **Community submission — not reproduced in the reference lab.**
> Read [`STATUS.md`](STATUS.md) first. All numbers below are contributor
> measurements on the contributor's hardware (2× Arc Pro B70, Fedora 44,
> kernel 7.2.10, host Level-Zero 1.33.1).

Intel's first-party **OpenVINO GenAI** runtime runs LLM inference on the Arc
Pro B70 through its Level-Zero GPU plugin — no oneAPI `setvars`, no `torch`,
no conversion step when you feed it a pre-converted INT4 IR. On a single B70
it decodes **Qwen2.5-7B INT4 at ~113 tok/s single-stream**, at the card's
memory-bandwidth roofline. A **current** llama.cpp-SYCL build reaches ~98.6
tok/s on the same card/model, so the engine gap is only ~15%.

## Headline numbers (1× B70, Qwen2.5-7B, single-stream)

| Engine / build | Decode tok/s | Prefill pp512 |
| --- | --- | --- |
| OpenVINO GenAI 2026.4.1, INT4, no-spec | **~113** (tech 114 / code 112) | — (TTFT 18–84 ms) |
| OpenVINO GenAI, INT4 + 1.5B draft spec (k=5) | 98.6 prose / 128.2 code | — |
| llama.cpp-SYCL **fresh** (`970b51c`, 2026-10-22, `-fa`) | **98.6 ± 0.3** (tg256) | 3528 ± 28 |
| llama.cpp-SYCL stale (`5aba5364d`, 2026-06-01) | 13.2 | 1083 |

**The stale build is the trap:** an 8× "win" for OpenVINO evaporates once
llama.cpp is rebuilt from current master. Rebuild before comparing.

## Reproduce (OpenVINO GenAI)

```bash
# 1. Env — system Python 3.14 has no OV wheels; use 3.12
uv venv --python 3.12 ~/ov-genai
uv pip install --python ~/ov-genai/bin/python openvino openvino-genai huggingface-hub

# 2. Confirm the B70s are visible (no setvars needed)
~/ov-genai/bin/python - <<'PY'
import openvino as ov
c = ov.Core()
print(c.available_devices)
for d in c.available_devices:
    if d.startswith("GPU"):
        print(d, c.get_property(d, "FULL_DEVICE_NAME"))
PY
# -> GPU.0 Arc Pro B60, GPU.1 / GPU.2 Arc Pro B70

# 3. Pull pre-converted INT4 IRs (main + a spec draft)
~/ov-genai/bin/hf download OpenVINO/Qwen2.5-7B-Instruct-int4-ov  --local-dir ~/ov-models/qwen25-7b-int4
~/ov-genai/bin/hf download OpenVINO/Qwen2.5-1.5B-Instruct-int4-ov --local-dir ~/ov-models/qwen25-1.5b-int4

# 4. Bench (pin to a B70 via the device string)
~/ov-genai/bin/python reported/ov-bench.py both
```

`reported/ov-bench.py` targets `GPU.1`. Change the `DEV` constant to pick a
different card. Spec-decode is enabled by constructing the pipeline with
`draft_model=openvino_genai.draft_model(DRAFT, DEV)` and setting
`num_assistant_tokens` on the `GenerationConfig`.

> Note: `pipe.generate(str, cfg)` returns a bare string. Pass a **list**
> (`pipe.generate([prompt], cfg)`) to get a `DecodedResults` with
> `perf_metrics` (throughput / TTFT / TPOT).

## Reproduce (llama.cpp-SYCL baseline)

```bash
# Build CURRENT master — a stale build will badly understate decode
git clone --depth 1 https://github.com/ggml-org/llama.cpp ~/llama-fresh
source /opt/intel/oneapi/setvars.sh --force
cmake -B ~/llama-fresh/build -S ~/llama-fresh \
  -DGGML_SYCL=ON -DGGML_SYCL_DNN=OFF -DGGML_SYCL_F16=ON -DGGML_SYCL_GRAPH=ON \
  -DCMAKE_C_COMPILER=icx -DCMAKE_CXX_COMPILER=icpx -DCMAKE_BUILD_TYPE=Release
cmake --build ~/llama-fresh/build --target llama-bench -j

# Same B70, same model as Q4_K_M
ONEAPI_DEVICE_SELECTOR=level_zero:1 ~/llama-fresh/build/bin/llama-bench \
  -m Qwen2.5-7B-Instruct-Q4_K_M.gguf -sm none -mg 0 -ngl 99 -fa 1 -p 512 -n 256 -r 6
```

(`-DGGML_SYCL_DNN=OFF` because oneDNN isn't bundled with the oneAPI compiler
package here; install `intel-oneapi-dnnl*` if you want it on.)

## Caveats

- **Dense Qwen2.5-7B, not the GDN/MoE `qwen3_5` models** the B70 serving
  stacks actually deploy. optimum-intel's OV exporter likely can't convert
  `Qwen3_5ForConditionalGeneration` yet (not attempted here). This is an
  engine datapoint on a dense model, not a drop-in for the serving stack.
- **Single-stream only.** No batched/concurrent (serving) throughput measured.
- The contributor's **deployed** llama.cpp endpoints use tuned B70 SYCL kernels
  (~+4% over upstream) that build only `llama-server`; the 13 tok/s stale build
  was a stray dev build, **not** a deployed endpoint.

## Files

- `STATUS.md` — structured evidence record (classification, environment, findings, open questions).
- `reported/ov-bench.py` — the OpenVINO GenAI harness (no-spec + spec arms, `perf_metrics`).
- `reported/results.md` — raw run output.
