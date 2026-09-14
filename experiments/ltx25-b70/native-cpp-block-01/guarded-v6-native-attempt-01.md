# Guarded CPU v6: detection setting worked; generic handlers still enumerate

2026-09-14. Root ran one bounded diagnostic, PID108612 (tool session71145),
exit1. One eager tiny CPU call completed. The first Python-boundary compile
stopped before producing a compiled result; no C++ compiled call or cache-save
omission occurred. XPU and CUDA stayed uninitialized.

The native setting was verified: `triton_disable_device_detection=True` and
the unchanged native `has_triton()` returnedFalse. It avoided v5's detection
path, but Dynamo's generic torch-function handler registration independently
calls `get_registered_device_interfaces()` at `variables/torch.py:1719`.
That reached `init_device_reg()` and the retained CUDA device-count trap.
The source-backed distinction matters: v6's setting worked for its intended
branch; it does not suppress every device-registry user in Dynamo.

Root read the full policy and harness delta, independent review found no
blocker for the bounded diagnostic, and69 stdlib/source checks plus the
source-only gate passed first. This is another preserved diagnostic refusal,
not a model correctness failure or a completed CPU C++ qualification.

[Result and captured stack](guarded-v6-result-01.json),
[startup](guarded-v6-startup-01.json),
[source check](guarded-v6-source-check-01.json),
[run output](guarded-v6-run-01.log), and
[17:34:40 UTC postflight](guarded-v6-postflight-01.json) preserve evidence.
Postflight confirmed the probe absent, unchanged LTX PID84255, identical full
endpoint identity, empty queue, only that PID on all four render nodes and
no matching kernel/fault entries. No application, host or settings action.

Do not rerun v6 unchanged. A future compiler diagnostic needs an explicit,
reviewed CPU-fixture treatment of the device registry with all hardware traps
retained; its compiler semantics must be declared rather than represented as
unchanged GPU behavior. Only source investigation is queued for that decision.
The independently passed embedding CPU proof and inactive runtime integration
continue without depending on C++ compilation.
