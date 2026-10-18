"""Render a focused patch from a packet61-style reference; NEVER edit a packet.

The retained integration.patch is an example for the next unsealed candidate.
This script only reads three source files and prints a unified diff to stdout.
"""
import argparse
import ast
import difflib
from pathlib import Path


def once(source, old, new):
    if source.count(old) != 1:
        raise ValueError('integration point changed: ' + old[:100])
    return source.replace(old, new, 1)


def transform(name, source):
    if name == 'window.py':
        source = once(source, 'import pipeline as pp\n',
                      'import pipeline as pp\nfrom chain_devices import mask_native, private_home\n'
                      'from window_adapter import run_window, verify_receipt\n')
        nodes = ast.parse(source).body
        index = next(i for i, node in enumerate(nodes) if getattr(node, 'name', None) == 'foreign_engines')
        if getattr(nodes[index + 1], 'name', None) != 'Watch':
            raise ValueError('foreign admission integration boundary changed')
        start, end = source.index('def foreign_engines('), source.index('class Watch:')
        source = source[:start] + source[end:]
        source = once(source, 'def __init__(self,out,boot,seconds):',
                      'def __init__(self,out,boot,seconds,admission=None):\n        self.admission=admission')
        source = once(source, '        self.launched.append(int(pid))',
                      '        self.launched.append(int(pid))\n        if self.admission:self.admission.register(int(pid))')
        source = once(source, '    def check(self):\n        self.poll_kernel()',
                      '    def check(self):\n        self.poll_kernel()\n        if self.admission:self.admission.check()')
        source = once(source, '    diagnostic=bool(identity.get(\'diagnostic_unsealed\'))',
                      '    if not cpu_rehearsal:verify_receipt(row)\n    diagnostic=bool(identity.get(\'diagnostic_unsealed\'))')
        source = once(source, 'def main(*,cpu_rehearsal=False):',
                      'def main(*,cpu_rehearsal=False,admission=None):')
        source = once(source, '    a=p.parse_args();a.cpu_rehearsal=cpu_rehearsal',
                      '    a=p.parse_args();a.cpu_rehearsal=cpu_rehearsal\n'
                      "    require(cpu_rehearsal or admission is not None,'device entry requires lane admission')")
        line = "    environment=environment_gate();require(environment['native']['OMP_NUM_THREADS']=='2','OMP_NUM_THREADS=2')"
        source = once(source, line, line + "\n    if admission:environment['native']=mask_native(environment['native'])")
        source = once(source, "    record['foreign_engine_admission']=foreign_engines();out.mkdir(parents=True)",
                      "    if admission:admission.check()\n"
                      "    record['foreign_engine_admission']=admission.record['clients'] if admission else {'scope':'cpu-rehearsal'}\n"
                      "    record['timing_claim_eligible']=bool(admission and admission.scope=='whole-host')\n"
                      "    out.mkdir(parents=True)\n"
                      "    native_env=private_home(environment['native'],out/'driver-home') if admission else environment['native']\n"
                      "    record['execution_environment']=native_env")
        source = once(source, 'watch=Watch(out,boot,seconds);old=', 'watch=Watch(out,boot,seconds,admission);old=')
        for old in ("run_draft(a,out,environment['native'],", "run_fixtures(a,out,environment['native'],",
                    "concurrency_canary(args,out,environment['native'],"):
            source = once(source, old, old.replace("environment['native']", 'native_env'))
        # Two pp.run calls, suite and single request, share the same native env.
        old = "pp.run(args,environment['native'],"
        if source.count(old) != 2:
            raise ValueError('pipeline run call sites changed')
        source = source.replace(old, 'pp.run(args,native_env,')
        source = once(source, '            args.selection_sha256=',
                      '            args.lane_ready=admission.ready if admission else None\n            args.selection_sha256=')
        source = once(source, "if __name__=='__main__':raise SystemExit(main())", '''def coordinated_main():
    # Capture a fresh boundary before waiting for the current B screen.
    _,cursor=journal()
    def wait_check():
        nonlocal cursor
        text,cursor=journal(cursor)
        require(not FAULT.search(text),'fresh GPU fault during admission wait')
    return run_window(main,wait_check=wait_check)

if __name__=='__main__':raise SystemExit(coordinated_main())''')
    elif name == 'pipeline.py':
        source = once(source,
                      'rank_home=P/"build"/"driver-cache"/("rank"+str(rank));rank_home.mkdir(parents=True,exist_ok=True)',
                      'rank_home=out/"driver-cache"/("rank"+str(rank));rank_home.mkdir(parents=True,exist_ok=False)')
        source = once(source, '        for rank in range(2):self.receive(rank,args.seconds,ready=True)',
                      '        for rank in range(2):self.receive(rank,args.seconds,ready=True)\n'
                      '        if self.device and getattr(args,"lane_ready",None):args.lane_ready([p.pid for p in self.children])')
    elif name == 'queue_runner.py':
        source = once(source, 'def validate_success(name, out, rc):',
                      'def validate_success(name, out, rc):\n    from window_adapter import verify_receipt')
        source = once(source, "    row = json.loads((out / name / 'window.json').read_text())",
                      "    row = json.loads((out / name / 'window.json').read_text())\n    verify_receipt(row)")
    else:
        raise ValueError('unknown integration file')
    return source


def render(reference):
    return render_sources({name: (reference / name).read_text()
                           for name in ('window.py', 'pipeline.py', 'queue_runner.py')})


def render_sources(sources):
    parts = []
    for name in ('window.py', 'pipeline.py', 'queue_runner.py'):
        source = sources[name]
        changed = transform(name, source)
        compile(changed, name, 'exec')  # syntax only, imports/device paths never execute
        parts.extend(difflib.unified_diff(source.splitlines(True), changed.splitlines(True),
                                         fromfile='a/' + name, tofile='b/' + name))
    return ''.join(parts)


def transform_screen(name, source):
    if name == 'conditions.py':
        source = once(source, 'import fcntl\n',
                      'import fcntl\nfrom drain_gate import DEFAULT_DRAIN_ROOT, screen_teardown_admit\n')
        source = once(source, 'def __init__(self, output, root=HERE, now=time.monotonic, sleep=time.sleep):',
                      'def __init__(self, output, root=DEFAULT_DRAIN_ROOT, now=time.monotonic, sleep=time.sleep):')
        old = '''def teardown_admit():
    path = HERE / 'teardown-state.json'
    if path.exists():
        row = read(path)
        require(row.get('boot_id') != Path('/proc/sys/kernel/random/boot_id').read_text().strip()
                or row.get('drained') is True, 'incomplete teardown; coordinator recovery required')
'''
        source = once(source, old, '''def teardown_admit(lane):
    # Only the prelaunch check permits live A computation. Actual Teardown
    # still locks, waits 60 seconds and refuses an incomplete previous drain.
    screen_teardown_admit(lane)
''')
    elif name == 'screen.py':
        source = once(source, 'import fault_review\n',
                      'import fault_review\nfrom drain_gate import DEFAULT_DRAIN_ROOT\n'
                      'from window_adapter import run_lane_b_screen\n')
        source = once(source, 'def main(argv=None):', 'def screen_main(argv=None):')
        source = once(source, '    teardown_admit()', '    teardown_admit(args.lane)')
        source = once(source, "    require(not list(HERE.glob('fault-' + boot + '*.json'))",
                      "    require(not list(DEFAULT_DRAIN_ROOT.glob('fault-' + boot + '*.json'))\n"
                      "            and not list(HERE.glob('fault-' + boot + '*.json'))")
        source = once(source, "if __name__ == '__main__':", '''def main(argv=None):
    args = parser().parse_args(argv)
    if args.plan:
        return screen_main(argv)  # no locks, flags, journal or device activity
    require(args.lane == 'B' and args.pair_dir is None,
            'chain-coordinated wrapper is standalone lane B only')
    require(args.authorized_device_window, 'coordinator authorization required')
    _, cursor = S.journal()
    def wait_check():
        nonlocal cursor
        fresh, cursor = S.journal(cursor)
        require(not fault_review.fault_lines(fresh), 'fresh fault while waiting for chain hold')
        require(not (args.output.parent / 'STOP').exists(), 'STOP while waiting for chain hold')
    return run_lane_b_screen(lambda: screen_main(argv), args.output, wait_check=wait_check)


if __name__ == '__main__':''')
    else:
        raise ValueError('unknown screen integration file')
    return source


def render_screen_sources(sources):
    parts = []
    for name in ('conditions.py', 'screen.py'):
        source = sources[name]
        changed = transform_screen(name, source)
        compile(changed, name, 'exec')
        parts.extend(difflib.unified_diff(source.splitlines(True), changed.splitlines(True),
                                         fromfile='a/' + name, tofile='b/' + name))
    return ''.join(parts)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--screen', action='store_true', help='render the future lane-B wrapper integration')
    args = parser.parse_args()
    print(render_screen_sources({name: (args.reference / name).read_text()
                                 for name in ('conditions.py', 'screen.py')}) if args.screen
          else render(args.reference), end='')
