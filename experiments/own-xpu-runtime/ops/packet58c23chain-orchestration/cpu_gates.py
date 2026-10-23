#!/usr/bin/env python3
"""Packet58-onecard-cache23-chain CPU gates after the cache23 delta (phase 2). CPU only; never a device, service,
queue or PAUSE file; the only native executions are the host parser (--p58r-parse-test / --help) and ldd / the
device binary's --help inside the Landlock entry sandbox (no /dev/dri, no /mnt, no packet data).

  nice -n 19 taskset -c 8-15,24-31 python3 -B cpu_gates.py --all        run every gate in order, receipts in <packet>/evidence
  nice -n 19 taskset -c 8-15,24-31 python3 -B cpu_gates.py --step NAME  one gate
  nice -n 19 taskset -c 8-15,24-31 python3 -B cpu_gates.py --check      verify every receipt exists and passed

Gate (receipt)                       What it proves on the FINAL packet bytes
  argument   script-argv-check.json   suite_driver.py run as a script per model window (native Popen intercepted): the
                                      native argv carries --wait-policy spin --foreground-io kernel --cache-cap max23
                                      --cache-bytes 23049601024 exactly once each (the chain-176-a defect class)
  parser     chain-flags.json         the generator's real-parser gate re-run on the final sources: the cache23 host
                                      parser accepts every model-window argv, refuses an invalid flag value, parses
                                      without each flag (chain-flags.json is rewritten; same schema, same flags)
  help       help-cache23.json        device --help (Landlock sandbox, from the derivation) and host --help list
                                      --cache-cap 18GB|max|max23, --cache-bytes, --wait-policy, --foreground-io
  predevice  predevice-cache23.json   the generator's pre-device rehearsal (window.main of all 7 windows up to the
                                      device boundary) on the final packet with the cache23 memory plan
  closure    closure-cache23.json     the generator's runtime-read closure check against the parent packet
  postnative postnative-cache23.json  window.k1_summary on the screen's K1a/K1b and window.postload_observation with
                                      THIS packet's WS128 plan on the screen's real WSCREEN evidence (23,049,601,024-
                                      byte arena census): the plan admits the measured 23 GB post-load state; the
                                      generator's 21.55 GB rehearsal on packet182c's chain stays in the orchestration
  drain      drain-fix.json           scripts/check_drain_fix.py on the packet (0 UNFIXED)
  launch     launch-limits.json       ldd of the three binaries under the closed loader environment (entry sandbox),
                                      exec_limits.check(), the chain command's systemd/taskset/env -i properties,
                                      LD_LIBRARY_PATH == library-path.json, nothing executes a device
  python     python-cpu-gates-cache23.json  unittest discover on the packet (0 failures) and the same suite on a
                                      git-archive scratch copy of packet182c-chain (inherited failure classes listed)
  admission  admission-gate.json      admission_gate.py --verify (the five screen views recomputed from raw data)
  engine     engine-binding-check.json engine-binding.json re-hashed: packet copies and cache23 sources unchanged
  submission submission-rehearsal-cache23.json  the packet's rehearse_submission.py (58ad real evidence replay with
                                      in-memory identity substitutions, final-location CLI --dry-run, notes <= 2000)
                                      plus packet182c's real chain bundle refused by this validator
  queue      queue-gate.json          queue_runner.py --plan (host floor 100,487,123,456; 7 windows; 90 s gaps) and a
                                      temporary lanequeue plan on the orchestration's entry-proposal (live queue untouched)
"""
import argparse, contextlib, gzip, hashlib, io, json, os, resource, shutil, subprocess, sys, tempfile, time
from pathlib import Path

ROOT = Path('/home/steve/llm-optimizations')
X = ROOT / 'experiments/own-xpu-runtime'
O = X / 'ops/packet58c23chain-orchestration'
P = X / 'stage2/packet58-onecard-cache23-chain'
P0 = X / 'stage2/packet58aj-onecard-resident'
SCREEN = X / 'stage2/packet58-onecard-cache23/screen/evidence/card0-58c23-v5-a/resident'
C182 = X / 'stage2/packet182c-chain'
EV = P / 'evidence'
FLAGS = {'--wait-policy': 'spin', '--foreground-io': 'kernel'}
CAPACITY = {'--cache-cap': 'max23', '--cache-bytes': '23049601024'}
HOST_FLOOR = 100487123456
CPU = ['nice', '-n', '19', 'taskset', '-c', '8-15,24-31']
sys.path.insert(0, str(X / 'ops'))
sys.path.insert(0, str(X / 'ops/lane-queue'))
import onecard_chain_derive as G  # noqa: E402

RECEIPTS = dict(argument='script-argv-check.json', parser='chain-flags.json', help='help-cache23.json', predevice='predevice-cache23.json',
                closure='closure-cache23.json', postnative='postnative-cache23.json', drain='drain-fix.json', launch='launch-limits.json',
                python='python-cpu-gates-cache23.json', admission='admission-gate.json', engine='engine-binding-check.json',
                submission='submission-rehearsal-cache23.json', queue='queue-gate.json')
ORDER = list(RECEIPTS)
# phase a gates never call window.build_gate (the seal is stale between apply_cache23_chain_delta.py and reseal.py); phase b gates do.
PHASES = dict(a=['argument', 'parser', 'help', 'admission', 'engine', 'submission', 'drain', 'launch', 'python'], b=['predevice', 'closure', 'postnative', 'queue'])


def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def rel(p):
    return str(Path(p).relative_to(ROOT))


def save(name, row):
    row = dict(schema=f'packet58cache23chain.gate.{name}.v1', **row)
    row.setdefault('device_executed', False)
    (EV / RECEIPTS[name]).write_text(json.dumps(row, indent=2) + '\n')
    return row


def run(cmd, cwd=ROOT, env=None, timeout=1800):
    return subprocess.run(list(map(str, cmd)), cwd=cwd, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout,
                          env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1', **(env or {})))


def closed_env():
    sys.path.insert(0, str(P))
    import launch_env
    return launch_env.environment()


def gate_argument():
    out = EV / 'script-argv-check.json'
    cp = run([*CPU, 'python3', '-B', O / 'script_argv_check.py', P, '--flags', json.dumps({**FLAGS, **CAPACITY}), '--json', out])
    row = json.loads(out.read_text()) if out.is_file() else {}
    assert cp.returncode == 0 and row.get('passed') is True and len(row.get('windows', [])) == 5, cp.stdout + cp.stderr
    row.update(schema='packet58cache23chain.gate.argument.v1', tool_record=dict(name='script_argv_check.py', parent_relpath=rel(O / 'script_argv_check.py'), parent_digest=sha(O / 'script_argv_check.py')),
               tool_provenance=dict(name='script_argv_check.py', parent_relpath='experiments/own-xpu-runtime/stage2/packet182-onecard-kio-rebracket/chain/script_argv_check.py',
                                    parent_digest=sha(X / 'stage2/packet182-onecard-kio-rebracket/chain/script_argv_check.py')),
               required_flags={**FLAGS, **CAPACITY})
    out.write_text(json.dumps(row, indent=2) + '\n')
    return row


def gate_parser():
    records = G.parser_gate(P, FLAGS)
    for r in records:
        argv = r['actual_native_argv']
        for flag, value in {**FLAGS, **CAPACITY}.items():
            assert argv.count(flag) == 1 and argv[argv.index(flag) + 1] == value, f'{r["window"]}: {flag}'
        assert r['parser_receipt']['cache_allocation_bytes'] == 23049601024 if 'cache_allocation_bytes' in r['parser_receipt'] else True
    previous = json.loads((EV / 'chain-flags.json').read_text())
    row = dict(previous, passed=True, device_executed=False, model_reads=False, parser=records, binary_sha256=sha(P / 'build/device/own-rt-iq3'),
               host_binary_sha256=sha(P / 'build/gnu-host/own-rt-iq3'), capacity_argv=CAPACITY,
               rerun='phase 2 (after apply_cache23_chain_delta.py) on the final sources; the derivation-time run is derivation.json/capacity-patch.json')
    (EV / 'chain-flags.json').write_text(json.dumps(row, indent=2) + '\n')
    return row


def gate_help():
    env = closed_env()
    hp = subprocess.run([str(P / 'build/gnu-host/own-rt-iq3'), '--help'], stdin=subprocess.DEVNULL, capture_output=True, text=True, env=env, timeout=60)
    device_help = json.loads((O / 'help.json').read_text())['device']
    need = ['--cache-cap', '18GB|max|max23', '--cache-bytes', '--wait-policy', '--foreground-io']
    host_ok = hp.returncode == 0 and all(n in hp.stdout.split() for n in need)
    device_ok = all(n in device_help.split() for n in need)
    assert host_ok and device_ok, (hp.returncode, [n for n in need if n not in hp.stdout.split()], [n for n in need if n not in device_help.split()])
    return save('help', dict(passed=True, host_binary_sha256=sha(P / 'build/gnu-host/own-rt-iq3'), device_binary_sha256=sha(P / 'build/device/own-rt-iq3'),
                             required_tokens=need, host_help_listed=True, device_help_listed=True,
                             device_help_source=dict(name='help.json', parent_relpath=rel(O / 'help.json'), parent_digest=sha(O / 'help.json'), note='captured by the generator inside the Landlock entry sandbox'),
                             host_help=hp.stdout))


def gate_predevice():
    row = G.predevice_gate(P)
    return save('predevice', dict(passed=True, generator='ops/onecard_chain_derive.py predevice_gate', memory_plan='cache23 (apply_cache23_chain_delta.py)',
                                  windows=row['windows'], records=row['records'], simulated=['priority', 'affinity', 'user_unit_gate']))


def gate_closure():
    missing, checked = G.closure_check(P, P0, ROOT)
    assert not missing, missing[:10]
    return save('closure', dict(passed=True, checked=checked, parent=P0.name, missing=[]))


def gate_postnative():
    sys.path.insert(0, str(P))
    for m in ('window', 'memory_plan', 'legacy_memory_plan', 'onecard_admission', 'views', 'exec_limits', 'owner_teardown', 'p56_head_support'):
        sys.modules.pop(m, None)
    import window as W
    rows = []
    for name in ('K1a', 'K1b'):
        src = SCREEN / name
        stored = json.loads((src / 'summary.json').read_text())
        summary = W.k1_summary(json.loads((src / 'run/k1.json').read_text()))
        assert summary.get('passed') is True, name
        same = {k: stored.get(k) == summary.get(k) for k in summary}
        rows.append(dict(window=name, passed=True, keys=len(summary), equal_to_screen_summary=all(same.values()), differing_keys=[k for k, v in same.items() if not v]))
    src = SCREEN / 'WSCREEN'
    w = json.loads((src / 'window.json').read_text())
    budget = W.M.window_plan('WS128')
    assert budget['host_required_available_bytes'] == HOST_FLOOR and W.M.CACHE_BYTES == 23049601024
    with tempfile.TemporaryDirectory(prefix='p58c23-postnative-', dir=P / 'build') as tmp:
        out = Path(tmp) / 'WSCREEN'
        shutil.copytree(src, out, symlinks=True, ignore=shutil.ignore_patterns('native-home'))
        observation = W.postload_observation(out, budget, w['memory_admission'])
    stored = w['postload_memory']
    compare = {k: observation[k] == stored[k] for k in observation if k in stored}   # the screen harness predates the exact_half_decode_table_bytes key
    assert observation['full_cache_bytes'] == 23049601024 and observation['complete_postload'] is True and observation['exact_half_decode_table_bytes'] == 262144 \
        and len(compare) >= 9 and all(compare.values()), [k for k, v in compare.items() if not v]
    rows.append(dict(window='WSCREEN', passed=True, plan_window='WS128', full_cache_bytes=observation['full_cache_bytes'], kv_bytes=observation['kv_bytes'],
                     pinned_expert_bytes=observation['pinned_expert_bytes'], peak_shadow_bytes=observation['peak_shadow_bytes'],
                     equal_to_screen_postload_memory=True, compared_keys=sorted(compare), keys_absent_in_screen_receipt=sorted(set(observation) - set(stored)), sources=observation['sources']))
    return save('postnative', dict(passed=True, evidence=rel(SCREEN), evidence_files=[dict(name=f.name, parent_relpath=rel(f), parent_digest=sha(f)) for f in (src / 'window.json', src / 'summary.json')],
                                   budget=dict(host_required_available_bytes=budget['host_required_available_bytes'], device_owned_bound_bytes=budget['device_owned_bound_bytes'],
                                               expert_cache_arena=budget['device_categories']['expert_cache_arena'], driver_allowance_bytes=budget['driver_allowance_bytes']),
                                   records=rows,
                                   generator_rehearsal=dict(name='postnative-rehearsal.json', parent_relpath=rel(O / 'postnative-rehearsal.json'), parent_digest=sha(O / 'postnative-rehearsal.json'),
                                                            note='packet182c real chain (21.55 GB arena) with the parent plan at derivation time')))


def gate_drain():
    cp = run(['python3', '-B', ROOT / 'scripts/check_drain_fix.py', rel(P), '--json'])
    try:
        report = json.loads(cp.stdout)
    except ValueError:
        report = dict(raw=cp.stdout[-2000:])
    ok = cp.returncode == 0 and isinstance(report, dict) and report.get('passed') is True and report.get('counts', {}).get('UNFIXED') == 0 and report.get('counts', {}).get('FIXED', 0) >= 1
    assert ok, cp.stdout[-800:] + cp.stderr[-800:]
    return save('drain', dict(passed=True, returncode=cp.returncode, report=report, checker_sha256=sha(ROOT / 'scripts/check_drain_fix.py')))


def gate_launch():
    sys.path.insert(0, str(P))
    import launch_env, exec_limits
    binaries = {}
    for leaf in ('build/device/own-rt-iq3', 'build/gnu-host/own-rt-iq3', 'build/device/p58-cache-fixtures'):
        r = launch_env.check_binary(P / leaf)
        assert r['passed'], (leaf, r)
        binaries[leaf] = dict(sha256=sha(P / leaf), ldd=r)
    limits = exec_limits.check()
    derived = json.loads((P / 'derived-chain.json').read_text())
    cmd = derived['chain_command']
    lib = json.loads((P / 'library-path.json').read_text())['LD_LIBRARY_PATH']
    props = ['--unit=packet58-onecard-cache23-a', '--property=Restart=no', '--property=SendSIGKILL=no', '--property=TimeoutStopSec=infinity', '--property=Nice=0',
             '--working-directory=/home/steve/llm-optimizations', '/usr/bin/taskset -c 0-3,16-19 /usr/bin/env -i PATH=/usr/bin:/bin LD_LIBRARY_PATH=' + lib + ' OMP_NUM_THREADS=2',
             str(P / 'queue_runner.py') + ' --authorized-device-window --card 0 --view down-tile16 --output-root ' + str(P / 'evidence/card0-cache23-a'),
             '--fault-review ' + str(P / 'evidence/fault-review-cache23-a.json') + ' < /dev/null']
    assert all(p in cmd for p in props) and '$' not in cmd and cmd.startswith('systemd-run --user '), cmd
    assert lib == launch_env.library_path()
    ready_file = next(f for f in (O / 'READY-FOR-DEVICE.json', O / 'derivation-READY-FOR-DEVICE.json') if f.is_file())
    ready = json.loads(ready_file.read_text())
    assert hashlib.sha256(cmd.encode()).hexdigest() == ready['chain_command_digest_sha256'] and ready['chain_command'] == cmd, 'chain command differs from the derivation READY'
    import window as W
    writes = sum(W.WRITES['K1' if n.startswith('K1') else n] for n in ('K1a', 'K1b', 'KD', 'W2m', 'WS', 'WS128x', 'WS128'))
    return save('launch', dict(passed=True, binaries=binaries, rlimits=limits, chain_command_digest_sha256=hashlib.sha256(cmd.encode()).hexdigest(),
                               properties_checked=props, library_path_equals_recorded=True, planned_write_bytes=writes,
                               host_floor_bytes=HOST_FLOOR, launcher_host_floor_bytes=HOST_FLOOR + 1073741824,
                               root_free_floor_bytes=25_000_000_000 + writes, native_executed='ldd/--help only, inside the entry sandbox'))


def unittest_in(directory, tag):
    cp = run([*CPU, 'python3', '-B', '-m', 'unittest', 'discover', '-s', directory, '-p', 'test_*.py'], cwd=directory, timeout=1800)
    text = cp.stdout + cp.stderr
    summary = next((l for l in reversed(text.splitlines()) if l.startswith(('OK', 'FAILED'))), '')
    ran = next((l for l in text.splitlines() if l.startswith('Ran ')), '')
    failed = sorted({l.split(' ', 1)[1].split(' (')[0] + ' (' + l.split('(')[1].rstrip(')') + ')' for l in text.splitlines() if l.startswith(('FAIL: ', 'ERROR: '))})
    causes = {}
    for l in text.splitlines():
        if l.startswith(('ValueError', 'AssertionError', 'AttributeError', 'FileNotFoundError', 'KeyError', 'TypeError', 'ModuleNotFoundError', 'ImportError')):
            causes[l[:120]] = causes.get(l[:120], 0) + 1
    return dict(tag=tag, returncode=cp.returncode, ran=ran, summary=summary, failed=failed, causes=causes, log_sha256=hashlib.sha256(text.encode()).hexdigest())


def gate_python():
    mine = unittest_in(P, 'packet58-onecard-cache23-chain')
    assert mine['returncode'] == 0 and mine['summary'].startswith('OK'), mine
    with tempfile.TemporaryDirectory(prefix='p58c23-p182c-', dir=P / 'build') as tmp:
        tar = subprocess.run(['git', '-C', str(ROOT), 'archive', 'HEAD', rel(C182)], capture_output=True, check=True).stdout
        subprocess.run(['tar', '-x', '-C', tmp, '--exclude=' + rel(C182) + '/evidence/card0-182-a', '--exclude=' + rel(C182) + '/submission'], input=tar, check=True)
        copy = Path(tmp) / rel(C182)
        shutil.copytree(C182 / 'build', copy / 'build')
        theirs = unittest_in(copy, 'packet182c-chain (git archive HEAD scratch copy + its build/)')
    inherited = sorted(set(mine['failed']) & set(theirs['failed']))
    return save('python', dict(passed=True, mine=mine, packet182c=theirs, inherited_failures_still_failing_here=inherited,
                               adaptation='test_submission synthetic fixture carries the generated chain flags; test_ready bracket-evaluation tests skipped on the '
                                          'generated verify_ready; parent test fixtures evidence/postload-census.json and evidence/58c-kd/run/progress.jsonl copied; '
                                          'cache23 values in test_submission/test_resident/test_memory_*/test_admission58e (evidence/cache23-chain-delta.json)',
                               sources={rel(f): sha(f) for f in sorted(P.glob('test_*.py'))}))


def gate_admission():
    cp = run([*CPU, 'python3', '-B', O / 'admission_gate.py', '--verify'])
    assert cp.returncode == 0, cp.stdout + cp.stderr
    row = json.loads((EV / 'admission-gate.json').read_text())
    row['verified_at_gate_run'] = json.loads(cp.stdout.strip().splitlines()[-1])
    (EV / 'admission-gate.json').write_text(json.dumps(row, indent=2) + '\n')
    return row


def gate_engine():
    b = json.loads((P / 'engine-binding.json').read_text())
    checks = {}
    for key in ('engine', 'host_parser', 'k1_fixture'):
        item = b[key]
        checks[item['path']] = dict(packet_copy=sha(P / item['path']) == item['sha256'], source=sha(ROOT / item['source']['parent_relpath']) == item['source']['parent_digest'])
    for rec in b['cache23_provenance']:
        checks[rec['parent_relpath']] = dict(source=sha(ROOT / rec['parent_relpath']) == rec['parent_digest'])
    assert all(all(v.values()) for v in checks.values()), checks
    return save('engine', dict(passed=True, engine_binding_sha256=sha(P / 'engine-binding.json'), checks=checks, compiled_here=False, compiler_runs=0))


def gate_submission():
    cp = run([*CPU, 'python3', '-B', P / 'rehearse_submission.py'], cwd=P, timeout=1800)
    assert cp.returncode == 0 and (EV / 'submission-rehearsal-cache23.json').is_file(), cp.stdout[-1500:] + cp.stderr[-1500:]
    row = json.loads((EV / 'submission-rehearsal-cache23.json').read_text())
    assert row['passed'] is True and row['notes_characters'] <= 2000 and row['payload_written'] is False and row['network_used'] is False
    # Negative: packet182c's real record bundle (21.55 GB line) through THIS validator, in memory.
    sys.path.insert(0, str(P))
    for m in ('packet58_submission', 'suite_metrics', 'composition'):
        sys.modules.pop(m, None)
    import packet58_submission as S
    bundle = C182 / 'submission/chain-a/evidence.json.gz'
    members = json.loads(gzip.decompress(bundle.read_bytes()))['members']
    refusal = None
    try:
        S.derive(S.Evidence(members))
    except (ValueError, KeyError) as e:
        refusal = type(e).__name__ + ': ' + str(e)[:200]
    assert refusal, 'packet182c real bundle must be refused by this validator'
    cap = dict(label=S.derive.__module__, old_argv_refused_by_tests=['--cache-cap max', '--cache-bytes 21552729600', '--cache-cap 18GB', '--cache-bytes 18000000000'])
    row.update(schema='packet58cache23chain.gate.submission.v1', device_executed=False,
               packet182c_real_bundle=dict(name=bundle.name, parent_relpath=rel(bundle), parent_digest=sha(bundle), refused=True, refusal=refusal),
               validator_sha256=sha(P / 'packet58_submission.py'), policy_sha256=sha(P / 'submission-policy.json'), capacity=cap,
               cli=dict(prepare='ops/packet58c23chain-orchestration/prepare_submission.py', submit='ops/packet58c23chain-orchestration/submission.py',
                        server_dry_run='not run on CPU (needs the key); coordinator step'))
    (EV / 'submission-rehearsal-cache23.json').write_text(json.dumps(row, indent=2) + '\n')
    return row


def gate_queue():
    env = closed_env()
    probe = P / 'evidence/.plan-probe'
    assert not probe.exists()
    cp = run(['python3', '-B', P / 'queue_runner.py', '--card', '0', '--view', 'down-tile16', '--output-root', probe, '--plan'],
             env=dict(LD_LIBRARY_PATH=env['LD_LIBRARY_PATH']), timeout=600)
    assert cp.returncode == 0 and not probe.exists(), cp.stdout[-800:] + cp.stderr[-800:]
    plan = json.loads(cp.stdout.strip().splitlines()[-1])
    assert plan['passed'] is True and plan['device_executed'] is False and plan['host_required_available_bytes'] == HOST_FLOOR \
        and plan['windows'] == ['K1a', 'K1b', 'KD', 'W2m', 'WS', 'WS128x', 'WS128'] and plan['gap_seconds'] == 90 and plan['scope'] == 'whole-host'
    for name in ('K1a', 'K1b', 'KD', 'W2m', 'WS', 'WS128x', 'WS128'):
        c = plan['commands'][name]
        timing = name.startswith('W')
        assert (c[0] == '/usr/bin/taskset' and '0-3,16-19' in c) if timing else (c[:3] == ['/usr/bin/nice', '-n', '19'] and '8-15,24-31' in c), name
        assert '--window' in c and str(probe / name) in c and '/usr/bin/env' in c and '-i' in c, name
    # entry-proposal: the generator wrote the parent's host floor; this packet's plan raises it (the lanequeue takes the maximum declared bound)
    job = json.loads((O / 'entry-proposal.jsonl').read_text().strip())
    job['plan']['host_required_available_bytes'] = HOST_FLOOR
    job['plan']['memory_plan'] = 'packet58-onecard-cache23 re-partition (admission.json); queue_runner --plan reports the same floor'
    (O / 'entry-proposal.jsonl').write_text(json.dumps(job) + '\n')
    with tempfile.TemporaryDirectory(prefix='p58c23-plan-', dir=P / 'build') as tmp:
        (Path(tmp) / 'queue-A.txt').write_text(json.dumps(job) + '\n')
        lq = run(['python3', '-B', X / 'ops/lane-queue/lanequeue.py', 'plan', '--lane', 'A', '--directory', tmp], timeout=900)
    rows = [json.loads(l) for l in lq.stdout.splitlines() if l.startswith('{')]
    assert lq.returncode == 0 and len(rows) == 1 and rows[0].get('plan') == 'passed' and rows[0]['host_required_available_bytes'] == HOST_FLOOR, lq.stdout[-800:] + lq.stderr[-800:]
    (O / 'queue-plan.log').write_text(lq.stdout + lq.stderr)
    return save('queue', dict(passed=True, plan={k: v for k, v in plan.items() if k != 'commands'}, ws128_command=plan['commands']['WS128'],
                              entry_proposal_sha256=sha(O / 'entry-proposal.jsonl'), lanequeue_plan=rows[0], lanequeue_sha256=sha(X / 'ops/lane-queue/lanequeue.py'),
                              live_queue_changed=False, launched_by='launch_chain.sh (systemd-run unit packet58-onecard-cache23-a), never a lane queue row'))


GATES = dict(argument=gate_argument, parser=gate_parser, help=gate_help, predevice=gate_predevice, closure=gate_closure, postnative=gate_postnative,
             drain=gate_drain, launch=gate_launch, python=gate_python, admission=gate_admission, engine=gate_engine, submission=gate_submission, queue=gate_queue)


def check():
    rows = {}
    for name, leaf in RECEIPTS.items():
        r = json.loads((EV / leaf).read_text())
        rows[name] = dict(receipt='evidence/' + leaf, passed=r.get('passed') is True, device_executed=r.get('device_executed'), sha256=sha(EV / leaf))
    ok = all(v['passed'] and v['device_executed'] is False for v in rows.values())
    return ok, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--step', choices=ORDER)
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--phase', choices=('a', 'b'), help='a: gates that do not read the seal (before reseal.py); b: seal-reading gates (after reseal.py)')
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19 and set(os.sched_getaffinity(0)) <= set(range(8, 16)) | set(range(24, 32)), 'run under nice -n 19 taskset -c 8-15,24-31'
    assert shutil.disk_usage('/').free >= 26_000_000_000, 'root below the 26 GB preparation floor'
    units = subprocess.run(['systemctl', '--user', 'list-units', '--no-legend', '--plain', '--state=active,activating', 'window-*', 'lanequeue-*', 'packet*'],
                           capture_output=True, text=True).stdout.strip()
    assert not units, 'device units active: ' + units
    if a.check:
        ok, rows = check()
        print(json.dumps(dict(passed=ok, gates=rows), indent=1))
        return 0 if ok else 1
    steps = ORDER if a.all else PHASES[a.phase] if a.phase else [a.step]
    for name in steps:
        t0 = time.monotonic()
        row = GATES[name]()
        print(f'{name}: PASS ({time.monotonic() - t0:.1f} s) -> evidence/{RECEIPTS[name]}', flush=True)
    return 0


if __name__ == '__main__':
    # no RLIMIT_AS here: exec_limits.check() (launch gate) requires the unlimited inherited limit; child gates set their own
    raise SystemExit(main())
