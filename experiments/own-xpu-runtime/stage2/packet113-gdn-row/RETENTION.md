# Packet113 retention and rebuild

The source snapshot records packet110 provenance in `source-origin.json`; the
unchanged recurrence header hash is identical in packets97, 103, 110 and 113.
Builds are local lab artifacts, not a portable published recipe. Frozen
packet97 objects and the pinned oneAPI installation are required. Every object
and source hash is retained in `evidence/build-*.json`; parent re-link proofs
reproduce the parent binary before the new layer object is linked.

`build/` is ignored. The 66.6 MB local build remains in place for coordinator
use, below the 150 MB budget. No other packet's files were removed or changed.
The two small leaf executables accidentally entered the initial preparation
commit; the next commit removed them from tracking while preserving current
copies as `build/retained-gnu-leaf-gdn` and `build/retained-intel-leaf-gdn`.
Initial versions remain recoverable from commit `69adfabff` or its exact source.
Raw equality precedes every transcript digest; full synthetic state dumps are
not needed to reproduce their deterministic input generator.

From the repository root, prefix each CPU command with
`nice -n 19 taskset -c 8-15,24-31`, use `python3 -B` and stdin `/dev/null`.
Run `build_engine.py --mode gnu-host`, `--mode intel-host`, and `--mode device`
serially. All take packet94's compiler turn, use an 8 GiB CPU-only CLI cap,
and retain exact commands and hashes. `cpu_leaf.py` rebuilds the leaf programs.
CPU checks require fresh output directories and refuse to overwrite retained
receipts; use a new experiment copy for new measurements. Never remove evidence
to make a run pass. `cpu_layers.py` writes invocation hashes before each process.

`seal.py` checks the completed CPU evidence and compiler inputs. `run_micro.py
--owner 1 --lane B --plan` (and owner 2) is CPU only. Only the coordinator may
use `--run`; the two JSON lines in the proposed file are not a live queue.
No generated artifact of at least 1 MiB is newly tracked.
