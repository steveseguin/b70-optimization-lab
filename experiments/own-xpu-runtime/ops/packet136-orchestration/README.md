# Packet136: bundle7 plus banked rollback state

CPU preparation ahead of packet131b's lane-B verdict. This packet copies
packet124c and preserves all 182 links. The packet49 oracle remains a symlink;
`oracle-binding.json`, `shared_oracle.static_binding()` and the real
`shared_oracle.py --require-complete` subprocess verify it. Oracle paths never
enter new repository source maps. Those maps use the runtime's safe-path check
at creation and admission, including `--plan`.

There are exactly two selections: bundle7 with `rollback_state=copy` and
bundle7 with `rollback_state=banks`. They map to native `miss=batch` and
`miss=banks-batch`. Both reuse packet131b's identical GNU/device binaries,
source closure and exact state transcripts. No new device output is inherited.
The unchanged identity is `iq3-p49-split32-v1`, BF16 KV, draft prefix 80,128.
The existing 58.223834 tok/s record, `cmvdx8urg0068rf01vvb32bcs`, remains current.

The bank allocation/prepared-command layout is not runtime-switchable in v5.
[The proposed lane-A file](../lane-queue/proposed-p136-confirm-A.txt) therefore
contains a composed twelve-prompt 64-token smoke followed by five fresh v4
loads: control/candidate/control/candidate/control. Each grid load uses all
twelve cold 128-token prompts and an incident64 check, matching packet131b B.
Expected total: 35–55 minutes, including the separate smoke. Each grid load
has a 60-minute watchdog (estimated 6–10 minutes); smoke has a 30-minute
watchdog (estimated 5 minutes). There is no campaign retry. The proposal is
planned only on a temporary queue. It is not queued or launched.

`ready.json` is false until both candidate repeats beat every same-lane control
by at least 0.5% on **both** A and B, control drift is at most 3%, all outputs
are exact, per-prompt acceptance counts agree, selections/binaries/dispatch and
memory layouts are identical, and the separate composed 12 × 64 smoke passes.
Lane B reads packet131b's registered original receipts; its own 1% study verdict
is not substituted for packet136's preregistered 0.5% threshold. Rates are
recomputed from raw request timestamps; stored pass booleans cannot qualify.
Missing, malformed, changed or failed evidence refuses. No parent chain or
bundle7 screen result substitutes for these device gates.

The extended argument gate exercises eleven real chain window paths, 31 native
argument lists, K2 replay and the real queue loop with twelve input preflights
and six complete-oracle subprocesses. The six confirm entry tests reach both
intercepted native rank launches through real CPU/oracle admission. Operational
receipts are explicitly synthetic and stay in disposable CPU scratch. Drain,
teardown-on-error, getrlimit and fresh-chain checks remain mandatory. Launch
commands embed their environment; runtime imports never set resource caps.

CPU commands use `nice -n 19 taskset -c 8-15,24-31 python3 -B`,
`OMP_NUM_THREADS=2` and stdin `/dev/null`. CPU-only capped mains use 4 GiB;
positive native-limit probes must start uncapped and allocate only metadata.
Compiler turns go through `ops/compile_turn.py`. Root must stay above 25 GB,
and build storage below 300 MB.

Reproduction order:

1. Bundle `cpu_prepare.py reuse_build.py cpu_gate.py prepare_chain.py full_shape.py startup103.py`.
2. Here, `seal_view.py`, `prepare.py`, `argument_gate.py`, `launch_limit_gate.py`.
3. `orchestrate.py` runs CPU tests, temporary proposal/chain plans and entry tests;
   then `final_audit.py` verifies all preparation and records pending evidence.
4. After device evidence arrives, only `orchestrate.py --evidence-only` and
   `verify_ready.py` remain. Source changes invalidate preparation receipts.

The chain folder `build/device-cards01-a` must remain fresh. The explicit
coordinator command is in `ready.json`; it passes verified readiness before
starting. This preparation neither starts a unit nor authorizes a launch.

`prepare_submission.py --chain <registered completed chain> --output <fresh
submission folder>` builds a portable, hash-bound evidence bundle and promotion
attestation. `submission.py --help` exposes the complete submission CLI.
Notes name the superseded record, separate quantized model, exact oracle,
BF16 KV, unchanged full target verifier and preregistered non-benchmark prefix.
The retained owner-authorized 128-token scope is honest:
`realistic_final_gate.passed=false`; it is not a strict512 claim. Preparation
never submits anything or changes a public record.

The shared K2 native CPU fixture exceeds the task's 4-GiB cap. Its startup row
reuses packet124c's verified archive and byte-identical binary, explicitly
labeled `fresh_native_run=false`. Other startup paths run locally. K2's actual
Python argument path and retained timing-receipt replay still execute in the
extended gate. The cap was not raised; the original CPU allocation refusal
and successful cleanup are retained in this packet's evidence.
