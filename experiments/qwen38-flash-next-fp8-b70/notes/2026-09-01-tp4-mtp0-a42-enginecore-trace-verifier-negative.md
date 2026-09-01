# Qwen3.8 Flash-Next FP8 A42 EngineCore trace-verifier negative

Date: 2026-09-01
Status: preserved healthy-endpoint, zero-request negative

A42 loaded, captured on all four ranks, and became healthy. Its corrected
diagnostic receipt passed. The trace-aware verifier then rejected EngineCore
because `TORCH_TRACE` was no longer present in that process environment. Four
rank-specific trace logs existed under the exact isolated A42 directory,
showing that workers received and used the selector. Zero requests were sent.

A43 keeps strict exact-path checks on every worker and all trace contents. It
allows only `VLLM::EngineCore` to omit the selector after structured logging
consumes it; a different declared value is still rejected. Seven focused tests
cover missing/different EngineCore values, strict worker behavior, argument
binding, and base hash drift. The endpoint tore down cleanly; no reboot is
needed.
