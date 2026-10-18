# Packet99 coordinator handoff

No device was launched during preparation. Proposed files are not live queue
entries. Planning never supplies the missing device evidence.

1. Run `ops/lane-queue/proposed-p99-micro-B.txt` under the existing coordinator.
   This is one lane-B card (physical card 2, PCI `0000:43:00.0`), a complete
   512-expert bank, ten routed experts, gate/up rows=640, K=2560, WG64/SG32.
   It uses the actual operation bodies, independently poisons output/status
   buffers before correctness runs, then measures 40 alternating pairs per
   candidate. Fill and barrier costs are inside event timing. The synthetic
   input is a kernel diagnostic only; CPU raw FP32 checks remain separate.
2. `micro_gate.py` requires exact BF16/status bytes and at least 15% less kernel
   time overall and in each order. The hash-bound qualification is generated
   after clean drain. There is no retry, selection override or fabricated
   pending qualification.
3. For a qualified candidate `<view>`, use
   `proposed-p99-<view>-B-grid-B-grid.txt`, then
   `proposed-p99-<view>-B-grid-A-confirm.txt`. Each job is exactly
   control → candidate → control, with the existing 90-second gaps.
   Every request must match packet49, and acceptance counts must be unchanged.
   A confirmation cannot start without that same candidate beating both B
   controls. Failed candidates receive no screen launch.
4. Compare the completed pair with:

   ```bash
   nice -n 19 taskset -c 8-15,24-31 python3 -B \
     experiments/own-xpu-runtime/stage2/packet99-iq2-grid/compare.py \
     --direction B-grid --grid exp-slm </dev/null
   ```

   Use the exact qualified view. A must beat both of its fresh controls;
   **lane A decides, and any later record chain runs on A**. This packet does
   not launch or qualify a record chain. Screens use the shared 128-token
   diagnostic suite; they are not a 512-token final performance headline.

CPU-only plan commands (also invoked by temporary queue planning):

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B \
  experiments/own-xpu-runtime/stage2/packet99-iq2-grid/run_micro.py --plan </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B \
  experiments/own-xpu-runtime/stage2/packet99-iq2-grid/run_screens.py \
  --plan --direction B-grid --grid exp-slm --lane B </dev/null
```

Six available view names: `exp-slm`, `exp-compact-slm`, `exp-compact-global`,
and each with `+halfcache`. Systemd job names replace `+` with `-`; selection
names and proposed filenames retain `+`. The failed first planning attempt and
initial seals before this unit-name fix are retained in `evidence/`.

The actual wrappers keep the shared lane lease, memory/storage admission,
fault review, process ownership, graceful stop and drain rules. No host setting
is changed. They require fresh output paths and explicit coordinator admission.
