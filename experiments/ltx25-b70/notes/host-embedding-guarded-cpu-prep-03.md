# Guarded CPU embedding driver v3: explicit import-only refusal

2026-09-14. Root's separate guarded C++ v4 attempt encountered an unconditional
`torch.xpu.device_count()` in pinned Comfy model_management module initialization.
Comfy's bare exception handler swallowed the guard's exception, but its sticky
record halted the attempt before fixture execution. XPU and CUDA stayed
uninitialized. The prepared embedding v2 driver was not executed.

The separate v3 embedding driver installs the shared
`scripts/cpu_comfy_import_policy_v1.py` immediately after the frozen accelerator
guard and before the existing CPU availability policy captures function
identities. The policy refuses exactly one call from the pinned Comfy module's
top-level code and actual importing globals, only with explicit `args.cpu=True`
and the declared import phase. An ordinary exception lets Comfy take its existing
CPU import fallback; no hardware count is queried or fabricated. Every other
device-count attempt delegates to the original sticky accelerator trap.

The actual imported module must complete with `xpu_available=False` and exactly
one omission. The driver binds that completion after importing the unchanged
CPU fixture, and requires it in every subsequent integrity check, including
finalization. Unconditional Triton-backend and compilation refusals remain
identical to v2. Startup identity precedes Torch import, all output paths remain
exclusive, and no native work is performed by a source-only check.

Packet10 and the base checkout have identical model_management source SHA
`ef3f3af0657c1b022ad69b25928fa52dd429db9aed9cb688e89c7fbe68ab50cd`.
The shared policy accepts the explicit packet source path and verifies these
bytes. The embedding candidate and six-group numerical/ownership fixture are
unchanged from prep02. This successor alters only disposable CPU import
admission; it is not native qualification or runtime integration.

The seven-group stdlib successor suite reuses the earlier refusal/identity and
stop-on-first-failure tests, adds the exact install/completion order, and checks
that the numerical fixture and unconditional backend traps remain frozen.
All seven stdlib tests and the wrapper's source-only check passed. Evidence is
`data/host-embedding-cpu-v3-stdlib-01.json`, its matching log, and copied
startup/result receipts from
`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/host-embedding-cpu-v3-source-01`.
The driver SHA is
`1448bcf30e481f6c8e5d46a23cea1f84ef2e01b8cd574abd9716bddb03c1e6ca`;
the shared helper SHA is
`7634e653e66a682596e2bd941017722a41b9241c785dd1fb4885bfc051c31bec`.
`patches/host-embedding-driver-prep-03.patch` preserves the two new driver/test
sources. Root alone schedules any native CPU attempt after review and
postflight; no concurrent CPU/GPU experiment is implied.
