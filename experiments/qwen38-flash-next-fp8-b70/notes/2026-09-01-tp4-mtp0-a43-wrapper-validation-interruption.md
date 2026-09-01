# Qwen3.8 Flash-Next FP8 A43 wrapper-validation interruption

Date: 2026-09-01
Status: preserved pre-load orchestration interruption

A43 was interrupted while its layered source wrappers were still validating
their ancestry. The supervisor evidence records exit code 130. No attempt-43
run, runtime-cache, compile, or RPC directory was created; no model worker,
checkpoint load, endpoint, or request occurred. Four-device postflight was
clean, with no host or GPU fault.

This is an orchestration-cost result, not a model or full-graph result. A44
retains A43's exact inference identity and audited EngineCore-aware verifier on
fresh paths. Its derivation was additionally checked as a direct A43/A44 diff
before launch. Future successors must flatten the accumulated wrapper ancestry
or rewrite named fields rather than adding another broad attempt-name rewrite.
