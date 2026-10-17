# Packet55 route locality diagnostic

This is an independently instrumented copy of packet49c's checked source
closure. The sealed packet49c and packet49d trees are read only. It copies
existing ordered top-10 expert IDs and normalized FP32 weights after each
router, including the INT8 MTP draft. The copied IDs are the same device output
used to construct the production route descriptors; no router is recomputed.

Target dispatch, weight bytes, BF16 boundaries, split32 QSA, 16-bit KV and
23/25 target placement are unchanged. The only nonlogging runtime changes are
raising this diagnostic's generation cap from 128 to 256 and checking physical
PCI identity before creating a device context. A separate 128-token sanity
request must equal the hash-bound packet49 CPU oracle before any calibration
request runs. That sanity trace never enters training or held-out analysis.
Full-model token identity is a coordinator gate, still pending until execution.

D2H copies follow each prepared router site's timing interval. They synchronize
the owner and change request elapsed time and overlap. **This executable is a
route diagnostic; none of its times are a model speed result.** The wrapper
marks every request diagnostic and clears inherited rate fields. Existing
kernel bodies and their argument bindings are unchanged.

`calibration-prompts.json` contains 24 newly written requests: code, prose,
analysis, structured output, multilingual writing and mathematics. The first
12 train, the other 12 test, with two prompts of each class in each half.
Every request asks for 256 new tokens. Natural EOS is honored, with no retry,
prompt substitution or EOS suppression. A short response is retained and makes
`requested_scope_complete` and `all_generated_256` false; observed partial
routes remain useful, but are not a complete 24×256 calibration measurement.

The MTP dependency is the existing packet49c hash-bound official draft under
`/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8`. The admitted IQ3 folder contains
only three GGUF shards, with no MTP material. The window refuses without
`--allow-existing-p49c-draft`, which the coordinator may provide only after the
owner allows this exact existing dependency. Preparation reads no draft weight
bytes. Target weight reads remain restricted to the admitted IQ3 directory.

Build and CPU checks, from repository root (one compiler at a time):

```bash
P=experiments/own-xpu-runtime/stage2/packet55-feasibility/route
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/build.py" device
nice -n 19 taskset -c 4-15,20-31 /home/steve/.venvs/vllm-xpu/bin/python3 -B "$P/prepare_inputs.py"
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/test_route.py"
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/build_host.py"
nice -n 19 taskset -c 4-15,20-31 env OMP_NUM_THREADS=2 python3 -B "$P/cpu_smoke.py"
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/source_gate.py" --write
```

The native build takes about 8 minutes on this host; the host build takes a few
minutes and the tiny synthetic CPU check takes seconds. `source_gate.py` binds
all project include dependencies, including the injected external
`kernel_guard.hpp` and the private host validation headers; the window verifies
that closure before launching. The host smoke uses no real model bytes.

The build copies about 14 MB of checked sources, compiles only engine objects
and links one executable; it rejects a route build larger than 650 MB. The
whole packet must also remain below the owner's 1 GB build limit. Input
preparation reads only about 21.9 MB of admitted GGUF header bytes and verifies
the existing identity/header hashes. It uses the already installed `regex`
dependency in the named venv. No model tensor payload is read by preparation.
Re-run input preparation only into a fresh build/input destination; never
silently replace its bound calibration manifest.

The optional `refresh-main` build action is for the retained preparation
correction only: it compares the entire source mirror, restricts allowed
changed files, traverses all compiled translation units' quoted includes, and
recompiles every dependent object. Its receipt preserves prior and current
source hashes and commands. A fresh normal `device` build incorporates the
same final changes without a correction pass.

Coordinator command (estimate 30–90 minutes, including startup, diagnostic
copies, snapshot compression and the five-minute postflight; hard cooperative
budget four hours). The coordinator supplies its reviewed-fault UTC boundary
and approved library path; the preparer never starts the unit:

```bash
P=/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet55-feasibility/route
# REVIEWED_UTC is the coordinator's actual UTC fault-review boundary.
# The draft flag below requires the exact existing-source allowance above.
systemd-run --user --unit=packet55-route-cards23-a \
  --property=Nice=19 --property=CPUAffinity='4-15 20-31' \
  --property=KillMode=none --property=TimeoutStopSec=infinity \
  /usr/bin/env -i LD_LIBRARY_PATH="$LD_LIBRARY_PATH" \
  /usr/bin/python3 -B "$P/window.py" \
  --output "$P/evidence/cards23-a" \
  --faults-reviewed-through "$REVIEWED_UTC" \
  --authorized-device-window --allow-existing-p49c-draft
```

Physical card 2 must be `0000:43:00.0`, card 3 `0000:47:00.0`. Both must be
free. Unrelated card-0/1 clients are recorded, not stopped. **At least 97 GiB
MemAvailable is required before loading the resident engine**, so disjoint
cards do not imply enough host memory to run beside packet49d. The coordinator
must choose the window. A shared packet55 exclusive nonblocking flock prevents
overlap with packet55 CPU throughput and H2D windows; it does not schedule other
packets. Memory blocks 53–57 must remain offline. The wrapper retains full boot
journal evidence, polls new fault lines every 250 ms, cooperatively stops only
its own rank owners, never retries, and keeps a fault latch. No health probe,
recovery operation, power setting or memory setting is part of this runner.

The observer adds no pinned allocation: it reuses each rank's existing 4 MiB
readback slab, and holds only tiny route byte vectors. The inherited resident
engine memory ledger remains enforced. Full request-boundary state snapshots
are compressed with byte-for-byte hash verification before replacing their
owned raw files. Budget roughly 2 GB for 25 request snapshot archives plus
under 100 MB of binary routes; the wrapper requires 10 GB free initially and
keeps an 8 GB free floor. Actual snapshot size is workload dependent and a
floor refusal terminates the window cleanly. No file in another packet is
removed or rewritten.

Offline conversion (typically seconds to a minute):

```bash
nice -n 19 taskset -c 4-15,20-31 python3 -B "$P/convert.py" \
  --window "$P/evidence/cards23-a" \
  --output "$P/evidence/cards23-a/routes.jsonl.gz"
```

The converter requires a successful complete window and all 24 requests,
validates records, owners, top-10 uniqueness/probability normalization and all
committed target/draft positions. Every uncancelled command must cover its full
23/25 layers; a cancelled speculative rank-0 command may contain an ordered
layer prefix, bound to the native timing cancellation receipt. A route can be
observed immediately before cancellation prevents its experts from executing.
These are observed routing demands, not completed expert byte counters. A
cache simulator that admits every observed route is a declared scenario, not
a proven bound on an eventual one-card cancellation policy. It merges per-rank streams by monotonic timestamp, rank and sequence.
Speculative and corrected executions remain distinct and both cost bytes.
An early EOS only reduces the declared observed request length; it never gets
filled in. The resulting `.gz.json` sidecar binds window, manifest, request
results, binary logs and compressed output hashes.

Binary schema: header `P55RTE1\n`, then little-endian fixed 124-byte records
`<QQIIIIIII10I10f`: sequence, monotonic nanoseconds, position, layer, role
(0 target/1 draft), count, command ID, speculative flag, fixture index,
10 unsigned expert IDs and 10 float32 weights. Command IDs are per-owner
monotonic dispatch counts, because rank 0's existing wire sequence is not
unique. The JSONL converter adds prompt ID, train/test split, category and
prefill/decode phase. Last prompt position produces the first output token;
draft internal position is one less than its confirmed target position.

Credit Niko1221 / Strata for the described hot-expert cache and CPU-miss design
idea. No Strata, llama.cpp or vLLM code was used. These observations measure
this lab engine and this quantized compressed checkpoint only.
