# Resume scope takes precedence

All already-passing commands below are historical reproduction instructions,
not instructions to rerun them during this resume. Parse and hash their receipts.
The only new target-model execution is resume_intel_composite.py. Required
new draft-head references are resume_draft_references.py. New final-seal
admission checks execute no model/device binaries. See CLOSEOUT.md.

# CPU reproduction: ordered, serial, no device execution

These are reproduction commands, not a statement that the gates have passed.
The final `build-receipt.json` and `CLOSEOUT.md` carry the observed outcome.
Run from `/home/steve/llm-optimizations` after coordinating the host CPU slots.
Keep the inherited CPU affinity. Do not add `taskset`, device selectors, device
probes, `torch.xpu`, or oneAPI environment setup. The `device` build below only
compiles and links; never execute anything in `build/device/` on this path.

The sequence uses one compiler or one gate runner at a time. Compilation uses
`-j1`; at most two compile jobs are permitted if another coordinator explicitly
schedules parallel work. The resumed job may own at most two CPU-bound model processes;
other coordinator CPU jobs are sharing memory bandwidth. Runtime gates may own two rank processes. Keep
aggregate anonymous memory below 10 GB. The gate monitor's own 8 GB ceiling is
not permission to exceed that host-wide limit.

Prerequisites are the existing GNU compiler, CMake, Intel compiler at
`/opt/intel/oneapi/compiler/2026.0/bin/icpx` (and its `latest` alias for the
standalone selection gate), LLVM22 clang++ at the path in
`build_native_controller.py`, `/home/steve/.venvs/vllm-xpu/bin/python`, the
read-only packet1 tensor contract, the admitted local target/official draft
weights, the packet38 captured development inputs, both suite manifests and
their CPU oracle directories. `build.py prepare` uses that Python environment
for the local GGUF/tokenizer readers. No downloads or device discovery occur.
The capture provenance needed by `capacity_draft_gate.py` is
`../packet38-integrated/build/captured-incident-retrospective` plus its sealed
capture receipt; missing local inputs must be restored from their recorded
provenance, never synthesized and called an oracle.

Use these shell helpers. Every external command runs at nice 19/idle I/O with
OMP 2. `packet44_admit` checks root free space and the stricter 4 GB CPU build
cap before each write phase. Stop below 8 GB root free or at the build cap;
do not remove unrelated files to make space. Keep watching disk during large
phases, since other jobs share the filesystem. The coordinator's later window
cap is 6 GB; it does not replace this 4 GB preparation limit.

```bash
packet44=/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet44-context
packet44_cpu=(nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 ASAN_OPTIONS=detect_leaks=1:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1 python3 -B)
packet44_admit() {
  nice -n 19 ionice -c 3 df -B1 / || return
  "${packet44_cpu[@]}" - "$packet44" <<'PY_CHECK'
import pathlib, shutil, sys
p=pathlib.Path(sys.argv[1])/'build'
size=sum(f.stat().st_size for f in p.rglob('*') if f.is_file()) if p.exists() else 0
free=shutil.disk_usage('/').free
if free < 8_000_000_000 or size >= 4_000_000_000:
    raise SystemExit(f'STOP: root free={free}; packet build bytes={size}; floor 8 GB/cap 4 GB')
print(f'CPU admission: root free={free}; packet build bytes={size}')
PY_CHECK
}
packet44_run() {
  packet44_admit && "${packet44_cpu[@]}" "$packet44/$1" "${@:2}"
}
```

Run the following groups in order, stopping on any nonzero return code. Do not
queue the next group while the current one runs. Resolve a failed gate and
repeat its affected dependencies; do not carry an old successful receipt over
a changed source or binary. `seal_context.py` rejects stale identities.

```bash
packet44_run generate_rope.py
packet44_run build.py prepare
packet44_run final_build.py gnu-host
packet44_run final_build.py icpx-host
packet44_run final_build.py asan
packet44_run final_build.py device
packet44_run build_native_controller.py
packet44_run run_native_gates.py
packet44_run cpu_gates.py
packet44_run prepared_unit_gate.py
packet44_run capture_gate.py
```

`generate_rope.py` checks the arithmetic-v2 4096-position prefix and writes the
32768-position table. `capture_gate.py` only inspects the device image and
compiles an intentionally oversized capture; it never runs the image. Native
controller coverage is six CPU binaries: controller and mailbox-fault tests,
each normal GNU, ASAN/UBSAN GNU and LLVM TSAN. Precision flags are checked on
both compile and link. No device library path is needed for host execution.

Run full fixture qualification before deleting compiler objects. A fixture
failure can require a rebuild, so deleting objects earlier creates unnecessary
large recompiles. These commands run their compiler arms serially.

```bash
packet44_run capacity_selection_gate.py
packet44_run capacity_fixture_gate.py --phase all --compiler both
packet44_run gates.py mini gnu-host
packet44_run gates.py mini icpx-host
packet44_run gates.py mini asan
packet44_run mtp_gates.py gnu-host
packet44_run mtp_gates.py icpx-host
packet44_run mtp_gates.py asan
packet44_run native_mini_gate.py --binary "$packet44/build/gnu-host/own-rt-iq3" --output "$packet44/native-mini-cpu.json"
packet44_run cleanup_objects.py
```

The selection gate independently compiles GNU/icpx, compares arithmetic-v2
selection and attention, hashes its executable/output, writes the receipt,
compresses its raw output and deletes its standalone scratch. The fixture gate
covers six full nongemv arms (three capacities, two compilers), two linked-p33
arms, three K2 registration arms and the remaining validation arm, plus light
wrapper/selection tests. It writes each arm's receipt and compressed evidence
before deleting scratch. Mini and MTP sanitizer gates use host binaries only.
`cleanup_objects.py` records hashes before removing regenerable `.o` files;
it preserves binaries, compile commands and link proof. Do not rebuild again
unless a source correction actually requires it.

The coordinator reduced the resumed CPU plan on 2026-10-12. Do not rerun the
completed GNU matrix or expand the Intel matrix. The retained 25 cases are
verified by parsing/hash only. See resume-receipt-verification.json. Exactly
one Intel composite and the two needed GNU draft references remain authorized:

```bash
packet44_run resume_intel_composite.py
packet44_run resume_draft_references.py
```

Run sequentially, at most two model rank processes. The Intel diagnostic uses
four tokens at capacity 4,096 and real MTP, with two forced mailbox misses;
192 retained layer files must equal the oracle. The native controller lacks
that diagnostic override, so this one request uses its Python peer. GNU native
MTP and both-compilers' native-controller gates remain separately required.

The draft runner uses confirmed captured streams, not another target-model
request. Keep build/draft-reference-c4096 and build/draft-reference-c32768 plus
the captured streams and table for KD. The original capacity_cpu_gate.py and
six-arm capacity_draft_gate.py remain available for future explicitly expanded
qualification, but are not the resumed plan. The waived Intel matrix is never
reported as passed.

Generate the inherited pure-Python receipt with this exact serial driver. It
retains compressed stdout/stderr immediately after hashing; any failure makes
the aggregate fail. It executes no model binary itself.

```bash
packet44_admit && "${packet44_cpu[@]}" - "$packet44" <<'PY_INHERITED'
import gzip, hashlib, json, os, pathlib, subprocess, sys
p=pathlib.Path(sys.argv[1]); rows=[]
for name in ('math_gate.py','queue_gate.py','test_state_machine.py',
             'test_mtp_controller.py','test_submission_overlay.py',
             'test_cleanup_paths.py','test_state_retention.py','test_suite_warmup.py'):
    r=subprocess.run(['nice','-n','19','ionice','-c','3',sys.executable,'-B',str(p/name)],
                     cwd=p,env=os.environ.copy(),stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    raw=r.stdout
    rows.append(dict(script=name,returncode=r.returncode,raw_sha256=hashlib.sha256(raw).hexdigest()))
    (p/(name+'.log.gz')).write_bytes(gzip.compress(raw,mtime=0))
    (p/'inherited-python-gates.json').write_text(json.dumps(dict(
        passed=len(rows)==8 and all(x['returncode']==0 for x in rows),
        rows=rows,device_executed=False),indent=2)+'\n')
    if r.returncode: raise SystemExit(raw.decode(errors='replace'))
PY_INHERITED
```

The following wrapper tests mock device contact, journals, launches and memory
snapshots. The sole inherited host profiling case is excluded here because
runtime qualification is handled separately. Both contexts' complete window
rehearsals, including summaries, storage refusal and post-run compression
failure, are exercised by `context_window_gate.py`.

```bash
packet44_run context_window_gate.py
packet44_admit && "${packet44_cpu[@]}" - "$packet44" <<'PY_WRAPPER'
import json, pathlib, sys, unittest
p=pathlib.Path(sys.argv[1]);sys.path.insert(0,str(p))
import test_window
names=unittest.defaultTestLoader.getTestCaseNames(test_window.Gate)
suite=unittest.TestSuite(test_window.Gate(n) for n in names if n!='test_class_diagnostic_contract')
r=unittest.TextTestRunner(verbosity=2).run(suite)
(p/'window-mocked-inherited-tests.json').write_text(json.dumps(dict(
    passed=r.wasSuccessful(),tests=r.testsRun,device_executed=False,
    excluded='test_class_diagnostic_contract invokes host binary; reserved for CPU runtime gate'),indent=2)+'\n')
raise SystemExit(not r.wasSuccessful())
PY_WRAPPER
```

Recompute the byte plan and exercise its 27 admission boundaries. These are
allocation arithmetic checks, not a physical residency measurement.

```bash
packet44_run memory_plan.py
packet44_admit && "${packet44_cpu[@]}" - "$packet44" <<'PY_MEMORY'
import hashlib, json, pathlib, sys
p=pathlib.Path(sys.argv[1]);sys.path.insert(0,str(p))
from memory_gate import check
ledger=json.loads((p/'memory-plan.json').read_text()); checks=0
def census(n):return dict(totals=dict(device=n),allocations=[dict(bytes=n,live=True,memory='device')])
for context in (256,4096,32768):
    for rank in (0,1):
        for mtp in (False,True):
            row=ledger['capacities'][str(context)]['ranks'][rank]
            n=row['total_with_mtp_bytes'] if rank==1 and mtp else row['target_total_bytes']
            assert check(census(n),ledger,rank,mtp,context)['passed'];checks+=1
            try:check(census(n+1),ledger,rank,mtp,context)
            except ValueError:checks+=1
            else:raise AssertionError('over-plan allocation admitted')
    try:check(census(1),ledger,0,False,context+1)
    except ValueError:checks+=1
    else:raise AssertionError('unlisted context admitted')
assert checks==27
(p/'memory-plan-gates.json').write_text(json.dumps(dict(passed=True,
    device_executed=False,checks=checks,
    memory_plan_sha256=hashlib.sha256((p/'memory-plan.json').read_bytes()).hexdigest(),
    scope='12 rank/context/draft admission successes; 12 over-plan rejections; 3 unlisted-context rejections'),indent=2)+'\n')
PY_MEMORY
packet44_run draft_auth_gate.py
packet44_run capacity_rollback_asan.py
packet44_run post_python_gates.py
packet44_run seal_context.py --bootstrap
packet44_run test_window_seal_admission.py --build-receipt "$packet44/build-admission-candidate.json"
packet44_run seal_context.py
packet44_run integration_inventory.py
packet44_admit
```

The seal checks gate completeness, arithmetic flags, argument size, source and
binary hashes and reference provenance. It writes `build-receipt.json`,
`cpu-tests.json` and `BINARY-HASHES.md` only after the required receipts pass.
The integration inventory lists every changed file against packet38 for the
packet40 merge. Regenerate it after any final documentation edits.

`WINDOW.md` is a separate coordinator-only sequence; none of its commands
belongs in this CPU run. Its `--context`, `--card`, prerequisite receipt paths,
`--input`, `--oracle`, `--dispatch`, suite manifest and native controller flags
match `window.py`. The only supplied device environment value is the existing
`LD_LIBRARY_PATH`, forwarded byte-for-byte. K2 uses six 4096 or seven 32768
lengths for every capacity-touching class; the historical 66-length range in
the copied registry is replaced by `registry_for_context`, including metadata,
and is never the active packet44 schedule. Actual device arithmetic, residency,
launch timing and real-context throughput remain coordinator gates.

Additional current gates, run serially before sealing:

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B "$packet44/draft_auth_gate.py"
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 ASAN_OPTIONS=detect_leaks=1:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1 python3 -B "$packet44/capacity_rollback_asan.py"
```

`remaining_cpu_gates.py` is the recorded serial driver for owner/capture,
mini/MTP (both compilers and sanitizer), draft authentication, exhaustive native
mini controller, both-compiler rollback and sanitizer rollback stages. It stops
at the first failure and records compressed logs; it does not retry.
