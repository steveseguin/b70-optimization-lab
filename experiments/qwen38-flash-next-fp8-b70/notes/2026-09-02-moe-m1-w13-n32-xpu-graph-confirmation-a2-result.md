# Qwen3.8 Flash-Next W13-N32 M1 MoE graph confirmation A2: pass (2026-09-02)

Date: 2026-09-02 01:14--01:29 EDT
Status: component confirmation passed on the frozen A2 wrapper; not yet an
endpoint result

## Result

The frozen A2 wrapper (`tools/run-q38-w13-m1-xpu-graph-confirmation-a2.sh`,
derived from the hash-pinned A1 base) ran layers 0 and 47 on EP ranks 0--3
with seed 20260827 as eight matched fresh-process control/candidate/control
cells against the external checkpoint on one B70, with the root SSD at Gen3
x4 under the validated `q38_root_nvme_link_clearance_v1` receipt.

Clean attempt (attempt 4, exit 0, health receipt `pass`):

| gate | value |
|---|---|
| all 8 cells exact (100 changing-input graph hashes each) | true |
| positive cells | 8 / 8 |
| median matched reduction | `22.246154%` |
| worst cell reduction | `21.551557%` |
| control drift within 2% | true (max about 0.9%) |
| local-NVMe corrected delta / root-port delta | 0 / 0 |
| local-NVMe sectors read during the run | 8 (cap 4,194,304) |
| swap used / memory-full avg10 | 0 / 0.0 |

Candidate `W1_CONFIG={"BLOCK_SIZE_N": 32}` runs the M1 W13 grouped path at
about `167--170 us` against `215--218 us` controls on both layers and all
four ranks. This reproduces the discovery census (`22.627183%` on one
layer/rank) across the full EP topology. Evidence:
`/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/components/20260901-moe-m1-w13-xpu-graph-confirmation-a2/`
(`summary.json`, `health-receipt.json`, 24 cell JSONL files, SHA256SUMS).

## Attempts preserved beside it (procedural negatives, no measurement credit)

1. `...-a2.failed-ntfs-chmod-20260902T0512Z`: after the cold boot the Corsair
   drive was remounted root-owned; `install -m` on the FUSE mount failed.
   Fix: `ntfs-3g -o allow_other,default_permissions,uid=1000,gid=1000`.
2. `...-a2.failed-local-read-cap-cold-cache-20260902T0515Z`: the cold page
   cache made each fresh process read hundreds of MB of Torch/oneAPI
   libraries from the local SSD; the 2 GiB read guard stopped it at cell 5
   (GPU smoke passed). Fix: pre-read the venv, oneAPI, vLLM, and kernels
   trees (12.2 GB in 6 s, zero link events); a warm import then reads 15 MB.
3. `...-a2.measurement-pass-health-foreign-pgrep-20260902T0522Z`: all 24
   cells completed and every measurement gate passed (median `22.233186%`,
   worst `21.668224%`), but the final health contract failed closed because
   `pgrep -af w13-m1-xpu-graph-gate.py` matched a concurrent Codex shell
   command that was tailing this run directory with that string in its
   argument list. Also during attempt 3 a Codex `find /mnt/fast-ai
   /mnt/usb-models -type f -size -20M | while read` scan had read 3.5 GB
   from the local SSD; it was terminated so the run's read guard held.
   A lane-ownership notice was added to `CURRENT.md`.

## What this authorizes

W13-N32 is a lossless, cross-layer, cross-rank component win and advances to
integration as a default-off selector, then exact eager/captured component
qualification, then the TP4/EP4 MTP0 endpoint arm. Expected whole-target-step
effect must be computed from the A28 profile share of the W13 M1 path before
ranking it against HC gate-mix and HC combine-norm; the component percentage
alone is not the endpoint claim. Protected results are unchanged.
