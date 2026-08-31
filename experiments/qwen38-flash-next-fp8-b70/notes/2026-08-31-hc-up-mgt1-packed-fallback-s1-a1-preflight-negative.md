# Qwen3.8 Flash-Next HC-up M>1 S1 attempt-1 preflight negative

Date: 2026-08-31

Status: preserved orchestration negative; no XPU work

S1 attempt 1 failed on its first authority worker before importing Torch. The
driver inherited `/usr/bin/python3` from its shebang and used that interpreter
for the worker. That interpreter does not contain `safetensors`, so the worker
stopped at module import. The durable receipt records return code 1 and the
exact `/usr/bin/python3` command. No arm JSON exists, no checkpoint tensor was
read, and no XPU extension or kernel was loaded.

Evidence is preserved under:

`/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/hc-up-mgt1-packed-fallback-s1-r1-seed20260831`

The structured classification is
`data/20260831-hc-up-mgt1-packed-fallback-s1-a1-preflight-negative.json`.
This is a harness defect, not a provider result. It changes no protected speed,
quality, source-integration, or endpoint claim.

The successor binds `/home/steve/.venvs/vllm-xpu/bin/python`, requires the
worker's `sys.prefix` to equal `/home/steve/.venvs/vllm-xpu`, records the exact
interpreter identity, and uses a new attempt-2 evidence root.
