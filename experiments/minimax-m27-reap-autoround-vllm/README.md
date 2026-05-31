# MiniMax M2.7 REAP AutoRound W4A16 on vLLM/XPU

Target model:

- HF repo: `MJPansa/MiniMax-M2.7-REAP-172B-A10B-AutoRound-W4A16`
- Local path: `/mnt/fast-ai/llm-models/minimax-m2.7-reap-autoround-w4a16`
- Active vLLM tree: `/home/steve/src/vllm`
- Baseline lane to compare against: `/mnt/fast-ai/llm-models/minimax-m2.7-int4-autoround`

Why this lane exists:

- It keeps the known-good MiniMax M2.7 production recipe intact.
- The REAP checkpoint is materially smaller than the Lasimeri AutoRound model.
- It uses the same `MiniMaxM2ForCausalLM` architecture and AutoRound W4A16 quantization path, so it should exercise the existing XPU MiniMax/vLLM work before any new DeepSeek or STEP implementation work.

Initial fit estimate:

- HF repo size: 91,544,661,302 bytes total, 91,512,175,232 bytes of safetensors.
- Decimal/GiB: 91.54 GB / 85.26 GiB total.
- TP4 floor: about 21.3 GiB of safetensors per B70 before runtime overhead, KV cache, graph capture, and fragmentation.
- This is a much cleaner 4x32GB fit than the 120.7 GB Lasimeri checkpoint already running in production.

Run order:

1. `scripts/check-hf-metadata.sh`
2. `scripts/download-model.sh`
3. `scripts/quality-smoke.sh`
4. `scripts/bench-decode.sh`

Do not submit LocalMaxxing results from this lane until quality gates pass against the existing MiniMax canaries and repeatability is clean.
