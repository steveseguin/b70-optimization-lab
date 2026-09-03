# Qwen3.8 Flash-Next FP8 A69 resolver head-pin negative

Date: 2026-09-02 22:08--22:25 EDT
Status: procedural negative; no request reached the server; no promotion claim

A69 (A68 with the client's helper file name restored) loaded normally (four
`mkldnn.deterministic=True` lines, weights 22:20, healthy 22:23). The client
passed its first pins and stopped at the official W13-N32 resolver receipt:

```
IntegrationContractError: vLLM prerequisite head drifted: 805cde592dfe198a82deaba52894ebfc0e4a4352
```

`tools/verify-moe-m1-w13-n32-selection.py` pinned the overlay head
`cbc3cb58...` in addition to hashing the three MoE source files it resolves
against. The served overlay is `805cde59...`, three diagnostic commits later
(GDN trace records, `Q38_` trace aliases, the `VLLM_XPU_MKLDNN_DETERMINISTIC`
worker flag), none of which touch those files. The supervisor tore the
untouched server down when the client exited (final status 143); no
request, quality row, or speed row exists, and the kernel log holds no GPU
event.

Fix: the verifier accepts both heads (`EXPECTED_VLLM_HEADS`), keeping the
per-file hash contract as the real guard; its SHA-256 becomes
`94487432...`. A70 (`tools/rewrite-q38-a67-to-a70-battery.py`) pins that
hash, moves the client's own three head receipts (`git rev-parse` check,
identity receipt, summary JSON) to `805cde59...`, and requires the
`mkldnn_deterministic=1` identity receipt. Attempt 70 / port 19742. The
sealed-lane rule applies: every helper the client invokes was grepped for
the old head literal before A70 was frozen, and only this verifier carried
it.
