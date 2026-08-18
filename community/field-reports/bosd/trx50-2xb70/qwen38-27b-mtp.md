# Qwen3.8-27B: MTP works out-of-the-box on Intel vLLM-XPU (one B70)

> **Evidence: `community-reported`; not run in the reference lab.** One host,
> one configuration, greedy short-context (MTP best case). Sibling of
> [`mtp-vllm-xpu-flip.md`](mtp-vllm-xpu-flip.md), which established the
> backend-swap MTP result on Qwen3.6-27B.

> **Maintainer note (2026-08-17):** inspection confirms that the named image
> supports `qwen3_5_mtp` and that the Qwen3.8 checkpoint has an MTP head. The
> reported +55% arithmetic is also correct. The performance was not
> independently reproduced from raw logs, however, and lower acceptance does
> not establish that Intel had not tuned the checkpoint or that the entire
> Qwen3.6/Qwen3.8 difference is in the draft path. Also,
> `CCL_ZE_IPC_EXCHANGE=sockets` selects socket-based Level Zero IPC handle
> exchange; it is not by itself proof of a PCIe P2P defect.

Pinned contributor write-up:
[`results/mtp-spec-decode-b70.md`](https://github.com/bosd/trx50-arc-b70-benchmarks/blob/64df816/results/mtp-spec-decode-b70.md).

## Why this test

`Qwen/Qwen3.8-27B` was released 2026-08-14. Intel's LLM-Scaler does **not** list
it as a supported model (the support matrix stops at Qwen3.6-27B / -35B-A3B).
The open question: does the `qwen3_5_mtp` speculative method work on it anyway,
given it is the same `qwen3_5` architecture family? It does.

## Reported setup

- One Arc Pro B70 (32 GB), ASRock TRX50 WS, Threadripper 9960X, Fedora 44,
  kernel 7.1.8, `xe`.
- `intel/llm-scaler-vllm:0.21.0-b3.1` (vLLM-XPU, torch 2.11.0+xpu), podman.
- `Qwen/Qwen3.8-27B` — 52 GB BF16, `qwen3_5` GatedDeltaNet arch, 64 layers,
  **carries the MTP head** (15 `mtp.*` keys in the weight index).
- Online INT4 (`--quantization sym_int4`, ~18 GB on-GPU), single B70
  (`ZE_AFFINITY_MASK=1`), `-tp 1`, `--max-model-len 8192`.
- One request stream, 512 generated tokens (`ignore_eos`), temperature 0.
- MTP via `--speculative-config '{"method":"qwen3_5_mtp","num_speculative_tokens":2}'`.

## Reported measurements

| Config | decode tok/s | draft acceptance |
| --- | ---: | --- |
| MTP-off | **28.9** | — |
| MTP-on | **~44.9** | **~61%**, mean accept-len 2.21 |

Mean of 3 measured 512-token runs after one warm-up (28.89 / 28.95 / 29.00 off;
43.81 / 43.99 / 46.76 on). Server logs `Detected MTP model. Sharing target model
embedding/lm_head weights with the draft model` — the head loads cleanly.

**MTP = +55%.** Same INT4/single-B70 recipe on Qwen3.6-27B gave +80% at ~74%
acceptance; Qwen3.8-27B's acceptance is lower (~61%), consistent with Intel not
having tuned the newer checkpoint. The MTP-*off* rate is identical to 3.6 (same
arch/size), so the difference is entirely in the draft path.

## Caveats (contributor)

- Best case for MTP: greedy (temp 0), short prompt (context depth ~0). Expect
  erosion with sampling and long context (see the depth table in the pinned
  write-up).
- `num_speculative_tokens=2`; not swept.
- Single host, 3 repeats, metrics from `vllm:spec_decode_*`; no full raw log
  directory published beyond the quoted acceptance numbers.

## Multi-GPU follow-up (updates the tp=2 note in `mtp-vllm-xpu-flip.md`)

`-tp 2` across both B70s on this stack now runs **end-to-end through engine
warmup** — weights shard to **9.12 GiB/card**, the **xccl/oneCCL** collective
backend initializes (world_size=2), KV cache allocates, and "init engine
(profile, create kv cache, warmup model)" completes (~37 s), i.e. the cross-GPU
collectives execute. Two fixes were needed: `CCL_ZE_IPC_EXCHANGE=sockets`
(the two B70s are PCIe-connected with no XeLink, so default P2P IPC hangs at the
first collective) and lowering `--gpu-memory-util` to 0.80 with
`--max-num-batched-tokens 4096` (0.9 reserved all VRAM for KV and OOM'd the
warmup activation). Remaining rough edge: the **APIServer↔EngineCore handshake
stalls** after warmup (no `startup complete`, HTTP never serves) — single-GPU
has no such issue, so it reads as a tp>1 front-end bug in b3.1, not a
compute-layer failure. This is a different multi-GPU stack from the llama.cpp
`-sm layer` path (ggml-org/llama.cpp#23797), which SIGABRTs immediately.
