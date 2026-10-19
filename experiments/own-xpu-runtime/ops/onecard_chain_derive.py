#!/usr/bin/env python3
"""Derive a sealed one-card record-chain packet + orchestration from a winning v5 bracket.

CPU only: no GPU, services, queue mutation or model reads. Usage (repo root):

  python3 -B experiments/own-xpu-runtime/ops/onecard_chain_derive.py \
    --parent-orch experiments/own-xpu-runtime/ops/packet58aj-orchestration \
    --packet experiments/own-xpu-runtime/stage2/<new-chain-packet> \
    --out experiments/own-xpu-runtime/ops/<new>-orchestration \
    --unit packet58-onecard-<tag>-a --output evidence/card0-<tag>-a \
    --flag wait-policy=spin [--flag key=value ...] \
    --binary <device own-rt-iq3> --host-binary <gnu-host own-rt-iq3 of the same source> \
    --bracket-summary <v5 .../WSCREEN/summary.json> \
    --threshold-file scripts/packet58_onecard_record_threshold.json

Order: bracket gate -> --help gate (device binary in the Landlock entry sandbox,
host binary plain) -> copy the parent chain harness into the NEW packet with
identity rewrites, the new binaries and the flags appended to every model
window argv -> real-parser gate (--p58r-parse-test) for every model window ->
seal -> verify_ready -> temporary lanequeue plan -> READY written last.
Any refusal removes the directories this run created and writes no READY.
"""
import argparse, datetime, hashlib, json, os, resource, shlex, shutil, subprocess, sys, tempfile
from pathlib import Path
from types import SimpleNamespace

OPS = Path(__file__).resolve().parent
MODEL_WINDOWS = ('KD', 'W2m', 'WS', 'WS128x', 'WS128')
SKIP_TOP = {'READY-FOR-DEVICE.json', 'ready.json', 'build-receipt.json', 'submission-pins.json',
            'seal.py', 'verify_ready.py', 'queue.lock', 'WINDOW.md'}
COPY_DIRS = ('selections', 'frozen-inputs', 'host-admission', 'native')
TEXT = ('.py', '.json', '.md', '.snapshot', '.txt', '.tsv', '.jsonl')
INVALID = '__onecard_chain_derive_invalid__'
MARK = '# >>> onecard_chain_derive generated chain flags'


class Refused(Exception):
    pass


def refuse(ok, why):
    if not ok:
        raise Refused(why)


def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def read(p):
    return json.loads(Path(p).read_text())


def put(p, text):
    """Replace, never write through: a symlinked destination is replaced, not followed."""
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name('.' + p.name + '.tmp'); tmp.write_text(text); os.replace(tmp, p)


def save(p, v):
    put(p, json.dumps(v, indent=2) + '\n')


def record(path, root):
    return dict(name=Path(path).name, parent_relpath=str(Path(path).relative_to(root)), parent_digest=sha(path))


def parse_flags(items):
    flags = {}
    for item in items:
        key, sep, value = item.partition('=')
        refuse(sep == '=' and key and value and not key.startswith('-') and ' ' not in item,
               f'--flag must be key=value without leading dashes: {item!r}')
        refuse('--' + key not in flags, f'duplicate flag {key}')
        flags['--' + key] = value
    refuse(bool(flags), 'at least one --flag key=value is required')
    return flags


# 1. Bracket gate -------------------------------------------------------------
def bracket_gate(path):
    s = read(path)
    views = s.get('views') or []
    requests = [r for v in views for r in v.get('requests', [])]
    drift_max = s.get('maximum_control_drift_fraction', 0.03)
    refuse(s.get('passed') is True and s.get('device_executed') is True, 'bracket summary did not pass')
    refuse(s.get('candidate_beats_all_controls') is True, 'bracket refused: candidate_beats_all_controls is not true')
    refuse(s.get('control_drift_passed') is True and s.get('control_drift_fraction') is not None
           and s['control_drift_fraction'] <= drift_max <= 0.03, 'bracket refused: control drift not ok')
    refuse(len(views) == 5 and requests and len(requests) == s.get('request_count')
           and all(v.get('passed') is True for v in views)
           and all(r.get('exact_oracle') is True and r.get('passed') is True for r in requests),
           'bracket refused: not every request is exact')
    window = read(Path(path).parent / 'window.json')
    refuse(window.get('passed') is True and window.get('returncode') == 0 and not window.get('stop_reasons')
           and window.get('boot_id'), 'bracket window receipt incomplete')
    return dict(rates=s['rates'], control_drift_fraction=s['control_drift_fraction'],
                minimum_gain=s['minimum_gain_vs_best_control'], exact_requests=len(requests),
                request_count=s['request_count'], boot_id=window['boot_id'],
                readiness_policy=s.get('readiness_policy'))


# 2. --help gate --------------------------------------------------------------
def bracket_only_hits(key, bracket_packet):
    """Where a candidate dimension is reachable only through the bracket table."""
    hits = []
    for rel in ('native/bracket_table.hpp', 'views.py', 'runtime-selection.json'):
        f = bracket_packet / rel
        if f.is_file():
            t = f.read_text(errors='replace')
            if key.replace('-', '_') in t or key in t:
                hits.append(rel)
    return hits


def help_gate(flags, binary, host_binary, bracket_packet):
    sys.path.insert(0, str(OPS))
    import entry_sandbox, launch_env
    entry_sandbox.MEMORY = 2_000_000_000
    cp = entry_sandbox.run(launch_env.env_command([str(binary), '--help']), binary=binary)
    # A binary without --help cannot prove any flag: treat as "not listed" (refused below).
    device_help = cp.stdout if cp.returncode == 0 else ''
    hp = subprocess.run([str(host_binary), '--help'], stdin=subprocess.DEVNULL, capture_output=True,
                        text=True, env=dict(PATH='/usr/bin:/bin', OMP_NUM_THREADS='2'), timeout=60)
    host_help = hp.stdout if hp.returncode == 0 else ''
    rows = []
    for flag in flags:
        listed = dict(device=flag in device_help.split(), host=flag in host_help.split())
        if not all(listed.values()):
            key = flag[2:]; hits = bracket_only_hits(key, bracket_packet)
            where = ' and '.join(k for k, v in listed.items() if not v)
            if hits:
                raise Refused(f'REFUSED {flag}: the candidate dimension {key!r} is selectable only through the '
                              f'bracket table ({", ".join(hits)} in {bracket_packet.name}), not as a process-wide '
                              f'CLI flag; the {where} binary --help lacks {flag}. Chain windows (KD/W2m/WS/WS128x/WS128) '
                              f'cannot use a bracket table (the packet58asc failure). Rebuild with a native CLI '
                              f'option (packet58asd pattern) and derive again.')
            raise Refused(f'REFUSED {flag}: the {where} binary --help does not list it; never assume a flag exists.')
        rows.append(dict(flag=flag, listed_device_help=True, listed_host_help=True))
    return rows, dict(device=device_help, host=host_help)


# 3. Packet derivation --------------------------------------------------------
def rewrite(text, pairs):
    for a, b in pairs:
        text = text.replace(a, b)
    return text


def inject(P, flags):
    sd = (P / 'suite_driver.py').read_text(); co = (P / 'composition.py').read_text()
    refuse(MARK not in sd and MARK not in co, 'parent already carries generated flags; derive from its own parent')
    refuse('def native_command(' in sd and 'FLAGS = {' in co and 'ARGV = ' in co,
           'parent harness lacks suite_driver.native_command / composition.FLAGS; cannot add flags')
    for flag in flags:
        refuse(f"'{flag}'" not in sd and f"'{flag}'" not in co,
               f'{flag} already appears in the parent window argv; change it at its source instead')
    lit = repr(list(flags.items()))
    put(P / 'suite_driver.py', sd.rstrip('\n') + f'''

{MARK}
GENERATED_CHAIN_FLAGS = {lit}
_parent_native_command = native_command
def native_command(args, manifest, table):
    command = _parent_native_command(args, manifest, table)
    for flag, value in GENERATED_CHAIN_FLAGS:
        require(flag not in command, 'generated chain flag duplicated: '+flag)
        command += [flag, value]
    return command
''')
    put(P / 'composition.py', co.rstrip('\n') + f'''

{MARK}
FLAGS.update({lit})
ARGV[:] = [item for pair in FLAGS.items() for item in pair]
''')


# Current lanequeue refuses a non-JSON coordinator plan that mentions whole-host
# admission. packet58asc (79abe970b) replaced packet58aj's text plan with this
# exact JSON line; apply the same replacement only on an exact match.
PLAN_TEXT = """        for name in ORDER:
            budget = W.M.window_plan(name)
            print('# '+name+': '+W.A.window_scope(name)+', MemAvailable >= '+str(budget['host_required_available_bytes'])
                  +' bytes; 8 GiB live reserve; gap '+str(GAP_SECONDS)+' s')
        for name, cmd in cmds.items():
            print(name+': '+shlex.join(cmd))
"""
PLAN_JSON = """        print(json.dumps(dict(passed=True, device_executed=False, commands=cmds, windows=list(ORDER), gap_seconds=GAP_SECONDS, scope='whole-host', host_required_available_bytes=W.M.window_plan('WS128')['host_required_available_bytes'])))
"""


def plan_json(P):
    q = P / 'queue_runner.py'; t = q.read_text()
    if PLAN_TEXT in t:
        refuse(t.count(PLAN_TEXT) == 1 and '\nimport json\n' in t, 'queue_runner plan block ambiguous or json not imported')
        put(q, t.replace(PLAN_TEXT, PLAN_JSON)); return 'packet58asc JSON plan line applied'
    return 'parent plan unchanged'


def derive_packet(a, P0, P, flags, root, pairs):
    P.mkdir(parents=True)
    copied = []
    for f in sorted(P0.iterdir()):
        if f.is_file() and f.name not in SKIP_TOP:
            if f.suffix in TEXT:
                put(P / f.name, rewrite(f.read_text(), pairs))
            else:
                shutil.copy2(f, P / f.name)
            copied.append(record(f, root))
    for d in COPY_DIRS:
        if (P0 / d).is_dir():
            shutil.copytree(P0 / d, P / d, ignore=shutil.ignore_patterns('__pycache__'))
    # Inherited CPU gate receipts are copied byte for byte (parent evidence, not rewritten).
    (P / 'evidence').mkdir()
    gates = read(P0 / 'build-receipt.json')['gates']
    for name in gates:
        dst = P / name; dst.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(P0 / name, dst)
    for rel, src in (('build/device/own-rt-iq3', a.binary), ('build/gnu-host/own-rt-iq3', a.host_binary),
                     ('build/device/p58-cache-fixtures', P0 / 'build/device/p58-cache-fixtures')):
        (P / rel).parent.mkdir(parents=True, exist_ok=True); shutil.copy2(src, P / rel)
    inject(P, flags)
    plan_note = plan_json(P)
    for f in P.glob('*.py'):
        compile(f.read_text(), str(f), 'exec')
    return copied, gates, plan_note


# 4. Real-parser gate per model window ----------------------------------------
PARSE = r'''
import json,subprocess,sys,tempfile
from pathlib import Path
from types import SimpleNamespace
P=Path(sys.argv[1]);flags=json.loads(sys.argv[2]);invalid=sys.argv[3]
sys.path.insert(0,str(P))
import suite_driver as D, composition as C
host=P/'build/gnu-host/own-rt-iq3';env=dict(PATH='/usr/bin:/bin',OMP_NUM_THREADS='2')
manifest=D.oracle_inputs();rows=[]
def parse(argv,out):
    a=list(argv);a[a.index('--output')+1]=str(out)
    cp=subprocess.run([str(host),'--p58r-parse-test',*a],stdin=subprocess.DEVNULL,capture_output=True,text=True,env=env,timeout=120)
    receipt=json.loads((out/'parser.json').read_text()) if (out/'parser.json').is_file() else None
    return cp,receipt
with tempfile.TemporaryDirectory(prefix='derive-parse-') as tmp:
    for window in ('KD','W2m','WS','WS128x','WS128'):
        out=Path(tmp)/window;out.mkdir();table=out/'suite-inputs.tsv';table.write_text('')
        actual=D.native_command(SimpleNamespace(window=window,view='down-tile16',miss_mode='zerocopy',output=out),manifest,table)
        C.check(actual)
        argv=list(actual[3:]);argv.remove('--authorized-device-window');argv[argv.index('--native-nice')+1]='19'
        row=dict(window=window,actual_native_argv=actual,flags={})
        for flag,value in flags.items():
            if actual.count(flag)!=1 or actual[actual.index(flag)+1]!=value:
                print(json.dumps(dict(passed=False,reason=f'{window}: {flag} {value} missing from window argv')));sys.exit(3)
        cp,receipt=parse(argv,out/'with')
        if cp.returncode!=0 or not receipt or receipt.get('passed') is not True or receipt.get('device_executed') is not False or receipt.get('model_reads') is not False:
            print(json.dumps(dict(passed=False,reason=f'{window}: real parser refused the chain argv with the flags: '+(cp.stderr or cp.stdout).strip()[-400:])));sys.exit(3)
        row['parser_receipt']=receipt
        for flag,value in flags.items():
            i=argv.index(flag);bad=list(argv);bad[i+1]=invalid
            cpb,_=parse(bad,out/('bad'+flag))
            without=argv[:i]+argv[i+2:];cpw,rw=parse(without,out/('without'+flag))
            if cpb.returncode==0:
                print(json.dumps(dict(passed=False,reason=f'{window}: parser accepted {flag} {invalid}; the value is not validated, so acceptance proves nothing')));sys.exit(3)
            if cpw.returncode!=0 or not rw or rw.get('passed') is not True:
                print(json.dumps(dict(passed=False,reason=f'{window}: argv without {flag} no longer parses; the flag is not an optional process-wide option')));sys.exit(3)
            row['flags'][flag]=dict(value=value,accepted=True,invalid_value_refused=True,invalid_error=(cpb.stderr or cpb.stdout).strip()[-200:],omitted_parses=True)
        rows.append(row)
print(json.dumps(dict(passed=True,records=rows)))
'''


def parser_gate(P, flags):
    cp = subprocess.run([sys.executable, '-B', '-c', PARSE, str(P), json.dumps(flags), INVALID],
                        stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=1200)
    try:
        row = json.loads(cp.stdout.strip().splitlines()[-1])
    except (IndexError, ValueError):
        raise Refused('parser gate crashed: ' + (cp.stderr or cp.stdout)[-800:])
    refuse(cp.returncode == 0 and row.get('passed') is True, 'REFUSED: ' + row.get('reason', 'parser gate failed'))
    return row['records']


# 5. Generated seal / verify_ready -------------------------------------------
SEAL = r'''#!/usr/bin/env python3
"""Generated by ops/onecard_chain_derive.py: verify the derived chain seal (never launch)."""
import hashlib,json,sys
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text())
def require(ok,why):
    if not ok:raise ValueError(why)
def verify_files(root,files):
    require(isinstance(files,dict) and bool(files),'empty closure')
    for n,h in files.items():require(sha(root/n)==h,'changed sealed input: '+n)
verify=verify_files
def main():
    import resource;resource.setrlimit(resource.RLIMIT_AS,(2_000_000_000,2_000_000_000))
    require('--verify' in sys.argv,'derived packets are sealed by onecard_chain_derive.py only; use --verify')
    row=read(P/'build-receipt.json')
    for root,key in ((ROOT,'sources'),(P,'artifacts'),(P,'gates')):verify_files(root,row[key])
    for name in row['gates']:
        g=read(P/name);require(g.get('passed') is True and g.get('device_executed') is False,'CPU gate failed: '+name)
    pins=read(P/'submission-pins.json');verify_files(ROOT,pins['sources'])
    require(pins['build_receipt_sha256']==sha(P/'build-receipt.json'),'stale submission pins')
    print(json.dumps(dict(passed=True,device_executed=False,sources=len(row['sources']),artifacts=len(row['artifacts']))))
if __name__=='__main__':main()
'''

VERIFY = r'''#!/usr/bin/env python3
"""Generated by ops/onecard_chain_derive.py: recompute readiness; never trust ready.json."""
import argparse,hashlib,json,shlex,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
DERIVED=json.loads((P/'derived-chain.json').read_text())
def require(ok,why):
    if not ok:raise ValueError(why)
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def chain_command():
    from launch_env import library_path
    command=DERIVED['chain_command']
    require('LD_LIBRARY_PATH='+shlex.quote(library_path())+' ' in command,'library path differs from the sealed chain command')
    return command
def verify():
    import window as W
    seal=W.build_gate()
    from composition import DIMENSIONS, FLAGS
    selection=json.loads((P/'runtime-selection.json').read_text())
    require(all(selection.get(k)==v and seal.get(k)==v for k,v in DIMENSIONS.items()),'full composition binding differs')
    require(all(FLAGS.get(f)==v for f,v in DERIVED['flags'].items()),'generated chain flags differ')
    require(selection.get('chain_flags')==DERIVED['flags']==seal.get('chain_flags'),'chain flag binding differs')
    pins=json.loads((P/'submission-pins.json').read_text())
    require(pins['build_receipt_sha256']==W.sha(P/'build-receipt.json'),'submission pins stale');W.verify_files(ROOT,pins['sources'])
    require(not (ROOT/DERIVED['chain_output']).exists(),'fresh chain output required; no retry')
    b=DERIVED['bracket'];summary=ROOT/b['summary']['parent_relpath'];window=summary.parent/'window.json'
    require(sha(summary)==b['summary']['parent_digest'] and sha(window)==b['window']['parent_digest'],'bracket evidence changed')
    s=json.loads(summary.read_text());boot=json.loads(window.read_text())['boot_id']
    require(s['candidate_beats_all_controls'] is True and s['control_drift_passed'] is True,'bracket gate failed')
    require(boot==Path('/proc/sys/kernel/random/boot_id').read_text().strip() or DERIVED.get('boot_check')=='cpu-rehearsal','same-hold chain requires current bracket boot')
    flags=json.loads((P/'evidence/chain-flags.json').read_text())
    require(flags['passed'] and flags['binary_sha256']==seal['artifacts']['build/device/own-rt-iq3'],'chain flag gate differs')
    return dict(passed=True,bracket_passed=True,candidate_beats_all_controls=True,boot_id=boot,rates=s['rates'],
                control_drift_fraction=s['control_drift_fraction'],minimum_gain=s['minimum_gain_vs_best_control'],
                record_gain_measured=False,chain_flags=DERIVED['flags'],build_receipt_sha256=W.sha(P/'build-receipt.json'),
                submission_pins_sha256=W.sha(P/'submission-pins.json'))
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path);args=ap.parse_args()
    row=dict(schema='onecard-chain-derive.ready.v1',passed=False,ready=False,device_executed=False,chain_command=chain_command(),coordinator_only=True,launch_performed=False)
    try:row.update(verify(),ready=True)
    except (ValueError,OSError,KeyError,TypeError,AssertionError,subprocess.TimeoutExpired) as error:row['reason']=str(error)
    if args.output:
        require(args.output.resolve()==P/'ready.json','only local ready.json may be written')
        args.output.write_text(json.dumps(row,indent=2)+'\n')
    print(json.dumps(row,indent=2));return 0 if row['ready'] else 1
if __name__=='__main__':
    import resource
    resource.setrlimit(resource.RLIMIT_AS,(2_000_000_000,2_000_000_000));raise SystemExit(main())
'''


def main(argv=None):
    resource.setrlimit(resource.RLIMIT_AS, (2_000_000_000, 2_000_000_000))
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    for name in ('parent-orch', 'packet', 'out', 'unit', 'output', 'binary', 'host-binary', 'bracket-summary', 'threshold-file'):
        ap.add_argument('--' + name, required=True)
    ap.add_argument('--flag', action='append', default=[])
    ap.add_argument('--cpu-rehearsal', action='store_true',
                    help='tests only: a bracket from an earlier boot is accepted at verify time (disclosed in READY)')
    a = ap.parse_args(argv)
    created = []
    try:
        flags = parse_flags(a.flag)
        P = Path(a.packet).absolute(); O = Path(a.out).absolute(); root = P.parents[3]
        refuse(P.parent.name == 'stage2' and O.parent.name == 'ops' and O.parent.parent == P.parent.parent,
               '--packet must be <root>/experiments/own-xpu-runtime/stage2/<name> and --out its sibling ops/<name>')
        refuse(not P.exists() and not O.exists(), 'refusing to write into an existing packet or orchestration dir')
        O0 = Path(a.parent_orch).absolute(); R0 = read(O0 / 'READY-FOR-DEVICE.json')
        refuse(R0.get('ready_for_device_chain') is True and R0.get('passed') is True, 'parent orchestration is not READY')
        refuse(hashlib.sha256(R0['chain_command'].encode()).hexdigest() == R0['chain_command_digest_sha256'], 'parent chain command digest differs')
        P0 = P.parent / R0['packet']; refuse(P0.is_dir(), 'parent packet missing: ' + str(P0))
        refuse(list(R0['windows']) == ['K1a', 'K1b', *MODEL_WINDOWS], 'parent windows differ from the one-card chain')
        unit0 = R0['coordinator_unit']; out0 = Path(R0['chain_output']).name; fr0 = Path(R0['fault_review']).name
        out = Path(a.output); refuse(out.parent == Path('evidence') and out.name.startswith('card0-'), '--output must be evidence/card0-<tag>')
        tag = out.name[len('card0-'):]; fault = f'fault-review-{tag}.json'
        refuse(a.unit.startswith('packet58-onecard-') and tag in a.unit, '--unit must be packet58-onecard-<tag>')
        bracket = bracket_gate(a.bracket_summary)
        summary = Path(a.bracket_summary).absolute()
        bracket_packet = next((p for p in summary.parents if p.parent.name == 'stage2'), summary.parent)
        helps, help_text = help_gate(flags, Path(a.binary).resolve(), Path(a.host_binary).resolve(), bracket_packet)
        pairs = [(R0['packet'], P.name), (unit0, a.unit), (out0, out.name), (fr0, fault)]
        created += [P, O]
        copied, inherited_gates, plan_note = derive_packet(a, P0, P, flags, root, pairs)
        records = parser_gate(P, flags)
        binary_sha = sha(P / 'build/device/own-rt-iq3')
        save(P / 'evidence/chain-flags.json', dict(
            schema='onecard-chain-derive.chain-flags.v1', passed=True, device_executed=False, model_reads=False,
            flags=flags, binary_sha256=binary_sha, host_binary_sha256=sha(P / 'build/gnu-host/own-rt-iq3'),
            help=helps, model_windows=list(MODEL_WINDOWS), k1_windows='inherited K1 fixture binary; no model flags',
            parser=records, device_help_sandboxed=True))
        sel = read(P0 / 'runtime-selection.json'); sel['chain_flags'] = flags
        for flag, value in flags.items():
            sel[flag[2:].replace('-', '_')] = value
        save(P / 'runtime-selection.json', sel)
        threshold = Path(a.threshold_file).resolve(); shutil.copy2(threshold, P / 'record-threshold.snapshot')
        ledger = read(threshold); last = ledger['records'][-1]
        rates = ' / '.join(f'{r:.3f}' for r in bracket['rates'])
        flagtext = ' '.join(f'{k} {v}' for k, v in flags.items())
        policy = read(P / 'submission-policy.json')
        policy['schema'] = f'{P.name}.submission-policy.v1'
        policy['ledger_sha256'] = sha(P / 'record-threshold.snapshot')
        policy['supersedes'] = {k: last[k] for k in ('reference_submission', 'threshold_tok_s')}
        policy['readiness_amendment'] = (
            f'v5 A0/B0/A1/B1/A2: {rates} tok/s; A0 warm-up excluded; {bracket["exact_requests"]}/{bracket["request_count"]} exact, '
            f'drift {bracket["control_drift_fraction"]*100:.3f}%, minimum gain +{bracket["minimum_gain"]*100:.2f}%; '
            f'chain flags {flagtext} on every model window; readiness only. Only fresh WS128 timing above '
            f'{last["threshold_tok_s"]} tok/s ({last["reference_submission"]}) and the live ledger may be submitted; '
            f'otherwise the submission tool refuses.')
        save(P / 'submission-policy.json', policy)
        chain_command = rewrite(R0['chain_command'], [(str(P0), str(P)), *pairs])
        derived = dict(schema='onecard-chain-derive.v1', flags=flags, chain_command=chain_command,
                       chain_output=str((P / out).relative_to(root)), unit=a.unit,
                       boot_check='cpu-rehearsal' if a.cpu_rehearsal else 'current-boot',
                       bracket=dict(summary=record(summary, root), window=record(summary.parent / 'window.json', root),
                                    **{k: bracket[k] for k in ('rates', 'control_drift_fraction', 'minimum_gain', 'exact_requests', 'request_count', 'boot_id')}),
                       parent=dict(orchestration=record(O0 / 'READY-FOR-DEVICE.json', root), packet=P0.name),
                       identity_rewrites=[dict(parent=x, derived=y) for x, y in pairs], plan_output=plan_note)
        save(P / 'derived-chain.json', derived)
        put(P / 'seal.py', SEAL); put(P / 'verify_ready.py', VERIFY)
        put(P / 'WINDOW.md', f'''# {P.name} record-chain coordinator contract (generated)

Generated by ops/onecard_chain_derive.py from {O0.name} (packet {P0.name}).
CPU preparation only. Recheck seal.py --verify and verify_ready.py --output ready.json.
Use the exact chain_command in ready.json. Unit: {a.unit}.
Fresh output: {out}. Fresh fault review:
evidence/{fault} (fault_review.py immediately before launch).

Pause and drain both lanes. Hold the whole host through
K1a -> K1b -> KD -> W2m -> WS -> WS128x -> WS128 with {R0["gap_seconds"]}-second gaps.
Freeze Codex from WS through WS128 completion; one attempt, no retry.
Every model window (KD/W2m/WS/WS128x/WS128) appends: {flagtext}
(real-parser gate: evidence/chain-flags.json). K1a/K1b keep the inherited fixture.
All other window arguments, admission, memory, fault, drain and exactness gates
are the parent's, unchanged; every model window must exactly match the oracle.

Bracket (readiness only): {rates} tok/s, {bracket["exact_requests"]}/{bracket["request_count"]} exact,
drift {bracket["control_drift_fraction"]*100:.3f}%, minimum gain +{bracket["minimum_gain"]*100:.2f}%.
Only fresh WS128 supplies record timing; it must exceed {last["threshold_tok_s"]} tok/s
({last["reference_submission"]}) and the live ledger.
''')
        # Seal: every packet-local file; inherited gates byte-identical to the parent.
        prc = read(P0 / 'build-receipt.json')
        excluded = {'build-receipt.json', 'submission-pins.json', 'ready.json', 'READY-FOR-DEVICE.json'}
        files = [f for f in P.glob('*') if f.is_file() and f.suffix in TEXT and f.name not in excluded]
        for d in COPY_DIRS:
            files += [f for f in (P / d).rglob('*') if f.is_file() and '__pycache__' not in f.parts]
        artifacts = {r: sha(P / r) for r in ('build/device/own-rt-iq3', 'build/device/p58-cache-fixtures', 'build/gnu-host/own-rt-iq3')}
        gates = {n: sha(P / n) for n in inherited_gates}; gates['evidence/chain-flags.json'] = sha(P / 'evidence/chain-flags.json')
        for n in inherited_gates:
            refuse(sha(P / n) == sha(P0 / n), 'inherited gate copy differs: ' + n)
        receipt = {k: v for k, v in prc.items() if k not in ('sources', 'artifacts', 'gates', 'bracket_native', 'superseded_bracket_objects', 'chain_interface_patch', 'closure_before_packet58asd')}
        receipt.update(sources={str(f.relative_to(root)): sha(f) for f in files}, artifacts=artifacts, gates=gates,
                       chain_flags=flags, native_recompiled=binary_sha != prc['artifacts'].get('build/device/own-rt-iq3'),
                       parent_build_receipt=record(P0 / 'build-receipt.json', root), revision='derived:' + P.name,
                       inherited_gates_from_parent=sorted(inherited_gates), copied_from_parent=copied)
        save(P / 'build-receipt.json', receipt)
        names = [n for n in ('packet58_submission.py', 'composition.py', 'submission_cli.py', 'shared_submission_cli.py', 'suite_metrics.py', 'submission-policy.json', 'record-threshold.snapshot') if (P / n).is_file()]
        save(P / 'submission-pins.json', dict(schema=f'{P.name}.submission-pins.v1', build_receipt_sha256=sha(P / 'build-receipt.json'),
                                              sources={str((P / n).relative_to(root)): sha(P / n) for n in names}, artifacts=artifacts, finalized_before_chain=True))
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
        for args in (['seal.py', '--verify'], ['verify_ready.py', '--output', str(P / 'ready.json')]):
            cp = subprocess.run([sys.executable, '-B', str(P / args[0]), *args[1:]], cwd=root, stdin=subprocess.DEVNULL, capture_output=True, text=True, env=env, timeout=600)
            refuse(cp.returncode == 0, f'{args[0]} refused: ' + (cp.stdout + cp.stderr)[-1500:])
        ready = read(P / 'ready.json'); refuse(ready['ready'] is True and ready['chain_command'] == chain_command, 'ready.json not ready')
        # Temporary lanequeue plan (live queue untouched).
        O.mkdir()
        job = dict(name=f'{P.name}-chain-A', lane='A', argv=['/usr/bin/python3', '-B', str(P / 'queue_runner.py'), '--authorized-device-window', '--card', '0', '--view', 'down-tile16', '--output-root', str(P / out), '--fault-review', '{REVIEW}'],
                   review=str(P / 'fault_review.py'), planned_write_bytes=R0.get('planned_write_bytes', 1),
                   plan=dict(rehearsal_only=True, actual_unit=a.unit, scope='whole-host', host_required_available_bytes=98990252032,
                             entry_rehearsal=dict(binaries=[dict(path=str((P / 'build/device/own-rt-iq3').relative_to(root)), sha256=artifacts['build/device/own-rt-iq3']),
                                                            dict(path=str((P / 'build/device/p58-cache-fixtures').relative_to(root)), sha256=artifacts['build/device/p58-cache-fixtures'], args=['--help'], returncode=0, contains='--output')])))
        put(O / 'entry-proposal.jsonl', json.dumps(job) + '\n')
        with tempfile.TemporaryDirectory(prefix='derive-plan-') as tmp:
            (Path(tmp) / 'queue-A.txt').write_bytes((O / 'entry-proposal.jsonl').read_bytes())
            cp = subprocess.run([sys.executable, '-B', str(root / 'experiments/own-xpu-runtime/ops/lane-queue/lanequeue.py'), 'plan', '--lane', 'A', '--directory', tmp],
                                cwd=root, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=600)
        put(O / 'queue-plan.log', cp.stdout + cp.stderr)
        plans = [json.loads(x) for x in cp.stdout.splitlines() if x.startswith('{')]
        refuse(cp.returncode == 0 and len(plans) == 1 and plans[0].get('plan') == 'passed', 'temporary lanequeue plan refused: ' + (cp.stdout + cp.stderr)[-800:])
        save(O / 'help.json', dict(device=help_text['device'], host=help_text['host']))
        shutil.copy2(Path(__file__), O / 'onecard_chain_derive.py')
        pfiles = ['build-receipt.json', 'submission-pins.json', 'ready.json', 'WINDOW.md', 'runtime-selection.json', 'submission-policy.json',
                  'record-threshold.snapshot', 'derived-chain.json', 'seal.py', 'verify_ready.py', 'fault_review.py', 'evidence/chain-flags.json']
        ofiles = ['entry-proposal.jsonl', 'queue-plan.log', 'help.json', 'onecard_chain_derive.py']
        row = dict(schema=f'{P.name}.ready-for-device.v1', packet=P.name, revision='derived:' + P.name,
                   prepared_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), generator='ops/onecard_chain_derive.py',
                   preparation_passed=True, passed=True, ready_for_device=True, ready_for_device_chain=True, ready_for_coordinator_check=True,
                   reason=f'Derived from {O0.name}: parent chain harness and gates unchanged except {flagtext} on every model window and the chain binary.',
                   chain_binary_sha256=binary_sha, parent_chain_binary_sha256=prc['artifacts'].get('build/device/own-rt-iq3'),
                   coordinator_unit=a.unit, chain_unit=a.unit, chain_output=derived['chain_output'],
                   fault_review=str((P / 'evidence' / fault).relative_to(root)), chain_command=chain_command,
                   chain_command_digest_sha256=hashlib.sha256(chain_command.encode()).hexdigest(), command_hash_encoding='UTF-8, no trailing newline',
                   windows=R0['windows'], gap_seconds=R0['gap_seconds'], wait_seconds=R0.get('wait_seconds'), lane='A', card=0, scope='whole-host',
                   configuration=sel, chain_flags=flags, whole_host_hold_required_through_gaps=True, both_lanes_pause_and_drain_required=True,
                   codex_frozen_from='WS', codex_frozen_through='WS128 completion',
                   bracket_rates_tok_s=bracket['rates'], control_drift_fraction=bracket['control_drift_fraction'], minimum_gain=bracket['minimum_gain'],
                   candidate_beats_all_controls=True, bracket_exact_requests=bracket['exact_requests'], pinned_predecessor=policy['supersedes'],
                   submission_scope_tokens=128, strict512_claim=False, fresh_timing_repeat_passed=False, chain_native_interface_passed=True,
                   bracket_boot_check=derived['boot_check'], preparation_ram_budget_bytes=2_000_000_000,
                   files_sha256={str((P / n).relative_to(root)): sha(P / n) for n in pfiles},
                   orchestration_provenance=[record(O / n, root) for n in ofiles],
                   parent_provenance=[record(O0 / 'READY-FOR-DEVICE.json', root), record(P0 / 'build-receipt.json', root)],
                   chain_quality_pending=True, chain_performance_pending=True, no_retry=True, queued=False, device_executed=False,
                   services_started=False, model_payload_reads=False, live_queue_changed=False, submission_performed=False, final_content_write=True)
        for f in (P / 'READY-FOR-DEVICE.json', O / 'READY-FOR-DEVICE.json'):
            save(f, row)
        print(json.dumps(dict(passed=True, ready=str(O / 'READY-FOR-DEVICE.json'), flags=flags, digest=row['chain_command_digest_sha256'])))
        return 0
    except Refused as e:
        for d in created:
            if d.exists():
                shutil.rmtree(d)
        print('onecard_chain_derive: ' + str(e), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
