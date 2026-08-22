# Cookbook family hub — reported measurements (snapshot 2026-08-21)

Evidence level: `community-reported`. Numbers are the cookbook's own
measurements (one Arc Pro B70, C1, median of n=5, client monotonic SSE timing,
entropy-first cold prefixes unless a row says otherwise). Several cells cite
LocalMaxxing run IDs; those are leaderboard-reported. Maintainer notes at the
end are the only lab voice in this file.

## Model family hub (as reported)

| Family | Engine | Headline |
| --- | --- | --- |
| Qwen3.6-35B-A3B | vLLM XPU (Pi digest) | MTP4 p512/g128 **170.91** client post-first n=5; native MTP 1/2/4, 128K |
| Qwen3.8-27B | vLLM XPU (nightly digest) | Dense GPTQ-INT4 + MTP4, optional draft-INT4: C1 **106.7** (`cmt03mj040eh8ms01trjvhm75`); cache-off **112.65** (`cmszpqy000e8fms014ty6i5x3`); BF16-draft 83.7 (`cmsur82fz06svms01ga1f0z83`). Concurrent mixed-split v5 + draft-INT4, prefix on: C5 realistic **127.4 Σ-streams / 25.5 per-user** (`cmt03mjo60ehbms0117c5i745`), short-prompt C5 203.8 / C32 224.2, C32 Σ-streams 903 |
| Qwen3.6-27B | vLLM XPU (same digest) | Dense GPTQ-INT4 + MTP, fp8 KV: MTP4 p512/g128 **69.30** n=5 |
| Nemotron-3.5-Lightning-30B-A3B | vLLM XPU (newer digest) | **DFlash** n=7: **186.61** C1 client post-first p2048/g128 n=5; native MTP 0% |
| Muse-Glimmer-30B | llama.cpp SYCL | 26.8 engine tok/s p512/g128 128K n=5; vision + DFlash n2 |
| Ornith-1.5-35B-A3B | vLLM XPU | Self-reported: 230 W combined LMX 108.4 / prefill 9073 (`cmt2tdx5q0hy0mv01koh4xwpw`); host p512/g128 106.64; BF16-draft MTP1 150 W 96.43 |

## Reported stack pins (Qwen3.6 family)

- Image `vllm/vllm-openai-xpu@sha256:2c427ef477da092eb6f2cdbbbd24950b5fa171565b916db69d4c7bb10e68ca97`;
  vLLM `0.26.1rc1.dev457+gc810e5ee9.xpu`; vllm-xpu-kernels `0.1.12`
  (0.1.12.2 exists on PyPI, untested in that campaign).
- Patches, in order: `patch_mtp_nightly.py`, then `patch_mtp_boundary.py`.
- Dense 27B at 128K **requires fp8 KV** (fp16 KV needs ~9.5 GiB and does not fit).
- Tool-calling flags required for agent clients (`--enable-auto-tool-choice --tool-call-parser qwen3_coder`).

## Reported scheduler/context findings (2026-08-09 probes)

- `--max-num-batched-tokens` is a cap, not a target: at p4096, budget 16,384
  vs 8,192 gave **+17.6% prefill, +12.0% decode** at identical recipe — a
  scheduler/memory-layout effect, not chunk count. Caveats stated by the
  author: head-of-line starvation of short requests; activation VRAM spikes
  (128K recipe loads with ~1 GB free).
- Prefill is flat across context (8K/16K/32K/128K within noise at p4096).
- Full-context decode acceptance collapses with depth: at p130944/g128,
  MTP1 89.22%, MTP2 85.81%, MTP4 66.91%; at g512 MTP4 59.81%. Workload
  guidance: MTP4 for short C1, MTP2 at exact 128K, **no-spec for mixed
  long-prefill + short-chat loads** (MTP mixed-token XPU path unsupported).
- Prefix reuse largely fails at C5 on the concurrent build (0–38% hits vs 91%
  at C1) — warm-session TTFT at Cn flagged by the author as an open issue.

## Claim-audit precedent (as reported)

A 12,400 tok/s LocalMaxxing prefill claim was **not reproduced**: exact
hash-verified checkpoint and config gave 7,740 t/s median; the claim's cited
build hash `568afb3a1` was an upstream macOS-CI commit, and the entry ran on
Windows 11 vLLM 0.26.1.dev0 vs their Linux rc1 stack.

## Windows 11 kits (as reported)

Docker Desktop kit ~70 tok/s class (2026-08-18 BF16-draft measure); Microsoft
WSLC kit 2.4–2.8× slower, experimental. Kits reserve GPU memory for the
Windows desktop (gpu-memory-utilization 0.75 + explicit 4.25 GiB fp8 KV).

## Maintainer notes

- **Run `cmszpqy000e8fms014ty6i5x3` (the cache-off 112.65 cell) was audited by
  this lab on 2026-08-21 for public source/delta**: no public payload exists —
  the LocalMaxxing run page 404s, guessed API endpoints return 404/405, and no
  public repo/diff names the claimed `patch_draft_mtp_int4.py`. Treat that cell
  as leaderboard-reported, not source-inspectable.
- The hub's Qwen3.8 cells are measured on the cookbook's pinned nightly-digest
  image, not on this lab's pinned stack, and use the cookbook's GPTQ-INT4
  checkpoints; this lab's quality posture on Qwen3.8 GPTQ targets is the
  existing entry's
  [2026-08-16 quality/KV-dtype decision](../../../sergiiob-qwen38-27b-vllm-xpu/validation/2026-08-16-quality-kv-dtype-decision.md)
  (`quality-rejected` as the no-loss default; AutoRound INT4 is the lab lane's
  target).
- The 16,384 scheduler-budget finding, the C5 prefix-cache collapse, and the
  unsupported MTP mixed-token path are untested on this lab's pinned build and
  feed the lab ideas doc:
  [`notes/2026-08-21-b70-optimization-ideas-from-community-sources.md`](../../../../notes/2026-08-21-b70-optimization-ideas-from-community-sources.md).
- Ornith self-reported rows carry no independent verification anywhere in the
  intake; kept for orientation only.
