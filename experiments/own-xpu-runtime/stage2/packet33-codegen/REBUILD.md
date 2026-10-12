# CPU-only rebuild

Run commands from repository root. Installed compiler2026.0, ocloc26.18 and
packet29's original device objects, `compile_commands.json`, fixture files and
original `k2-fixtures` are required. Their identities are sealed in the receipt;
this is a local research packet, not a clean-checkout public runtime recipe.
The original module byte offsets/hashes are verified before extraction.
Nothing below executes a SYCL device program. Never execute p33-k0 or
p33-timing during this CPU-only sequence.

Execute serially; use nice19, idle I/O and OMP2 on every command:

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/stage2/packet33-codegen/offline.py
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/stage2/packet33-codegen/build_driver.py
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/stage2/packet33-codegen/timing_prepare.py
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/stage2/packet33-codegen/link_native.py
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/stage2/packet33-codegen/candidate_offline.py
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/stage2/packet33-codegen/analyze.py
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/stage2/packet33-codegen/make_table.py
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/stage2/packet33-codegen/option_study.py
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/stage2/packet33-codegen/candidate-gates.py
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/stage2/packet33-codegen/model.py --extract --fit
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/stage2/packet33-codegen/test_protocol.py
```

`link-command.json` also records the exact original-object relink that produced
the first24 modules via `-fsycl-dump-device-code`. Rebuild scripts generate all
harness deltas by single-match substitutions; changed dependencies fail those
assertions rather than patching another packet. `build-receipt.json` is the
captured original seal, not silently refreshed by any timing command. A rebuild
must be reviewed and sealed separately if it changes those hashes.

Assembly/vISA/LLVM dumps and binaries remain ignored under build. The committed
codegen JSON is larger than1MiB because it retains every selected kernel's
message histogram, loop regions, payload/scratch metadata and final-text proof;
it is the reviewable extracted evidence requested by this study. Restore it with
offline.py + candidate_offline.py + analyze.py + make_table.py, with the exact
sealed inputs. It contains no full assembly dump. `iteration-codegen.json`
retains initial extraction for history; early instruction regex omitted BFN
opcodes, so use the independently corrected review for before/after counts.
