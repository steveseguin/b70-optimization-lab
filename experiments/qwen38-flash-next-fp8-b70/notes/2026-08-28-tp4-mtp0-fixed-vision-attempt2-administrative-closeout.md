# Flash-Next TP4 eager MTP0 fixed-vision attempt 2 administrative closeout

Date: 2026-08-28

Attempt 2 stopped during admission before any card check, collective, launcher,
model load, API request, text case, or vision request. The admission receipt
directory does exist and is preserved at
`/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-vision-512-r1-attempt2-supervisor`.
Its 16 files are pinned by
`data/20260828-tp4-mtp0-fixed-vision-attempt2-admission-evidence.sha256`
(manifest SHA-256
`e41fbbcf87d57ef9da28249ca9fa2215ef6d463ed155ce539aac1dc15afbfea7`).

The stop was an administrative classifier false positive. The old admission
gate searched full command text for `qwen38-flash-next`. Its captured
`processes-before.txt` contains only PID 1904941, the attempt-2 supervisor
itself. The supervisor's repository directory has that text in its pathname,
so the gate necessarily matched itself. No lifecycle state file, run
directory, cache, compile directory, or RPC directory exists.

This is not a model/runtime negative and grants no capability, quality,
deployment, speed, matrix, or website credit. No protected result changes.
Attempt 2 is closed and its receipt directory must not be reused.

Attempt 3 changes only this administrative gate. It enumerates `/proc`,
excludes its own process and ancestors, and recognizes exact vLLM server,
vLLM worker, torch distributed launcher, XCCL probe, or exact Flash-Next model
ownership shapes. A committed fixture proves the supervisor-path and old
search-command examples are clear while real vLLM, distributed, and collective
examples fail closed. Model, runtime, placement, cache, tests, timeouts,
resource floors, and interpretation remain unchanged.
