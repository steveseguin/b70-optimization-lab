# Qwen3.8 Flash-Next HC-up M>1 packed-fallback S1 attempt-2 preregistration

Date: 2026-08-31

Status: frozen before XPU execution

This is the exact successor to the attempt-1 interpreter preflight negative.
All model, runtime, weight, input, provider, M2/M64, memory, correctness,
classification, and no-promotion rules from the
[S1 preregistration](2026-08-31-hc-up-mgt1-packed-fallback-s1-prereg.md)
remain frozen.

The only behavioral change is worker interpreter binding:

- the driver invokes `/home/steve/.venvs/vllm-xpu/bin/python` rather than its
  own shebang interpreter;
- the worker requires `sys.prefix == /home/steve/.venvs/vllm-xpu` and records
  its executable and prefix;
- `safetensors 0.7.0` imports successfully in that frozen environment;
- evidence moves to distinct run attempt 2 and cannot reuse attempt 1.

Frozen identities:

- worker SHA-256:
  `153a51f4a742f461f6bd1a5d4e4e289ca2f91415d11f66e65580d1221d2891c4`;
- driver SHA-256:
  `67dcd9d94fb70aa9c545ea970c175e9a85a6781d445cecebfe442ab8522d1d76`;
- S1 attempt-2 plan SHA-256:
  `9a3b771a33d8f659c86380af139a88dd6134816969d39b1f7a6653a9167e6fc9`;
- expected evidence root:
  `/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/hc-up-mgt1-packed-fallback-s1-r1-a2-seed20260831`.

Frozen command:

```bash
experiments/qwen38-flash-next-fp8-b70/tools/run-hc-up-mgt1-packed-fallback-gate.py \
  --scope s1 --repeat r1
```

Attempt 2 still performs no reboot, server launch, or full model load. No
provider result can authorize source integration or an endpoint claim.
