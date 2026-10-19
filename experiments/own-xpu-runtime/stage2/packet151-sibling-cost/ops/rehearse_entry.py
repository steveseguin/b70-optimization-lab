#!/usr/bin/env python3
"""CPU-only native entry rehearsal: python3 -B rehearse_entry.py PROPOSAL.

Reads JSONL proposals, reconstructs lanequeue.command (never executes it),
and tests each declared native ELF with ldd and its help/argument parser.
Default mode performs no packet import. --report imports the real entry and
executes its unchanged post-device report source on temporary synthetic receipts.
Packet58 queue runners use one-card WSCREEN or record-window report adapters.
No --plan, model read, queue mutation, service or device entry.

Default binary inventory comes from the packet's build-receipt.json artifacts
or artifacts_sha256. New proposals may declare plan.entry_rehearsal.binaries:
[{"path": "repo/relative/native", "sha256": "...", "args": ["--version"],
  "returncode": 0, "contains": "version"}]. Omit args for --help (including
an explicit unknown-option parser refusal). An empty inventory always fails.
Script coordinators require a packet-specific rehearsal; they fail here rather
than guessing their inner environment. This is only the loader/entry gate;
the packet's real arm/state-machine CPU rehearsal remains separately required.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'v5'))
import freeze_safe
sys.path.insert(1, str(Path(__file__).resolve().parents[3] / 'ops'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import entry_sandbox
import launch_env

OPS = Path(__file__).resolve().parents[3] / 'ops'
ROOT = OPS.parents[2]


def lanequeue():
    directory = OPS / 'lane-queue'
    sys.path.insert(0, str(directory))
    try:
        spec = importlib.util.spec_from_file_location('_entry_lanequeue', directory / 'lanequeue.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


def resolve(path):
    path = Path(path)
    return path if path.is_absolute() else ROOT / path


def inventory(job):
    declaration = job.get('plan', {}).get('entry_rehearsal', {})
    if not isinstance(declaration, dict):
        raise ValueError('invalid entry rehearsal declaration')
    explicit = declaration.get('binaries')
    if explicit is not None:
        if not isinstance(explicit, list) or not explicit:
            raise ValueError('empty or invalid native inventory')
        return explicit
    argv = job['argv']
    script = resolve(argv[2] if Path(argv[0]).name.startswith('python') else argv[0])
    packet = next((p for p in (script.parent, *script.parents)
                   if (p / 'build-receipt.json').is_file()), None)
    if packet is None:
        raise ValueError('declare plan.entry_rehearsal.binaries; no build receipt found')
    receipt = json.loads((packet / 'build-receipt.json').read_text())
    if not isinstance(receipt, dict):
        raise ValueError('invalid build receipt')
    artifacts = receipt.get('artifacts', receipt.get('artifacts_sha256', {}))
    if not isinstance(artifacts, dict):
        raise ValueError('invalid build artifact inventory')
    binaries = []
    for name, digest in artifacts.items():
        path = Path(name)
        if not path.is_absolute():
            path = ROOT / path if name.startswith('experiments/') else packet / path
        # No broad tree scans or model/payload reads. Native executables have
        # no extension in the packet build receipts; .o/.a/.bin are not entrypoints.
        if path.suffix or not ('build' in path.parts and any(
                part in path.parts for part in ('device', 'gnu-host', 'host'))):
            continue
        binaries.append(dict(path=str(path), sha256=digest))
    if not binaries:
        raise ValueError('no native binaries in build receipt; declare an explicit inventory')
    return binaries


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def unit_environment(job, queue, ldp):
    queue.validate(job, job.get('lane'))
    if 'script' in job:
        raise ValueError('script coordinator needs a packet-specific inner-environment rehearsal')
    command = queue.command(job, '/tmp/entry-review.json', '/tmp/entry-receipt.json', ldp)
    unit = '--unit=screen-' + job['name']
    if unit not in command:
        raise ValueError('lanequeue unit identity changed')
    index = command.index('/usr/bin/env')
    if command[index + 1] != '-i':
        raise ValueError('lanequeue environment is not closed')
    env = {}
    for arg in command[index + 2:]:
        if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*=', arg):
            break
        key, value = arg.split('=', 1)
        env[key] = value
    if env != queue.closed_env(ldp):
        raise ValueError('lanequeue environment construction changed')
    return env


def rehearse(job, queue, ldp, runner=entry_sandbox.run, *, report=False):
    name = job.get('name', '?')
    row = dict(job=name, unit='screen-' + name, passed=False, binaries=[],
               service_started=False, arm_sequence_tested=False)
    try:
        env = unit_environment(job, queue, ldp)
        if report:
            row['report'] = rehearse_report(job, env)
        row['shared_environment_matches'] = env == launch_env.environment()
        native_env = dict(env)
        # Some frozen wrappers replace LD_LIBRARY_PATH from this option. Test
        # that narrower environment as well; do not silently repair the packet.
        argv = job['argv']
        for i, arg in enumerate(argv):
            if arg == '--library-path':
                native_env['LD_LIBRARY_PATH'] = argv[i + 1]
            elif arg.startswith('--library-path='):
                native_env['LD_LIBRARY_PATH'] = arg.split('=', 1)[1]
        row['packet_library_override'] = native_env != env
        for spec in inventory(job):
            result = dict(passed=False)
            row['binaries'].append(result)
            try:
                result['phase'] = 'identity'
                path = resolve(spec['path']).resolve(strict=True)
                result['binary'] = str(path)
                if path.suffix or not os.access(path, os.X_OK):
                    raise ValueError('inventory entry is not a native executable')
                with path.open('rb') as stream:
                    if stream.read(4) != b'\x7fELF':
                        raise ValueError('inventory entry is not ELF')
                expected = spec.get('sha256')
                if not isinstance(expected, str) or not re.fullmatch('[a-f0-9]{64}', expected):
                    raise ValueError('native inventory requires a SHA256')
                if digest(path) != expected:
                    raise ValueError('native binary differs from recorded build')
                result['phase'] = 'ldd'
                result['unit_ldd'] = launch_env.check_binary(path, env, runner)
                result['native_ldd'] = (launch_env.check_binary(path, native_env, runner)
                                        if native_env != env else result['unit_ldd'])
                if not result['unit_ldd']['passed'] or not result['native_ldd']['passed']:
                    continue
                args = spec.get('args', ['--help'])
                if (not isinstance(args, list) or not args or
                        not all(isinstance(a, str) and '\x00' not in a for a in args)):
                    raise ValueError('invalid native entry probe arguments')
                result['phase'] = 'entry'
                cp = runner(launch_env.env_command([str(path), *args], native_env),
                            binary=path, cwd=ROOT)
                output = cp.stdout + cp.stderr
                if 'args' in spec:
                    match = spec.get('contains')
                    if not isinstance(match, str) or not match:
                        raise ValueError('explicit probe requires expected output text')
                    passed = cp.returncode == spec.get('returncode', 0) and match in output
                else:
                    # A named unknown --help option is itself the binary's own
                    # argument-parse path. A generic rc=1 is never a pass.
                    passed = ((cp.returncode == 0 and bool(re.search(r'usage|options|help', output, re.I)))
                              or (cp.returncode in (1, 2) and bool(re.search(
                                  r'(?:unknown|unrecognized|unexpected|invalid) (?:argument|option)[^\n]*--help',
                                  output, re.I))))
                result.update(passed=passed, entry_returncode=cp.returncode,
                              entry_kind='explicit' if 'args' in spec else 'help-or-parser',
                              entry_timed_out=cp.returncode == 124)
            except (OSError, ValueError, KeyError, TypeError, RuntimeError):
                result['error'] = 'native inventory, loader, or bounded entry check failed'
        row['passed'] = (bool(row['binaries']) and all(b['passed'] for b in row['binaries'])
                         and (not report or row['report']['passed']))
    except (OSError, ValueError, KeyError, IndexError, TypeError, RuntimeError):
        # Do not echo arbitrary exceptions, argv, environments or binary output:
        # proposal values can include coordinator secrets.
        row['error'] = 'invalid proposal/inventory, stale binary, or unavailable CPU sandbox'
    return row


# Report rehearsal deliberately has no packet imports in the parent process.
# Every kind starts a fresh interpreter with the job's script directory first.
def report_entry(job):
    argv = job.get('argv', [])
    if len(argv) < 3 or not Path(argv[0]).name.startswith('python') or argv[1] != '-B':
        raise ValueError('report rehearsal needs a Python -B entry')
    path = resolve(argv[2]).resolve(strict=True)
    if path.suffix != '.py':
        raise ValueError('report entry must be Python source')
    return path


def duplicate_modules(packet, paths):
    """Static filesystem check, including unimported modules on active paths."""
    def modules(directory):
        result = {p.stem: p for p in directory.glob('*.py') if p.name != '__init__.py'}
        result.update({p.parent.name: p for p in directory.glob('*/__init__.py')})
        return result
    top = modules(packet)
    rows = []
    for directory in sorted({Path(p).resolve() for p in paths if p}):
        if directory == packet or not directory.is_relative_to(packet):
            continue
        for name, path in sorted(modules(directory).items()):
            if name in top:
                rows.append(dict(module=name, top=str(top[name]), shadow=str(path)))
    return rows


def report_limits():
    import resource
    os.setpriority(os.PRIO_PROCESS, 0, 19)
    os.sched_setaffinity(0, entry_sandbox.CPU)
    resource.setrlimit(resource.RLIMIT_AS, (entry_sandbox.MEMORY, entry_sandbox.MEMORY))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1024**2, 1024**2))


def report_guard(scratch, source_root, metadata=()):
    """Deny execution, devices, model/data reads and writes outside scratch.

    Installed Python libraries, repository Python source and the small
    import-time kernel registry/launch environment are the only non-synthetic
    inputs. Audit failures are sticky even if packet code catches
    the exception. This is a trusted-source CPU harness, not a hostile-code VM.
    """
    violations = []
    def audit(event, args):
        denied = event in ('subprocess.Popen', 'os.system', 'os.posix_spawn',
                           'os.exec', 'os.fork', 'os.forkpty', 'os.kill', 'os.killpg',
                           'socket.connect', 'socket.bind', 'ctypes.dlopen')
        if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
            path = Path(os.fsdecode(args[0])).resolve()
            write = args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)
            allowed = path.is_relative_to(scratch)
            if not write:
                allowed |= path in metadata
                allowed |= path.is_relative_to(Path(sys.base_prefix)) and '/site-packages/' not in str(path)
                allowed |= (path.is_relative_to(source_root) or path.is_relative_to(ROOT)) and (path.suffix == '.py' or path.name in ('kernel-registry.json', 'launch-environment.json'))
            # Importlib may try bytecode before source even under -B.
            if not allowed and not write and path.suffix == '.pyc':
                raise PermissionError('bytecode excluded from source rehearsal')
            denied |= not allowed
        if event in ('os.mkdir', 'os.remove', 'os.rmdir', 'os.chmod', 'os.rename',
                     'os.link', 'os.symlink', 'os.truncate'):
            count = 2 if event in ('os.rename', 'os.link', 'os.symlink') else 1
            denied |= any(not isinstance(p, (str, bytes, os.PathLike)) or
                          not Path(os.fsdecode(p)).resolve().is_relative_to(scratch)
                          for p in args[:count])
        if denied:
            violations.append(event)
            raise PermissionError('report rehearsal attempted forbidden I/O')
    sys.addaudithook(audit)
    return violations


def oracle_import_prelude(driver):
    """Run the real oracle entry up to its first evidence read.

    The report needs its import/path side effects, not a live oracle seal.
    No report function or import is mocked. The read boundary is intercepted
    by tracing the driver/authority's read or digest helper before it opens data.
    A later import in this data-validation phase is outside this report gate.
    """
    class EvidenceBoundary(Exception):
        pass
    def trace(frame, event, arg):
        if event == 'call' and (frame.f_code.co_name in ('read', 'digest', 'sha') or
                (frame.f_code.co_name == 'read_text' and
                 getattr(frame.f_locals.get('self'), 'suffix', None) != '.py')):
            raise EvidenceBoundary()
        return trace
    sys.settrace(trace)
    try:
        driver.oracle_inputs()
    except EvidenceBoundary:
        pass
    finally:
        sys.settrace(None)


def synthetic_report(common, output, kind, lane):
    """Generate screen-v5 receipts from scratch; never clone device evidence."""
    def save(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))
    oracle = output / 'oracle'
    common.D.ORACLE = oracle  # Data location only; real token parser is retained.
    for prompt in common.D.CHECK.PROMPT_IDS:
        save(oracle / 'results' / prompt / 'result.json', dict(
            schema='iq3-runtime-cpu-oracle.v1', status='token-cap',
            arithmetic=common.ARITHMETIC, tokens=[1] * 128))
    lineage = output / 'lineage'
    save(lineage / 'selection.json', dict(choices=dict(class_layout_bank='synthetic')))
    for rank in (0, 1):
        save(output / 'run/ranks' / f'rank{rank}' / 'class-layout.json', dict(
            class_layout_bank='synthetic', bytes=1, budget=600 * 1024**2, weights=[1]))
    views, selections = [], []
    count = 64 if kind == 'smoke' else 128
    choices = ['candidate'] if kind == 'smoke' else ['control', 'candidate', 'control', 'candidate', 'control']
    for i, choice in enumerate(choices):
        dest = output / 'run/views' / f'{i:02d}-{choice}'
        selection = dict(choice=choice, selection_sha256='synthetic')
        boundary = dict(passed=True, total_reset=True, cached_tokens=0,
                        weight_uploads_after_load=0, selection_sha256='synthetic',
                        arena_descriptors_sha256='a', weight_descriptors_sha256='w')
        for rank in (0, 1):
            save(dest / 'boundary' / f'boundary-rank{rank}.json', boundary)
        incident = dict(passed=True, exact_oracle=True, cached_tokens=0, tokens=[1] * 64)
        receipt = dest / 'incident64/receipt.json'
        save(receipt, incident)
        incident['receipt_sha256'] = digest(receipt)
        requests = [dict(prompt_id=p, prompt_class=common.METRICS.PROMPT_CLASSES[p],
                         passed=True, exact_oracle=True, cached_tokens=0, tokens=[1] * count,
                         token_timestamps=[1 + j * .02 for j in range(count)],
                         tok_s_1_100_intervals_after_ttft=50., hits=1, guesses=2,
                         acceptance=.5, output_tokens=count, requested_max_new=count)
                    for p in common.D.CHECK.PROMPT_IDS]
        for prompt in ['incident64', *common.D.CHECK.PROMPT_IDS]:
            save(dest / prompt / 'rank1/draft-rows.jsonl', dict(
                draft_position=1, confirmed_token=1, guess=1, head='synthetic'))
            for rank in (0, 1):
                folder = dest / prompt / f'rank{rank}'
                folder.mkdir(parents=True, exist_ok=True)
                (folder / 'p105-transfers.jsonl').write_text('')
                (folder / 'timings.jsonl').write_text('')
        # Packet151 requires nonempty, internally consistent half/sibling streams.
        for request in requests:
            request['guess_rows'] = [dict(position=1, guess=1, actual=1, hit=True)]
            folder = dest / request['prompt_id'] / 'rank0'
            timing = dict(position=1, fixture=2, speculative=True, corrected=False,
                          cancelled=False, p151_device_ms=10., half_completion_ms=10.,
                          p151_sibling=choice == 'candidate', p151_sibling_prepare_ms=0.)
            save(folder / 'timings.jsonl', timing)
            if choice == 'candidate':
                save(folder / 'sibling-rows.jsonl', dict(position=1, fixture=2,
                     paired_half_device_ms=10., cancelled=False, discarded=True))
        views.append(dict(index=i, choice=choice, selection_sha256='synthetic', output=str(dest),
                          passed=True, started_utc_ns=100+i*10, finished_utc_ns=105+i*10,
                          boundary=[boundary, boundary], incident64=incident, requests=requests))
        selections.append(selection)
    isolation = dict(passed=True, synthetic_cpu_fixture=True)
    save(output / 'run/device-isolation.json', isolation)
    save(output / 'run/bracket-inputs.json', dict(passed=True, kind=kind, views=views))
    save(output / 'run/report-inputs.json', dict(passed=True, device_isolation=isolation,
         lane=lane, requests=requests, incident64=incident, placement={}))
    return dict(lineage=str(lineage), profile='tp2', lane=lane, timing='token', placement={},
                conditions={}, bracket=dict(kind=kind, views=selections))


def report_statements(screen):
    """Select the unchanged post-device source block, never guess a module name.

    Supports factored report_completed and the older inline screen_main tail.
    Unknown layouts refuse; adding a new schema requires fixtures and tests here.
    """
    import ast
    tree = ast.parse(Path(screen.__file__).read_text())
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'screen_main')
    for node in ast.walk(function):
        for field, statements in ast.iter_fields(node):
            if not isinstance(statements, list):
                continue
            for i, statement in enumerate(statements):
                if not isinstance(statement, ast.stmt):
                    continue
                source = ast.unparse(statement)
                if (source.startswith('report_completed(') or
                        (source.startswith('proof = read(') and 'run/report-inputs.json' in source)):
                    end = i + 1
                    while end < len(statements) and not ast.unparse(statements[end]).startswith('record.update('):
                        end += 1
                    if end == len(statements):
                        raise ValueError('unknown report tail boundary')
                    return compile(ast.Module(body=statements[i:end], type_ignores=[]), screen.__file__, 'exec')
    raise ValueError('unsupported report entry layout')


def source_block(path, start, end):
    """Compile an unchanged, bounded report tail from a known main layout."""
    import ast
    tree = ast.parse(Path(path).read_text())
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
    for node in ast.walk(main):
        for _, statements in ast.iter_fields(node):
            if not isinstance(statements, list):
                continue
            for i, statement in enumerate(statements):
                if isinstance(statement, ast.stmt) and ast.unparse(statement).startswith(start):
                    for j in range(i + 1, len(statements)):
                        if ast.unparse(statements[j]).startswith(end):
                            return compile(ast.Module(body=statements[i:j], type_ignores=[]), str(path), 'exec')
    raise ValueError('unsupported one-card report boundary')


def parse_entry(main, argv):
    """Execute the entry's real main/parser, stopping before admission or I/O."""
    class Parsed(Exception):
        pass
    result = []
    def trace(frame, event, arg):
        if frame.f_code is main.__code__ and event == 'line' and 'args' in frame.f_locals:
            result.append(frame.f_locals['args'])
            raise Parsed()
        return trace
    sys.settrace(trace)
    try:
        main(argv)
    except Parsed:
        pass
    finally:
        sys.settrace(None)
    if len(result) != 1:
        raise ValueError('entry parser boundary missing')
    return result[0]


def synthetic_onecard(driver, views, output, kind, candidate, maintenance):
    """Small invented token/timing receipts, consumed by unchanged packet code."""
    def save(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))
    driver['ORACLE'] = output / 'oracle'
    driver['ROOT'] = output
    views.P = output / 'selection-source'  # Data paths only; selection/digest stay real.
    selection = dict(schema='packet49d.selection.v1', decision=None, choices=dict(
        route='route-exp32-rank4', recurrence='rows4-shared', hc='production', down='down-tile16'))
    for view in ('tile16', *views.VIEWS):
        save(views.P / 'selections' / (view + '.json'), selection)
    save(driver['ORACLE'] / 'results/completion.json', dict(synthetic_cpu_fixture=True))
    prompts = []
    for prompt in driver['CHECK'].PROMPT_IDS:
        prompts.append(dict(prompt_id=prompt, prompt_tokens=4, input_bundle='inputs/' + prompt))
        save(output / 'inputs' / prompt / 'input.json', dict(tokens=[2, 3, 4, 5]))
        save(driver['ORACLE'] / 'results' / prompt / 'result.json', dict(
            schema='iq3-runtime-cpu-oracle.v1', status='token-cap',
            arithmetic=driver['ARITHMETIC'], tokens=[1] * 128))
    screen = kind in ('smoke', 'bracket')
    rows = views.bracket(candidate) if screen else [(None, candidate)]
    cap = 64 if kind == 'smoke' else 128
    native = dict(passed=True, safe_to_exit=True, device_executed=True, owner_cards=1,
                  cpu_affinity=[0, 1, 2, 3, 16, 17, 18, 19], observed_nice=0, native_nice=0,
                  selection_sha256=views.digest(candidate), teardown=[dict(
                      safe_to_exit=True, idle_marker_complete=True, exit_code=0, live_bytes=0, in_flight=0)])
    save(output / 'run/receipt.json', native)
    save(output / 'receipt.json', dict(passed=True, safe_to_exit=True,
                                     window='WSCREEN' if screen else kind))
    for label, view in rows:
        dest = output / 'run' if label is None else output / 'run' / label
        # Deliberately slow A0: amended packets must exclude it only from speed,
        # while the older 58v policy correctly returns a negative decision.
        rate = 10 if label == 'A0' else 60 if label in ('B0', 'B1') else 50
        save(dest / 'boundary.json', dict(passed=True, selection_sha256=views.digest(view),
            cache_maintenance=maintenance or view, cache_cap=view if view in ('18GB', 'max') else 'max',
            hc=view, cache_allocation_bytes=getattr(views, 'MAX_BYTES', 18_000_000_000),
            cache_started_empty=True, allocation_ids_preserved=True, weight_uploads_during_switch=0,
            model_loads=1, context_extent=32, arena_descriptors_sha256='a', weight_descriptors_sha256='w'))
        for prompt in prompts:
            request = dest / prompt['prompt_id']
            save(request / 'reset.json', dict(passed=True, cached_tokens=0, allocation_ids_preserved=True))
            save(request / 'result.json', dict(passed=True, arithmetic=driver['ARITHMETIC'],
                tokens=[1] * cap, cached_tokens=0, gpu_count=1, decode_mode='plain', context=4096,
                requested_max_new=cap, prompt_tokens=4, request_start_monotonic=0.,
                request_end_monotonic=1 + cap / rate,
                timing_rows=[dict(completed_monotonic=1 + i / rate) for i in range(cap)]))
    return dict(prompts=prompts)


def onecard_report_probe(job, kind, scratch, source_root):
    import importlib
    import runpy
    from types import SimpleNamespace
    path = report_entry(job)
    packet = path.parent
    # These two small declarative files are read at import by this lineage.
    # No evidence, seal, model input or device file is admitted.
    metadata = {(packet / name).resolve() for name in ('views.json', 'admission.json')}
    violations = report_guard(scratch, source_root, metadata)
    sys.path[0] = str(packet)
    sys.argv = [str(path), *job['argv'][3:]]
    for name in ('launch_env', 'entry_sandbox'):
        sys.modules.pop(name, None)
    entry = runpy.run_path(str(path), run_name='_onecard_entry')
    args = parse_entry(entry['main'], job['argv'][3:])
    window = entry['W']
    screen = 'WSCREEN' in entry['ORDER']
    if screen != (kind in ('smoke', 'bracket')) or job.get('lane', 'A') != 'A':
        raise ValueError('one-card report layout or lane differs')
    views = importlib.import_module('views')
    if screen:
        candidates = [v for a, v in entry['STAGES'] if a != 'smoke']
        if len(candidates) != 1:
            raise ValueError('ambiguous one-card candidate')
        candidate = 'smoke' if kind == 'smoke' else candidates[0]
    else:
        if kind not in entry['ORDER'] or kind not in ('WS128x', 'WS128'):
            raise ValueError('unsupported record window')
        candidate = args.view
    maintenance = getattr(args, 'cache_maintenance', None)
    window_name = 'WSCREEN' if screen else kind
    window_output = scratch / window_name
    driver_output = window_output / 'run'
    # Resolve the actual child route from window.py, without executing a command.
    window_args = SimpleNamespace(window=window_name, view=candidate, card=0,
                                  cache_maintenance=maintenance)
    command = window.native_command(window_args, window_output, 'zero-copy')
    driver_path = Path(command[2]).resolve()
    if command[:2] != ['/usr/bin/python3', '-B'] or driver_path != packet / 'suite_driver.py':
        raise ValueError('unsupported one-card driver route')
    driver = runpy.run_path(str(driver_path), run_name='_onecard_driver')
    # runpy's returned globals are a copy; functions retain the executing dict.
    driver = driver['main'].__globals__
    oracle_import_prelude(SimpleNamespace(oracle_inputs=driver['oracle_inputs']))
    manifest = synthetic_onecard(driver, views, driver_output, kind, candidate, maintenance)
    driver_args = SimpleNamespace(output=driver_output, view=candidate, window=window_name,
                                  cache_maintenance=maintenance)
    namespace = dict(driver, args=driver_args, manifest=manifest, row={})
    exec(source_block(driver_path, 'summary = summarize', 'row.update('), namespace)
    summary = json.loads((driver_output / 'summary.json').read_text())
    if summary.get('passed') is not True or summary.get('request_count') != (60 if kind == 'bracket' else 12):
        raise ValueError('incomplete one-card report')
    # Run the window's unchanged publication tail after its memory/teardown
    # gates. Device admission and postload observations are outside this gate.
    namespace = dict(window.__dict__, output=window_output,
                     args=window_args, admission=SimpleNamespace(scope='whole-host'),
                     record=dict(native_files={}))
    exec(source_block(window.__file__, 'receipt = json.loads(', "record['postload_memory']"), namespace)
    exec(source_block(window.__file__, "summary['timing_claim_eligible']", 'for leaf in'), namespace)
    published = json.loads((window_output / 'summary.json').read_text())
    if published != namespace['summary'] or namespace['record']['native_files']['summary.json'] != digest(window_output / 'summary.json'):
        raise ValueError('window summary closure differs')
    decision = None
    if screen:
        state = {}
        namespace = dict(entry, output=scratch, state=state, save=lambda: None)
        exec(source_block(path, 'decision = json.loads(', 'return 0'), namespace)
        decision = state['qualifies_for_fresh_screen']
        if decision != summary['candidate_beats_all_controls']:
            raise ValueError('queue summary decision differs')
    collisions = duplicate_modules(packet, sys.path)
    return dict(passed=not collisions and not violations, kind=kind, collisions=collisions,
                report_completed=True, synthetic_evidence=True, import_paths=list(sys.path),
                device_executed=False, real_entry_main=True, report_lineage='packet58-onecard',
                admission_executed=False, entry_execution='parser-only',
                window=window_name, request_count=summary['request_count'],
                candidate_beats_all_controls=decision, warmup_view=summary.get('warmup_view'),
                comparison_controls=summary.get('comparison_controls'))


def report_kinds(job):
    """Record chains have window reports, not fictitious smoke/bracket stages."""
    import ast
    path = report_entry(job)
    if path.name == 'queue_runner.py':
        for node in ast.parse(path.read_text()).body:
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'ORDER' for t in node.targets):
                order = ast.literal_eval(node.value)
                if 'WSCREEN' not in order and {'WS128x', 'WS128'} <= set(order):
                    return ('WS128x', 'WS128')
    return ('smoke', 'bracket')


def report_probe(job, kind, scratch, source_root):
    import ast
    import importlib
    import runpy
    from unittest.mock import patch
    path = report_entry(job)
    tree = ast.parse(path.read_text())
    if path.name == 'queue_runner.py' and any(
            isinstance(n, ast.Import) and any(a.name == 'window' and a.asname == 'W' for a in n.names)
            for n in tree.body):
        return onecard_report_probe(job, kind, scratch, source_root)
    if not any(isinstance(n, ast.Call) and ast.unparse(n.func) == 'screen.main' for n in ast.walk(tree)):
        raise ValueError('unsupported entry: no screen.main route')
    packet = next((p for p in path.parents if p.name.startswith('packet')), path.parent)
    violations = report_guard(scratch, source_root)
    sys.path[0] = str(path.parent)
    # The harness's helpers must not shadow the packet's real modules.
    for name in ('launch_env', 'entry_sandbox'):
        sys.modules.pop(name, None)
    argv = [str(path), *job['argv'][3:]]
    for flag, value in [('--kind', kind), ('--output', str(scratch)),
                        ('--fault-review', str(scratch / 'unused-review.json'))]:
        if flag in argv:
            argv[argv.index(flag) + 1] = value
        else:
            argv.extend([flag, value])
    if '--authorized-device-window' not in argv:
        argv.append('--authorized-device-window')
    sys.argv = argv
    # Import the actual entry and its preflight dependencies, in entry order.
    # Only admission checks are replaced; imports and reporting stay real.
    entry_globals = runpy.run_path(str(path), run_name='_report_entry')
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
    imports = [n for n in main.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    exec(compile(ast.Module(body=imports, type_ignores=[]), str(path), 'exec'), entry_globals)
    common = importlib.import_module('common')
    screen = importlib.import_module('screen')
    seal = importlib.import_module('cpu_seal')
    readiness = importlib.import_module('readiness')
    rows = []
    def finish(argv):
        # Exercise the screen's real parser as well as the outer entry parser.
        args = screen.parser().parse_args(argv)
        if args.output != scratch or args.lane != job.get('lane', 'B'):
            raise ValueError('entry routed unexpected report arguments')
        oracle_import_prelude(common.D)
        paths = list(sys.path)
        collisions = duplicate_modules(packet, [str(packet), str(path.parent), *paths])
        identity = synthetic_report(common, scratch, kind, args.lane)
        record = dict(started_utc_ns=1, boot_id='synthetic-cpu-only')
        namespace = dict(screen.__dict__, args=args, identity=identity,
                         record=record, coordination={})
        try:
            exec(report_statements(screen), namespace)
        except Exception as error:
            import traceback
            locations = [dict(file=Path(f.filename).name, line=f.lineno)
                         for f in traceback.extract_tb(error.__traceback__)]
            rows.append(dict(passed=False, kind=kind, collisions=collisions,
                             locations=locations, error_type=type(error).__name__,
                             error='report code failed'))
            return 1
        result = json.loads((scratch / 'bracket-summary.json').read_text())
        if result.get('passed') is not True or result.get('kind') != kind:
            raise ValueError('report did not complete requested kind')
        collisions = duplicate_modules(packet, [str(packet), str(path.parent), *sys.path])
        rows.append(dict(passed=not collisions and not violations, kind=kind,
                         collisions=collisions, report_completed=True, synthetic_evidence=True,
                         import_paths=paths, device_executed=False, real_entry_main=True))
        return 0
    # Bracket admission reads a previous device smoke. Replace only that
    # prerequisite reader, never finish/report/summary or its imported symbols.
    # Names come from the actual entry's `from ... import load`, not a guessed
    # generic compare module which could mask the very collision under test.
    from contextlib import ExitStack
    with ExitStack() as stack:
        stack.enter_context(patch.object(seal, 'verify', return_value=None))
        stack.enter_context(patch.object(readiness, 'verify_ready', return_value=None))
        stack.enter_context(patch.object(screen, 'main', side_effect=finish))
        if kind == 'bracket':
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and any(a.name == 'load' for a in node.names):
                    module = importlib.import_module(node.module)
                    stack.enter_context(patch.object(module, 'load', return_value=dict(
                        kind='smoke', passed=True, request_count=12, max_new=64)))
        try:
            runpy.run_path(str(path), run_name='__main__')
        except SystemExit as error:
            if error.code not in (None, 0, 1) or not rows:
                raise ValueError('entry refused report routing') from None
    if len(rows) != 1:
        raise ValueError('entry must route exactly one report')
    return rows[0]


def rehearse_report(job, env, source_root=ROOT):
    import subprocess
    import tempfile
    rows = []
    with tempfile.TemporaryDirectory(prefix='entry-report-') as directory:
        root = Path(directory)
        request = root / 'job.json'
        request.write_text(json.dumps(job))
        try:
            kinds = report_kinds(job)
        except (OSError, ValueError, SyntaxError):
            kinds = ('smoke', 'bracket')  # Child reports the sanitized entry error.
        for kind in kinds:
            scratch = root / kind
            scratch.mkdir()
            result_path = scratch / 'rehearsal-result.json'
            # No packet stdout/stderr is returned: exceptions may contain secrets.
            with tempfile.TemporaryFile() as out:
                try:
                    cp = freeze_safe.run([sys.executable, '-B', str(Path(__file__).resolve()),
                        '--report-probe', str(request), kind, str(scratch), str(source_root)],
                        env=env, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=out, stderr=out,
                        timeout=45, preexec_fn=report_limits)
                    row = json.loads(result_path.read_text()) if result_path.exists() else dict(
                        passed=False, kind=kind, error='report child failed before receipt')
                    row['passed'] &= cp.returncode == 0
                except (OSError, ValueError, subprocess.SubprocessError):
                    row = dict(passed=False, kind=kind, error='bounded report rehearsal failed')
                rows.append(row)
    return dict(passed=all(r['passed'] for r in rows), kinds=rows,
                synthetic_evidence=True, device_executed=False)


def report_child():
    request, kind, directory, source_root = sys.argv[2:]
    scratch = Path(directory).resolve()
    job = json.loads(Path(request).read_text())
    try:
        result = report_probe(job, kind, scratch, Path(source_root).resolve())
    except Exception as error:
        # Only a type, never exception text, packet output or proposal values.
        import traceback
        result = dict(passed=False, kind=kind, error_type=type(error).__name__,
                      locations=[dict(file=Path(f.filename).name, line=f.lineno)
                                 for f in traceback.extract_tb(error.__traceback__)],
                      error='entry import, report schema, or CPU isolation failed')
    (scratch / 'rehearsal-result.json').write_text(json.dumps(result))
    return 0 if result['passed'] else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('proposal', type=Path)
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--report', action='store_true', help='also rehearse screen or one-card window reports on synthetic evidence')
    args = ap.parse_args()
    queue = lanequeue()
    # Read only the one non-secret P49_LDP assignment; never source/print file.
    ldp = queue.library_path()
    rows = []
    for line in args.proposal.read_text().splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        try:
            job = json.loads(line)
            if not isinstance(job, dict) or not isinstance(job.get('name'), str) or not re.fullmatch(
                    r'[A-Za-z0-9][A-Za-z0-9_.-]{0,100}', job['name']):
                raise ValueError('invalid job')
            row = rehearse(job, queue, ldp, report=args.report)
        except (ValueError, TypeError):
            row = dict(job='invalid-job', passed=False, error='invalid JSONL job')
        rows.append(row)
        if not args.json:
            print(f'{"PASS" if row["passed"] else "FAIL"} screen-{row["job"]}: '
                  f'{sum(b["passed"] for b in row.get("binaries", []))}/'
                  f'{len(row.get("binaries", []))} native entries; '
                  f'report={row.get("report", {}).get("passed", "not requested")}; '
                  'CPU arm sequence still required')
    if args.json:
        print(json.dumps(dict(passed=bool(rows) and all(r['passed'] for r in rows), jobs=rows), indent=2))
    return 0 if rows and all(r['passed'] for r in rows) else 1


if __name__ == '__main__':
    raise SystemExit(report_child() if sys.argv[1:2] == ['--report-probe'] else main())
