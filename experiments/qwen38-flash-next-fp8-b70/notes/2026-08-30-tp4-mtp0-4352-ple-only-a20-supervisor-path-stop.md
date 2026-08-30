# Qwen3.8 Flash-Next FP8 A20 supervisor-path stop

Date: 2026-08-30
Status: pre-load contract stop; no model result

A20 passed artifact and collective preflight and started the external-path API
process. The supervisor's owned-process assertion still required the former
local checkpoint path, so it immediately failed closed and terminated the
server before worker initialization or checkpoint loading. No request, output,
trace, timing, or device failure occurred. Attempt-20 paths are preserved and
will not be reused; no protected result changes.
