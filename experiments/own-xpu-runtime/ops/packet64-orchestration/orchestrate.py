"""Packet64 coordinator orchestration. Dry mode cannot invoke external programs."""
import argparse
import ast
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shlex
import signal
import subprocess
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
STAGE = Path('experiments/own-xpu-runtime/stage2')
PACKET = STAGE / 'packet64-record-bundle'
SCREEN = STAGE / 'screen/v3-packet64'
LANES = STAGE / 'screen/v3-packet64-lanes'
OUT = Path('/home/steve/own-xpu-runtime-results/packet64-record-bundle/build/device-cards01-a')
DRIVER = Path('experiments/own-xpu-runtime/stage1/packet4-prep/driver/window_driver.py')
METRIC = 'class_balanced_tok_s_1_100_intervals_after_ttft'
CHOICES = ('1-production-control', '1-draft-hc-control', '1-draft-hc-batch')
SLUGS = ('prod-ctl', 'drafthc-ctl', 'drafthc-batch')
PROMPTS = ('incident-retrospective', 'code-review', 'customer-email', 'sql-debugging',
           'release-plan', 'benchmark-analysis', 'architecture-tradeoff',
           'bug-report-synthesis', 'technical-guide', 'risk-register',
           'performance-hypotheses', 'decision-memo')
CPU = ['nice', '-n', '19', 'taskset', '-c', '8-15,24-31', 'python3', '-B']


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def screen_path(lane, choice):
    return SCREEN / 'evidence' / f'p64-1-{SLUGS[CHOICES.index(choice)]}-{lane}'


def evidence(root, lane, choice, boot):
    base = root / screen_path(lane, choice)
    window, summary = read(base / 'window.json'), read(base / 'summary.json')
    require(window.get('passed') is True and window.get('device_executed') is True
            and window.get('child_still_running') is False and not window.get('child_retained'),
            'window not passed/drained')
    require(window.get('boot_id') == boot and window.get('lane') == lane, 'window boot/lane mismatch')
    expected = (root / PACKET / 'selections' / choice).resolve()
    require(Path(window['identity']['lineage']).resolve() == expected, 'wrong selection lineage')
    require(window['identity']['selection_sha256'] == digest(expected / 'selection.json'),
            'selection identity changed')
    require(summary.get('passed') is True and summary.get('lane') == lane
            and summary.get('request_count') == 12 and summary.get('cached_tokens') == 0
            and summary.get('kv_dtype') == 'BF16'
            and summary.get('device_isolation', {}).get('passed') is True,
            'summary quality/isolation invalid')
    require(summary.get('incident64', {}).get('passed') is True, 'incident failed')
    require([row['prompt_id'] for row in summary['requests']] == list(PROMPTS), 'wrong prompt suite')
    receipts = sorted((base / 'run').glob('*/receipt.json'))
    require({p.parent.name for p in receipts} == {'incident64', *PROMPTS}, 'expected 13 distinct receipts')
    for path in [base / 'summary.json', *receipts]:
        require(window['files'].get(str(path.relative_to(base))) == digest(path), 'receipt/summary hash mismatch')
    require(all(read(p).get('exact_oracle') is True for p in receipts), 'not 13/13 exact')
    speed = summary[METRIC]['median']
    require(type(speed) in (int, float) and math.isfinite(speed) and speed > 0, 'invalid speed')
    return dict(tok_s=speed, exact=13, summary_sha256=digest(base / 'summary.json'), path=str(base))


def select(root, boot, log):
    rows, errors = {}, {}
    for lane in 'AB':
        rows[lane] = {}
        for choice in CHOICES:
            try:
                rows[lane][choice] = evidence(root, lane, choice, boot)
                log(f'SCREEN lane={lane} choice={choice} tok_s={rows[lane][choice]["tok_s"]:.9f} exact=13/13')
            except (ValueError, OSError, KeyError, TypeError) as error:
                errors[f'{lane}/{choice}'] = str(error)
                log(f'SCREEN INVALID lane={lane} choice={choice} reason={error}')
    require(all(CHOICES[0] in rows[lane] for lane in 'AB'), 'production evidence invalid; no chain launch')
    eligible = []
    for choice in CHOICES[1:]:
        if all(choice in rows[lane] for lane in 'AB'):
            gains = {lane: rows[lane][choice]['tok_s'] / rows[lane][CHOICES[0]]['tok_s'] - 1 for lane in 'AB'}
            log(f'COMPARE choice={choice} A_gain_pct={gains["A"]*100:.6f} B_gain_pct={gains["B"]*100:.6f}')
            if not errors and all(g > 0 for g in gains.values()):
                eligible.append((min(gains.values()), -CHOICES.index(choice), choice))
    chosen = max(eligible)[2] if eligible else CHOICES[0]
    log(f'SELECTION {chosen}; all_six_exact={not errors}; rule=strictly-ahead-on-both-lanes; tie=maximin-then-fewer-changes')
    return dict(choice=chosen, rows=rows, errors=errors, all_six_exact=not errors,
                diagnostic=True, promotion_eligible=False, boot_id=boot)


class Backend:
    def __init__(self, root, log, mock=None):
        self.root, self.log, self.mock = root, log, mock
        self.tick = 0
        self.launched = {}
        self.patterns = {}
        for node in ast.parse((ROOT / DRIVER).read_text()).body:
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in ('FAULT', 'DELETED'):
                        self.patterns[target.id] = re.compile(ast.literal_eval(node.value.args[0]), re.I)
        require(set(self.patterns) == {'FAULT', 'DELETED'}, 'authoritative fault patterns unavailable')
        self.boot = mock['boot_id'] if mock is not None else Path('/proc/sys/kernel/random/boot_id').read_text().strip()

    def run(self, command):
        self.log(('MOCK ' if self.mock is not None else '') + 'RUN ' + shlex.join(map(str, command)))
        if self.mock is not None:
            require(not self.mock.get('fail_command') or self.mock['fail_command'] not in ' '.join(map(str, command)),
                    'injected command failure')
            return
        with (HERE / 'orchestrate.log').open('a') as output:
            subprocess.run(command, cwd=self.root, check=True, stdout=output, stderr=subprocess.STDOUT)

    def faults(self):
        if self.mock is not None:
            counts = self.mock.get('fault_counts', [2])
            count = counts[min(self.tick, len(counts)-1)]
        else:
            require(Path('/proc/sys/kernel/random/boot_id').read_text().strip() == self.boot, 'boot changed')
            result = subprocess.run(['journalctl', '-k', '-b', '--no-pager'], capture_output=True,
                                    text=True, check=True, timeout=15)
            require(result.stdout.strip(), 'kernel journal empty/unavailable')
            count = sum(bool(self.patterns['FAULT'].search(line)) and not self.patterns['DELETED'].search(line)
                        for line in result.stdout.splitlines())
        require(count == 2, f'fault count changed: expected exactly 2, found {count}; no new launches')

    def state(self, unit):
        if self.mock is not None:
            if unit in self.launched:
                age = self.tick - self.launched[unit]
                limit = 7 if unit == 'packet64-chain' else 2
                return dict(LoadState='loaded', ActiveState='active' if age < limit else 'inactive',
                            Result='success', ExecMainStatus='0')
            seq = self.mock.get('lane_states', ['active', 'inactive'])
            return dict(LoadState='loaded', ActiveState=seq[min(self.tick, len(seq)-1)],
                        Result='success', ExecMainStatus='0')
        result = subprocess.run(['systemctl', '--user', 'show', unit, '--property=LoadState',
                                 '--property=ActiveState', '--property=Result', '--property=ExecMainStatus'],
                                capture_output=True, text=True, timeout=15)
        props = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
        require(props.get('LoadState') in ('loaded', 'not-found') and props.get('ActiveState'),
                f'cannot inspect unit {unit}: rc={result.returncode}')
        return props

    def pause(self):
        self.tick += 1
        if self.mock is None:
            time.sleep(10)

    def launch(self, unit, cores, args):
        require(unit not in self.launched, 'no repeat launches')
        if self.mock is None:
            require(self.state(unit)['LoadState'] == 'not-found', f'unit already exists: {unit}')
        command = ['systemd-run', '--user', '--unit=' + unit, '--property=Restart=no',
                   '--property=Nice=0', '--property=CPUAffinity=' + cores.replace(',', ' '),
                   '--property=KillMode=process', '--property=SendSIGKILL=no',
                   '--property=ExitType=cgroup', '--property=TimeoutStopSec=infinity',
                   '--property=StandardOutput=append:' + str(HERE / 'orchestrate.log'),
                   '--property=StandardError=append:' + str(HERE / 'orchestrate.log'),
                   '--working-directory=' + str(ROOT), '/usr/bin/taskset', '-c', cores,
                   '/usr/bin/bash', str(HERE / 'device-entry.sh'), *map(str, args)]
        self.faults()
        self.run(command)
        self.launched[unit] = self.tick


def terminal(state):
    require(state['ActiveState'] != 'failed', 'unit failed; no retry')
    return state['ActiveState'] == 'inactive'


def orchestrate(backend, log, wait_seconds=14400):
    started = time.monotonic()
    seen = set()
    while True:
        backend.faults()
        states = {lane: backend.state('v3-lane' + lane + '-d7') for lane in 'AB'}
        for lane, state in states.items():
            if state['ActiveState'] in ('active', 'activating', 'deactivating'):
                seen.add(lane)
        complete_files = all((backend.root / screen_path(lane, choice) / 'window.json').exists()
                             for lane in 'AB' for choice in CHOICES)
        if all(terminal(state) for state in states.values()) and (seen == set('AB') or complete_files):
            break
        require(time.monotonic() - started < wait_seconds, 'screen wait deadline exceeded')
        log('WAIT d7 ' + ' '.join(f'{lane}={state["ActiveState"]}' for lane, state in states.items()))
        backend.pause()
    log('D7 INACTIVE fault_count=2')
    # Individual screen services can outlive a lane driver; never overlap them.
    for lane in 'AB':
        for choice in CHOICES:
            unit = 'screen-v3-' + screen_path(lane, choice).name
            require(terminal(backend.state(unit)), 'screen unit still owns work: ' + unit)
    result = select(backend.root, backend.boot, log)
    if backend.mock is None:
        with (HERE / 'selection.json').open('x') as stream:
            json.dump(result, stream, indent=2)
            stream.write('\n')
    draft = 'production' if result['choice'] == CHOICES[0] else 'draft-hc'
    miss = 'batch' if result['choice'].endswith('-batch') else 'control'
    steps = [(['fast_reseal.py', '--placement', '1', '--draft', draft, '--miss', miss]),
             ['chain_seal.py', '--verify'], ['check_inputs.py', '--output-root', str(OUT)],
             ['storage_precheck.py'], ['plan_gate.py'], ['queue_runner.py', '--phase', 'all',
                                                       '--output-root', str(OUT), '--plan']]
    for script, *args in steps:
        backend.faults()
        backend.run(CPU + [str(PACKET / script), *args])
    review = backend.root / SCREEN / 'evidence/review-window-04.json'
    # Only the sealed lane-aware entry may join. No external lock emulation.
    companion_ok = all((backend.root / LANES / leaf).is_file()
                       for leaf in ('screen.py', 'window_adapter.py', 'lane_admission.py',
                                    'placement-validation/wrapper-seal.json'))
    companion_ok = companion_ok and review.is_file()
    if companion_ok:
        try:
            backend.run(CPU + [str(HERE / 'check_companion.py'), str(review)])
            for choice in ('1-split23-production-control', '1-production-control'):
                placement = '1-split23' if choice.startswith('1-split23-') else '1'
                backend.run(CPU + [str(LANES / 'screen.py'), '--profile', 'tp2', '--lane', 'B',
                                  '--placement', placement, '--lineage', str(PACKET / 'selections' / choice),
                                  '--seal', str(PACKET / 'selections' / choice / 'screen-seal.json'),
                                  '--output', str(LANES / 'evidence' / ('orchestration-' + choice + '-B-a')), '--plan'])
        except (subprocess.CalledProcessError, OSError, ValueError) as error:
            companion_ok = False
            log(f'COMPANION SKIP: CPU protocol/seal/review/plan preflight refused: {error}')
    else:
        log('COMPANION SKIP: sealed lane-aware wrapper or coordinator review missing; no external protocol bypass')
    backend.launch('packet64-chain', '0-3,16-19', ['chain'])
    jobs = ['1-split23-production-control', '1-production-control'] if companion_ok else []
    companion = None
    chain_done = False
    last_status = None
    while True:
        backend.faults()
        state = backend.state('packet64-chain')
        chain_done = terminal(state)
        if chain_done:
            require(state.get('Result', 'success') == 'success' and state.get('ExecMainStatus', '0') == '0',
                    'chain exited unsuccessfully')
            if backend.mock is None:
                require(read(OUT / 'queue-all-complete.json').get('passed') is True, 'chain completion receipt absent')
            if jobs:
                log('COMPANION SKIP remaining: chain already finished')
                jobs.clear()
        if companion and terminal(backend.state(companion[0])):
            if backend.mock is None:
                require(read(companion[1] / 'lane-coordination.json').get('passed') is True,
                        'companion lacks successful lease/drain receipt')
            log('COMPANION COMPLETE ' + companion[0])
            companion = None
        if not companion and jobs and not chain_done:
            choice = jobs.pop(0)
            output = backend.root / LANES / 'evidence' / ('orchestration-' + choice + '-B-a')
            require(not output.exists(), 'companion output already exists; no retry')
            unit = 'screen-packet64-orchestration-' + choice
            log('COMPANION protocol=sealed run_lane_b_screen; one lease; hold checked under protocol.lock; native drain before timing')
            backend.launch(unit, '4-7,20-23', ['companion', choice, review, output])
            companion = unit, output
        status = (chain_done, companion[0] if companion else None, tuple(jobs))
        if status != last_status:
            log(f'MONITOR chain_done={chain_done} companion={status[1]} pending={len(jobs)}')
            last_status = status
        if chain_done and not companion:
            log('COMPLETE chain and companions; no resident service requested')
            return result
        backend.pause()


def main():
    # Log is opened before argument parsing, so invalid arguments also get EXIT.
    with (HERE / 'orchestrate.log').open('a', buffering=1) as stream:
        def log(message):
            line = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()) + ' ' + message
            print(line, flush=True)
            stream.write(line + '\n')
        code = 1
        backend = None
        try:
            parser = argparse.ArgumentParser(description=__doc__)
            parser.add_argument('--dry-run', type=Path, metavar='MOCK_JSON', help='mock evidence root adjacent to JSON; no external calls')
            parser.add_argument('--wait-seconds', type=float, default=14400)
            args = parser.parse_args()
            require(math.isfinite(args.wait_seconds) and args.wait_seconds > 0, 'invalid wait bound')
            require(os.getpriority(os.PRIO_PROCESS, 0) == 19 and
                    set(os.sched_getaffinity(0)) <= set(range(8, 16)) | set(range(24, 32)), 'requires CPU helper nice/affinity')
            def cancel(number, frame):
                raise RuntimeError(f'signal {number}; no new launches; owned units keep their own supervision')
            for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
                signal.signal(sig, cancel)
            with (HERE / 'orchestration.lock').open('a') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                mock = read(args.dry_run) if args.dry_run else None
                root = args.dry_run.resolve().parent if args.dry_run else ROOT
                log('START mode=' + ('MOCK no GPU/systemd/subprocess' if mock is not None else 'coordinator-live'))
                backend = Backend(root, log, mock)
                orchestrate(backend, log, args.wait_seconds)
                code = 0
        except SystemExit as error:
            code = error.code if isinstance(error.code, int) else 2
        except BaseException as error:
            log(f'REFUSED {type(error).__name__}: {error}')
        finally:
            units = ','.join(backend.launched) if backend else 'none'
            log(f'EXIT rc={code} launched_units={units}; no kills, retries, marker cleanup or restart')
        return code


if __name__ == '__main__':
    raise SystemExit(main())
