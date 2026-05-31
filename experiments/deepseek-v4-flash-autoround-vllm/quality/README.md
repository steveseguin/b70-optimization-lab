# Quality Gates

This folder is for DeepSeek V4 quality prompts, hashes, and summaries once the
model can generate through vLLM/XPU.

Initial gates should be lightweight:

- raw prompt smoke with deterministic greedy output;
- NUL/control-character count;
- distinct generated token count;
- basic JSON/code/math canaries after the first text path works;
- exact token hashes only after tokenizer and chat-template behavior are stable.

Do not compare speed records until the same quality gate has passed on the
candidate and on the current baseline.
