# MiniMax M2.7 AutoRound INT4 on 4x Intel Arc Pro B70

> **Certification: `candidate-portable-repro`, not a starter guide.** Install,
> restore, launch, and validation material is closed for the lab's own hosts;
> clean-host certification is still pending. The open items are listed under
> this guide's `missing` entry in [`repro/guide-catalog.json`](../guide-catalog.json).

This folder records the reproducible path for the current quality-clean 4x B70 MiniMax result:

- Model: `Lasimeri/MiniMax-M2.7-int4-AutoRound`
- Package download pin: `1afac074ecf7c3c4504c68b83d127506f8a7e5a4`
- Engine: `vLLM 0.20.1-local`, XPU/Level Zero, tensor parallel 4
- Hardware: 4x Intel Arc Pro B70 32 GB
- Benchmark shape: prompt 512, output 1536, context 2048, batch 1
- Promoted strict mean: `89.314 output tok/s`, `119.086 total tok/s`
- Post-reboot sanity on 2026-05-20: `88.72 output tok/s`, `118.30 total tok/s`

The result did not use speculative decoding, expert dropping, a smaller model, a different quantization, or GPU power-limit changes. Quality was gated with exact token hashes and semantic canaries before the promoted benchmark was submitted to LocalMaxxing.

The historical run retained the model repository name but not its Hugging
Face snapshot revision or a complete payload manifest. The download helper now
pins the immutable revision above for future package replays; this is a
reconstruction pin, not a claim that the historical payload has been proven
byte-identical. See `manifests/model-pin.json`.

A separately measured production request at **32,264 actual prompt tokens**
and 64 output tokens produced **63.9086 decode tok/s after TTFT**, with
**23.336 s TTFT**. LocalMaxxing approved receipt
`cmpm35jsa0003rt01zghtmwip`. This is a discrete near-32K service observation,
not a value extrapolated from the 2K headline and not a controlled context
curve: the stored production observations use different output lengths. It
also carries the historical payload-identity limitation above. Evidence:
`../../data/localmaxxing-minimax-m27-prod-c1-systemd-near32k-20260526.payload.json`
and `../../docs/minimax-production-c1-service.md`.

This is the older speed-focused 2K-context repro. For the newer OpenAI-compatible server recipe that defaults to a `32768` token context window, see `../minimax-m27-b70-110tps-ubuntu24-20260523/README.md`.

## Important Caveats

The first run after a rebuild or cold compile can be misleading. On this machine, the first post-reboot pass produced only `69.33 output tok/s` because it performed fresh compilation and left only `0.57 GiB` KV cache. The immediate warm rerun hit `88.72 output tok/s` with the same command. Treat the warm run, or the strict-gated repeat average, as the comparable number.

This system currently has only 16 GB host RAM and 64 GB swap, and still reproduces the 89-class result. More system RAM is recommended for less noisy model load and fewer swap interactions, but it is not required for the promoted p512/n1536 decode benchmark.

`lspci -vv` reports the B70 links as `2.5GT/s x1` on this system while the workload and XPU topology behave normally. Record it for diagnostics, but do not reject a run only on that line.

## Folder Contents

- `configs/promoted-env.sh`: exact environment flags used for the promoted path.
- `configs/bench-89.env`: benchmark variables for p512/n1536, TP4, ctx2048.
- `scripts/00-install-system-deps.sh`: Ubuntu 24.04 system package setup.
- `scripts/01-download-model.sh`: downloads the AutoRound model.
- `scripts/02-build-stack.sh`: clones vLLM and llm-scaler, applies patches, builds the runtime.
- `scripts/03-verify-runtime.sh`: verifies XPU, vLLM, and llm-scaler import state.
- `scripts/04-run-quality-gate.sh`: runs the strict quality gate before benchmarking.
- `scripts/05-run-benchmark.sh`: runs cold plus warm throughput sanity passes.
- `scripts/06-summarize-result.sh`: extracts output tok/s, total tok/s, KV cache, and path markers from logs.
- `patches/`: generated active patch snapshots for vLLM and llm-scaler.
- `manifests/`: current machine manifest and Python package freeze.
- `results/`: promoted strict summary, LocalMaxxing payload, and post-reboot sanity results.

## Fresh Ubuntu Quick Start

Use Ubuntu 24.04.4 LTS or newer HWE kernel with the four B70s installed. A fast NVMe mounted at `/mnt/fast-ai` is assumed.

```bash
cd ~/llm-optimizations/repro/minimax-m27-b70-89tps-20260520

# System packages, Intel graphics PPA, oneAPI repo, Level Zero, xpu-smi.
sudo bash scripts/00-install-system-deps.sh
sudo reboot
```

After reboot:

```bash
cd ~/llm-optimizations/repro/minimax-m27-b70-89tps-20260520

# Optional for private/rate-limited Hugging Face downloads:
# export HF_TOKEN=<optional_huggingface_token>
bash scripts/01-download-model.sh

bash scripts/02-build-stack.sh
bash scripts/03-verify-runtime.sh
bash scripts/04-run-quality-gate.sh
bash scripts/05-run-benchmark.sh
bash scripts/06-summarize-result.sh /mnt/fast-ai/bench-results/minimax-m27-b70-89tps
```

Expected warm benchmark band:

- `87.5-90.0 output tok/s` is normal for the promoted path.
- `117-120 total tok/s` is normal for p512/n1536.
- A cold first run in the `60-75 output tok/s` range is not comparable. Rerun warm.

## Quality Gates

The promoted result passed:

- raw145 n64 exact token hash: `267cbf30208d84929ee79284ac695467f7e80597bf8694130e1e1f8b180eb5bd`
- raw145 n256 exact token hash: `58f6e8251c7a0a17e8c441278b5861f7d5da914fa1823ecd10484b296f2d7537`
- arithmetic repeat hash: `578ec378bf31cb16fb49ac5c0043270fd00a0f7898e18ac498a41ffe775d7994`
- extended sixpack hash: `1e3560554f57b2b56cec8f49f28bc8ba12e9e0ced26bdc99a976f1433c99caa7`

Do not publish a new speed result unless the exact-token gates and semantic canaries pass first.

## Current Known-Good Stack

- Kernel: `6.17.0-23-generic`
- OS: Ubuntu `24.04.4 LTS`
- GPU driver path: kernel `xe`, Level Zero
- `xpu-smi`: `1.3.6-1~24.04~ppa1`
- `intel-opencl-icd`: `26.14.37833.4-0`
- `libze-intel-gpu1`: `26.14.37833.4-0`
- `level-zero`: `1.28.2`
- oneAPI compiler used for builds: `2025.3.2`
- Python: `3.12.3`
- PyTorch: `2.11.0+xpu`
- vLLM: `0.20.1` plus local patch snapshot

See `manifests/current-system-20260520.md` and `manifests/pip-freeze-vllm-xpu-current.txt` for exact local state.

## What The Patches Do

The vLLM patch snapshot includes the promoted quality-clean changes:

- XPU graph capture with communicator capture skipped under `VLLM_XPU_GRAPH_NOOP_COMM_CAPTURE=1`.
- Clone-safe compiled allreduce custom op.
- MiniMax Q/K RMS variance helper and direct in-place scale for tiny FP32 reductions.
- llm-scaler MiniMax INT4 MoE integration and logits work-sharing path.
- MiniMax MoE output allreduce inside the custom-op boundary.
- MiniMax full MoE forward custom-op wrapper for decode-sized XPU tensors.
- Runtime guards and benchmark/quality harness improvements.

The llm-scaler patch snapshot includes the INT4 W4A16 MiniMax MoE work-sharing kernels used by the promoted path.

## LocalMaxxing Reference

Promoted submission:

- ID: `cmpct6t4m007fnw01yjdtlcs4`
- Status: `APPROVED`
- Mean output: `89.314195 tok/s`
- Mean total: `119.085594 tok/s`
