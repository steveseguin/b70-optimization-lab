# Packet58g one-card scoped measurement

Qwen3.8 Flash-Next 125B-A6B Unsloth UD-IQ3_XXS (GGUF). Quantized compressed version, separate from FP8. Lab own Xe runtime, TP1, 1x Arc Pro B70. Host-pinned expert weights; 18 GB device expert cache, copy-on-miss cache fills; fallback miss path=zero-copy. BF16 KV at 4096. Plain greedy, no draft/MTP. 12/12 cold prompts, 1536 tokens exact to packet49 CPU oracle iq3-p49-split32-v1; fresh WS/WS128x/WS128 exactness repeats. No prompt/KV/response reuse, cached_tokens=0; only immutable weights cached. 128-token owner scope; strict 512 gate false. WS128 alone: whole-host timing, median of six prompt-class medians, 99 intervals between generated events 1 and 100 after TTFT. tokSTotal=median output/(last token-request start). WS128x is exactness under possible shared load, not timing confirmation. Second whole-host timing run still needed for a speed verdict. 512-token natural completion and standard prefill not measured. Public matching 1-GPU best unverified: authenticated API GET on 2026-10-18 was blocked (HTTP 403/Cloudflare 1010). No matching entry in the lab submission ledger; public absence is not established.

Measured WS128: 24.338653323339745 tok/s. See result.json for all prompt/class statistics.

Preparation only; no submission performed. Strict final gate and fresh timing confirmation remain false.

## Coordinator disclosure (2026-10-18 02:50 UTC)

The public LocalMaxxing speed-test list for model id `cmtas1yaz000cqq01umzx85mw` (unsloth/Qwen3.8-Flash-Next-GGUF) was read with an ordinary HTTP GET: 57 runs, 16 on one GPU, none on a single Intel Arc Pro B70. Other single-GPU hardware is faster (Strix Halo unified memory up to 110 tok/s, Radeon AI Pro R9700 63.97, CMP 170HX 46.05). This submission is therefore the first 1x Arc Pro B70 entry for the model, not a cross-hardware one-GPU record. The payload notes' last sentence was replaced with this finding; the original preparation is kept beside it. The payload omits `specNumTokens` because there is no draft: the server rejects 0, and the first preparation `card0-58g-a` failed the server dry-run on it.
