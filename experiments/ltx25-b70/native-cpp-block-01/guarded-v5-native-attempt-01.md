# Guarded CPU v5: import fixed, compiler detection refused

2026-09-14. One root-controlled diagnostic, PID107105 (tool session14864),
exited1. The scoped Comfy import omission worked exactly once. One eager tiny
CPU block call completed, then the first Python-boundary compilation stopped
before a compiled result. No C++ compiled call or cache-save omission occurred.
XPU and CUDA remained uninitialized.

The captured first stack is Dynamo `VariableBuilder._wrap` →
`torch.utils._triton.has_triton` → `get_registered_device_interfaces` →
`init_device_reg` → the trapped `torch.cuda.device_count`. Compilation metrics
unwinding then reached the same query through `has_triton` again. Those are
two guarded calls within one failed compilation, not two model attempts or
a client retry. The sticky guard and finalizer preserved failure.

Root reviewed the helper and harness delta, independent source review found
no blocker for the bounded attempt, and56 stdlib checks plus the source gate
passed before execution. Native compiler qualification remains incomplete.

[Result/stack](guarded-v5-result-01.json),
[startup](guarded-v5-startup-01.json),
[source check](guarded-v5-source-check-01.json),
[run output](guarded-v5-run-01.log), and
[17:26:58 UTC postflight](guarded-v5-postflight-01.json) preserve the attempt.
Postflight found this process absent, the unchanged healthy LTX PID84255,
identical full endpoint identity, empty queue, only that PID on all four
render devices, and no new kernel/fault evidence. No application/host action.

The separate no-compilation embedding fixture subsequently passed six CPU
groups using the same Comfy import policy. This establishes that the import
fix supports that bounded CPU path, not that compilation is qualified.

The next proposed C++ successor uses PyTorch's existing process-local
`TORCHINDUCTOR_TRITON_DISABLE_DEVICE_DETECTION=1` before Torch import.
Installed `torch/_inductor/config.py:592–595` defines it specifically to
disable host device detection; `torch/utils/_triton.py` returnsFalse before
enumerating interfaces when it is set. Record this as an explicit CPU
diagnostic configuration change shared by both compiled arms. Preserve
numerical compiler options, all hardware traps and the prior failed source.
Do not rerun v5 unchanged or treat this proposal as a native result.
