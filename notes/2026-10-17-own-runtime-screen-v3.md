# October 17: screen v3 accepts lean candidates on independent masked pairs

The CPU wrapper is ready for the coordinator. Packet56w-spin, packet59c's
selected attention candidate and packet60-hc-fusion all pass plans on both
lanes. All 26 CPU tests pass. No GPU, native binary, service or model load ran.
There is no new model-speed or native-isolation measurement.

The implementation and exact CPU/device commands are in
[screen/v3](../experiments/own-xpu-runtime/stage2/screen/v3/README.md).
V1 and v2 files and results were left intact. Work was limited to the new v3
folder and this requested note. `CURRENT.md` was left for the coordinator:
this task changed no card ownership, loaded model or authorized device window.

## Decisions

1. V3 uses the same candidate seal checks as v1 for its **two-card ABI**.
   It accepts explicit binary/dispatch/seal paths and selected lineages.
   The fixed packet56 Python controller is part of the wrapper's source
   closure; the candidate does not supply controller files. One-card lineages
   stay with v1's separate profile, rather than being reinterpreted as TP2.
   Packet57's explicit attribution support remains available, with token
   timing the default. Candidate memory ledgers remain hash-bound and undergo
   the controller's allocation admission; v2's extra whole-file equality to
   packet56 is not an additional candidate identity requirement.
2. Physical A is cards 0+1 (PCI 23/27), nice 0, cores 0–3/16–19. Physical B is
   cards 2+3 (PCI 43/47), nice 0, cores 4–7/20–23. Both native rank pairs use
   local indices 0 and 1 after filtering. CPU preparation used nice19,
   cores 8–15/24–31 and `python3 -B`.
3. Ordinary SYCL/Level Zero selectors are insufficient as a guarantee about
   which DRM files get opened. Intel compute-runtime
   [26.18.38308.1's discovery code](https://github.com/intel/compute-runtime/blob/26.18.38308.1/shared/source/os_interface/linux/drm_neo.cpp#L670-L762)
   checks `FilterBdfPath` before opening each by-path node. That matches the
   installed `libze-intel-gpu1` version; the local library also contains that
   flag and `NEOReadDebugKeys`. V3 inserts this fixed prefilter, PCI ordering,
   `ZE_AFFINITY_MASK=0,1` and `ONEAPI_DEVICE_SELECTOR=level_zero:0,1` after the
   original closed-environment gate. It checks the by-path/sysfs mapping
   without opening device nodes. This uses an Intel dependency's option, not
   an imported runtime implementation or an engine patch.
4. Native fdinfo proof is mandatory. Each PID is bound to start ticks, foreign
   or unidentified Xe handles fail, and both mapped cards must be observed
   before the incident request. Sampling continues through measurement; the
   last live check precedes FINISH. Evidence retains FD numbers, PCI devices,
   client IDs, masks and failures. Native validation remains the coordinator's
   job; CPU success is not substituted for it.
5. Standalone lanes use separate locks and no peer measurement barrier. The
   optional crossover runs candidate/control together, then swaps lanes.
   Cooperative teardown is serialized for all v3 workers, with at least 60
   seconds from the previous complete drain. An incomplete drain stays blocked.
   No process is hard-killed, retried or restored. Old unmasked workers still
   block any selected PCI devices they hold.
6. Retain exactly two reviewed fault lines, PF_EXITING sensing, the 54/56
   fence, closed caller environment and all inherited storage/memory floors.
   The initial root-free reading was about 11 GiB; no builds or payload copies
   were needed. Storage is checked again at device admission; a crossover
   requires 4.4 GB writes above the 8 GB free floor. No host setting was changed.
7. Every incident token and all 12 × 128 suite tokens must match packet49.
   Masks, CPU affinity and the wrapper do not authorize altered arithmetic,
   compressed KV, prompt reuse or a weaker oracle. All outputs stay diagnostic
   and ineligible for promotion; the full chain is still required.

## Validation and handoff

- [CPU seal](../experiments/own-xpu-runtime/stage2/screen/v3/wrapper-seal.json),
  [test log](../experiments/own-xpu-runtime/stage2/screen/v3/cpu-tests.log),
  [byte fixture](../experiments/own-xpu-runtime/stage2/screen/v3/byte-fixture.json).
- [Seven successful CPU plans and exact argv](../experiments/own-xpu-runtime/stage2/screen/v3/evidence/plan-commands.json):
  packet56w-spin with `screen-seal.json`, packet59c
  `selected/screen1-attention` with `build-receipt.json`, and packet60-hc-fusion
  with `screen-seal.json`, each on both A and B; plus packet60 versus packet56
  crossover. Every candidate plan supplies explicit binary and dispatch paths.
- [Passive topology evidence](../experiments/own-xpu-runtime/stage2/screen/v3/evidence/topology-cpu.json):
  A maps to renderD130/131; B maps to renderD128/129. The PCI identities, not
  render-minor order, decide membership.
- [CPU fault review](../experiments/own-xpu-runtime/stage2/screen/v3/evidence/cpu-review.json):
  exactly two known records; the captured journal boundary is
  `2026-10-17T14:13:17.184490Z`. A device launch revalidates the boot, capture
  and fresh tail. This does not authorize a window or clear any latch.
- [Closeout](../experiments/own-xpu-runtime/stage2/screen/v3/CPU-PREPARATION-CLOSEOUT.md).

The initial requested `git pull --rebase` refused because another job had a
tracked edit in packet56w-chain. Fetch showed no incoming commits; that file
was not stashed, reset or edited. After its owner committed, a second
`git pull --rebase` succeeded and reported up to date. This preparation stayed
on `main`, with no branch, worktree, sudo, service or settings change.
