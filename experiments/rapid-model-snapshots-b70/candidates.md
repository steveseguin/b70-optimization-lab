# Candidate Notes

## Qwen3 30B-A3B / Qwen3-Coder 30B-A3B

Why first vLLM/XPU target:

- likely best new-model fit for the existing Intel/vLLM XPU path;
- MoE active-parameter profile should be B70-friendly;
- prior Qwen work gives us strong benchmark, variance, and graph discipline;
- useful to users as a modern general/coder family.

Initial plan:

1. inspect available INT4/GPTQ/FP8/GGUF variants and local fit;
2. start with vLLM/XPU if an official Qwen3 30B-A3B INT4/GPTQ path loads
   cleanly;
3. use short context (`4096` or `8192`) for rapid decode snapshots;
4. disable thinking where appropriate for apples-to-apples short decode;
5. compare against GGUF only if vLLM setup is poor or blocked.

Watch-outs:

- do not reuse Qwen3.6-specific GDN/MTP assumptions blindly;
- record `COMPILATION_CONFIG`, XPU graph flags, TP/PP, and quant identity;
- keep prefix caching/APC off for headline rows.

## Mistral Small 3.2 24B Instruct

Why first llama.cpp dense target:

- useful dense instruct model size class;
- likely one-B70 fit at Q4/Q6 and possibly Q8 depending context/KV;
- llama.cpp GGUF setup should be fast;
- different architecture from Gemma/Qwen, useful snapshot for users.

Initial plan:

1. inspect available GGUF files and sizes;
2. download one high-quality file first, preferring Q8 if it fits, otherwise Q6
   or Q4_K-class;
3. run no-spec strict realistic baseline;
4. screen quick knobs (`ctx`, `ubatch`, FlashAttention, VMM, poll, threads);
5. try MTP/spec only if a target-verified draft path exists and is fresh-valid.

## Gemma 4 12B

Why queued:

- likely very fast on one B70;
- useful production reference;
- can compare vLLM AutoRound and llama.cpp GGUF.

Watch-outs:

- keep distinct from Gemma 4 26B Q8 production lane;
- do not move the Gemma 26B hot model while testing 12B.

## Phi-4 Family

Why queued:

- compact high-speed reference;
- useful baseline for users who want smaller models.

## Distill / Reasoning References

DeepSeek-R1-Distill-Qwen 14B/32B or similar can be sampled after the practical
instruct/coder models. Treat them as useful model-variation snapshots, not as
the main speed frontier.
