# Packet155c: bundle9 two-card record chain

Bundle9 keeps packet136 bundle8 and adds packet153's static snapshot descriptors
(`snapshot_host=static`, instrumentation `probe=off`). The target arithmetic is
`iq3-p49-split32-v1`, BF16 KV, draft prefix 80,128, rank1 draft, target split 24+24.
Both packet153 executables and their native sources are copied locally and pinned
by `inputs/packet153-native.json`. No new model performance is claimed here.

The final `ready.json` and `READY-FOR-DEVICE.json` govern admission. Run
`verify_ready.py` immediately before launch: it verifies current CPU/source pins
and recomputes packet153's real bracket from oracle tokens, timestamps and draft
proposal traces. All five views (65 checks) must be exact. Each static view must
beat every control by at least 0.2%, with at most 1% control drift. The retained
screen gives 58.874008 and 58.878497 versus 58.637969, 58.671236 and 58.663023:
minimum +0.34561%, drift 0.05673%. The original screen's separate qualification
flag does not decide this chain.

The coordinator explicitly chose the lab's idle-lane exception to the normal
+2% record-chain rule in the October 19 packet155c brief. This admits the chain
only. The fresh chain's WS128 must exceed **58.798109** and every exactness gate
must pass before any submission. The record remains `cmve4dtir007wrf01k57sdf23`.
Scope is 128 tokens; strict512 and `realistic_final_gate.passed` remain false.
Packet150's 0.743 ms/cycle capture_snapshot host attribution is context, not a
promised gain.

## Coordinator handoff

Lane **A**, physical cards **0+1**, exactly as packet136. The output must be new:
`stage2/packet155-record-bundle9/build/device-cards01-p155-a`. The service name
must be `packet155-chain-a`; environment and unit mismatches refuse. Preserve
packet136's lane reservation/drain protocol and exclusive whole-host timing
windows. This preparation has not queued or launched anything. Do not append
`proposal.jsonl` to a live queue: it is an entry-check descriptor, and the chain
waiter should execute `ready.json.chain_command` below.

```bash
systemd-run --user --unit=packet155-chain-a --property=Restart=no --property=Nice=0 '--property=CPUAffinity=0-3 16-19' --property=KillMode=process --property=SendSIGKILL=no --property=ExitType=cgroup --property=TimeoutStopSec=infinity --working-directory=/home/steve/llm-optimizations /usr/bin/taskset -c 0-3,16-19 /usr/bin/bash /home/steve/llm-optimizations/experiments/own-xpu-runtime/ops/packet155-orchestration/device-entry.sh chain /home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet155-record-bundle9/build/device-cards01-p155-a </dev/null
```

`device-entry.sh` rechecks readiness, constructs the closed library environment,
and enters the packet-local `coordinator_windows.sh`, which routes to
`chain_entry.py`. The eleven windows, in order, are K0, K1a, K1b, K2, W0p, KD,
W2m, WS, WSs, WS128x and WS128. Their argv, contexts, repeats, retention and
oracle/prefix prerequisites match packet136. No retry, resume or automatic
submission is registered. Each completed request checks stream presence,
format and exactness; elapsed wall time is never a data-proof gate. Ordinary
cooperative watchdogs and fault handling remain intact.

## CPU reproduction

Use `nice -n 19 taskset -c 8-15,24-31 python3 -B`, stdin `/dev/null`, and at most
4 GiB. Stop CPU preparation below 27 GB free. Device admission preserves 25 GB
plus the remaining measured write reserve. `storage-measurements.json` counts
packet136 retained bytes, archived/deleted original bytes and the largest
concurrent raw request state; planned windows use 1.25 times that conservative
peak, below the three-times limit. Earlier disk-stop evidence is historical.

The current receipts cover GNU/Intel state and production-size descriptor
checks; real Python arguments through all eleven native launch boundaries;
real queue-loop/input/oracle checks; both ranks' device-branch CPU preparation
and first decode; exact environment/unit refusal tests; native loader/parser
checks; unchanged resource-limit inheritance; and real packet136/153 reports.
The preparation probe replaces weight payloads and transport with numerical
CPU buffers. Its generated code and build command are retained under
`build/preparation155` and bound by `evidence/preparation-build.json`; it does
not replace either inference binary. The sandbox grants the specifically
hash-checked packet136 rotary constant through the shared checker's existing
rotary-input allowance.

The frozen `../rehearse_entry.py --report proposal.jsonl` passes all four
packaging checks and both native entries but does not support two-card chain
reports (it supports v5 screens and packet58 one-card reports). Its refusal is
retained in `evidence/shared-entry-report.json`. `rehearse_entry155.py --report
proposal.jsonl` calls those same checks unchanged and adds only the missing
report adapter. The adapter runs the real suite summarizer and exact-output
reader on packet136, plus packet153's raw-evidence verifier, in a fresh process
with the real closed environment and an audit guard forbidding writes, devices,
and subprocesses. `entry155.py` separately proves the actual coordinator unit
and all eleven Python entry paths. Generic `screen-*` wrapper labels in the
shared report are not launch instructions.

After any code edit, reseal with `seal155.py`, rerun affected gates, then run
`finalize155.py`. Write READY markers **last** with `write_ready.py`.

## Submission rehearsal and future preparation

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/ops/packet155-orchestration/prepare_submission.py --rehearse-packet136 </dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/ops/packet155-orchestration/prepare_submission.py --chain /home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet155-record-bundle9/build/device-cards01-p155-a --output experiments/own-xpu-runtime/stage2/packet155-record-bundle9/submission/prepared-a </dev/null
```

The first command replays a byte-identical copy of packet136's real evidence
through the final helper under its historical identity, then proves that the
current record floor and tampered-output controls refuse. It never relabels
those measurements as packet155. The second command is for the coordinator
after a finished chain. It prepares artifacts only and never posts. The private
helper retains packet136s's oracle-binding repair and the repository-root fix.

`evidence/packet136-chain-evidence.json.gz` (5.6 MB) is retained because the
rehearsal depends on its original receipt bytes. Restore by copying
`stage2/packet136-record-bundle/submission/prepared-a/evidence.json.gz`, then
check the hash in `evidence/submission-rehearsal.json`. The larger source census,
input closure, and initial pin receipt are preparation evidence, not caches;
their hashes and original failed steps are retained for audit. Parked unused
helpers are under `lineage-p155-scaffolding/` and do not control admission.
