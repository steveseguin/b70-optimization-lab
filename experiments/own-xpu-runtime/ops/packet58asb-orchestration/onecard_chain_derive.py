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
pin relocation (pin_guard audit) -> seal -> verify_ready -> temporary lanequeue
plan -> READY written last.
Any refusal removes the directories this run created and writes no READY.

Pin-guard hygiene (packet172b): the --packet prefix (text before the first '-')
must not collide with any existing stage2/ops/proposal prefix, because the pin
guard globs ops/<prefix>-* into the packet's closure. Every pin in copied or
generated metadata must point inside the new packet at a file with identical
bytes, or become a non-pin provenance record {name, parent_relpath,
parent_digest}; evidence/pin-relocation.json lists each change.
"""
import argparse, datetime, hashlib, json, os, re, resource, shlex, shutil, subprocess, sys, tempfile
from pathlib import Path
from types import SimpleNamespace

OPS = Path(__file__).resolve().parent
PREFIX = re.compile(r'packet\d+[a-z]*')
MODEL_WINDOWS = ('KD', 'W2m', 'WS', 'WS128x', 'WS128')
SKIP_TOP = {'READY-FOR-DEVICE.json', 'ready.json', 'build-receipt.json', 'submission-pins.json',
            'seal.py', 'verify_ready.py', 'queue.lock', 'WINDOW.md'}
# lineage/: runtime-read closure (packet58asb launch 2: legacy_memory_plan.seed_observation reads
# lineage/fixtures/58c-supervisor after the KD native run). Copied byte for byte, sealed as sources.
COPY_DIRS = ('selections', 'frozen-inputs', 'host-admission', 'native', 'lineage', 'screen-reader')
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


def selection_extra(flags):
    """The ONLY source of the keys the chain adds to the sealed runtime selection."""
    return dict(chain_flags=dict(flags), **{flag[2:].replace('-', '_'): value for flag, value in flags.items()})


VIEWS_CHECK = 'if runtime!=dict('


def bind_views(P, P0, flags):
    """packet58as hand-added wait_policy to BOTH runtime-selection.json and views.validate's literal;
    the packet58asb launch failed because only the JSON changed. Generate both from selection_extra."""
    vt = (P / 'views.py').read_text(); extra = selection_extra(flags)
    parent = read(P0 / 'runtime-selection.json')
    refuse(MARK not in vt and vt.count(VIEWS_CHECK) == 1,
           'views.py must contain exactly one runtime-selection check (if runtime!=dict(...)); cannot bind chain flags')
    clash = sorted(set(extra) & set(parent))
    refuse(not clash, f'chain flag keys already in the parent runtime selection: {clash}; derive from a parent without them')
    put(P / 'views.py', vt.replace(VIEWS_CHECK, 'if runtime!=dict(**GENERATED_RUNTIME_SELECTION,').rstrip('\n') + f'''

{MARK}
# Same source as runtime-selection.json (onecard_chain_derive.selection_extra).
GENERATED_RUNTIME_SELECTION = {extra!r}
''')
    save(P / 'runtime-selection.json', dict(parent, **extra))


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
    bind_views(P, P0, flags)
    plan_note = plan_json(P)
    for f in P.glob('*.py'):
        compile(f.read_text(), str(f), 'exec')
    return copied, gates, plan_note


# 3a. Packet prefix gate (pin guard globs ops/<prefix>-*) ----------------------
def prefix_taken(prefix, stage, ops):
    number = prefix[len('packet'):]
    hits = [*stage.glob(prefix + '-*'), *ops.glob(prefix + '-*'),
            *(ops / 'lane-queue').glob('proposed-p' + number + '-*')]
    hits += [p for p in (stage / prefix, ops / prefix) if p.exists()]
    return sorted({str(p) for p in hits})


def free_prefix(prefix, stage, ops):
    letters = 'abcdefghijklmnopqrstuvwxyz'
    for suffix in [*letters, *(a + b for a in letters for b in letters)]:
        if not prefix_taken(prefix + suffix, stage, ops):
            return prefix + suffix
    return None


def prefix_gate(P, O):
    prefix, sep, label = P.name.partition('-')
    refuse(sep == '-' and label and PREFIX.fullmatch(prefix),
           f'--packet name must be packet<digits><letters>-<label> (the pin guard identifies packets by that prefix): {P.name!r}')
    refuse(O.name.startswith(prefix + '-'),
           f'--out must be ops/{prefix}-<label> so the pin guard reads this orchestration with its packet: {O.name!r}')
    taken = prefix_taken(prefix, P.parent, O.parent)
    if taken:
        free = free_prefix(prefix, P.parent, O.parent)
        shown = ', '.join(str(Path(t).relative_to(P.parent.parent)) for t in taken[:6]) + (f' (+{len(taken) - 6} more)' if len(taken) > 6 else '')
        raise Refused(f'REFUSED --packet {P.name}: its prefix {prefix!r} (text before the first "-") collides with '
                      f'existing {shown}. The pin guard globs stage2/{prefix}-* and ops/{prefix}-* into the packet '
                      f'closure, so another packet\'s pins would be checked as this packet\'s (the packet58as-b-confirm '
                      f'failure). Use a free prefix' + (f', for example --packet .../stage2/{free}-{label} --out .../ops/{free}-orchestration.' if free else '.'))
    return prefix


# 3b. Pin relocation: every pin inside the new packet with identical bytes, or provenance
def load_guard():
    if str(OPS / 'lane-queue') not in sys.path:
        sys.path.insert(0, str(OPS / 'lane-queue'))
    import pin_guard
    return pin_guard


def guard_manifests(guard, P, root, extra=()):
    """Every manifest pin_guard.collect_pins reads for P (wrapped read_metadata), plus extra roots."""
    read, paths, seen = guard.read_metadata, guard.metadata_paths, []
    def wrapped(path):
        seen.append(Path(path)); return read(path)
    guard.read_metadata = wrapped
    guard.metadata_paths = lambda packet, root=root: sorted(set(paths(packet, root)) | {Path(e) for e in extra})
    try:
        pins, _ = guard.collect_pins(P, root)
    finally:
        guard.read_metadata, guard.metadata_paths = read, paths
    return list(dict.fromkeys(seen)), pins


def manifest_entries(guard, path):
    raw = guard.read_metadata(path)
    if path.name.endswith(('.json', '.json.gz')) or raw.lstrip().startswith((b'{', b'[')):
        row = json.loads(raw)
        direct = (guard.is_pin_file(path) and isinstance(row, dict) and 'schema' not in row
                  and all(isinstance(v, str) for v in row.values()))
        return 'json', row, direct, list(guard.extract_pins(row, 'sources' if direct else ''))
    lines = raw.decode().splitlines(); entries = []
    for line in lines:
        m = re.fullmatch(r'([0-9a-fA-F]{64})\s+\*?(.+)', line) if line.strip() and not line.startswith('#') else None
        if m:
            entries.append((m[2], m[1].lower()))
    return 'text', lines, False, entries


HASH_MAPS = {'sources', 'screen_sources', 'files_sha256', 'artifacts', 'gates', 'pins', 'files'}


def transform(row, fix, map_name=''):
    """Mirror pin_guard.extract_pins; fix(name, digest) -> None | ('path', new) | ('digest', new) | ('record', dict)."""
    if isinstance(row, list):
        return [transform(item, fix, map_name) for item in row]
    if not isinstance(row, dict):
        return row
    hash_map = map_name in HASH_MAPS or map_name.endswith(('_sources', '-sources'))
    record_path = row.get('path', row.get('file'))
    if isinstance(record_path, str) and ('sha256' in row or 'hash' in row):
        pk = 'path' if 'path' in row else 'file'; hk = 'sha256' if 'sha256' in row else 'hash'
        act = fix(record_path, str(row[hk]).lower())
        rest = transform({k: v for k, v in row.items() if k not in {'path', 'file', 'sha256', 'hash'}}, fix, '')
        if act is None:
            return {k: (rest[k] if k in rest else v) for k, v in row.items()}
        if act[0] == 'path':
            return {k: (act[1] if k == pk else rest.get(k, v)) for k, v in row.items()}
        if act[0] == 'digest':
            return {k: (act[1] if k == hk else rest.get(k, v)) for k, v in row.items()}
        return dict(act[1], **{k: v for k, v in rest.items() if k not in act[1]})
    out = {}
    for key, value in row.items():
        if isinstance(value, str) and re.fullmatch(r'[0-9a-fA-F]{64}', value):
            name = None
            if hash_map or '/' in key or '.' in key and not key.endswith(('_sha256', '.sha256')):
                name = key
            elif key.endswith('_sha256') and isinstance(row.get(key[:-7]), str) and ('/' in row[key[:-7]] or '.' in row[key[:-7]]):
                act = fix(row[key[:-7]], value.lower())
                if act and act[0] == 'path':
                    out[key[:-7]] = act[1]; out[key] = value; continue
                if act and act[0] == 'digest':
                    out[key] = act[1]; continue
                if act:
                    out[key[:-7]] = act[1]; continue   # path field becomes the provenance record; digest key dropped
            elif key in {'sha256', 'hash'} and any(isinstance(row.get(f), str) for f in ('path', 'file')):
                if any(fix(row[f], value.lower()) for f in ('path', 'file') if isinstance(row.get(f), str)):
                    raise Refused('unsupported pin shape for relocation: ' + json.dumps({k: row[k] for k in ('path', 'file') if k in row}))
            if name is not None:
                act = fix(name, value.lower())
                if act is None:
                    out[key] = value
                elif act[0] == 'path':
                    out[act[1]] = value
                elif act[0] == 'digest':
                    out[key] = act[1]
                else:
                    out[key] = act[1]
                continue
            if key not in out:
                out[key] = value
        elif isinstance(value, dict) and hash_map and 'sha256' in value and not {'path', 'file'}.intersection(value):
            act = fix(key, str(value['sha256']).lower())
            inner = transform({k: v for k, v in value.items() if k != 'sha256'}, fix, '')
            if act is None:
                out[key] = dict(value, **inner)
            elif act[0] == 'path':
                out[act[1]] = dict(value, **inner)
            elif act[0] == 'digest':
                out[key] = dict(value, **inner, sha256=act[1])
            else:
                out[key] = dict(act[1], **{k: v for k, v in inner.items() if k not in act[1]})
        elif isinstance(value, (dict, list)):
            out[key] = transform(value, fix, key if isinstance(value, dict) else '')
        else:
            out.setdefault(key, value)
    return out


def relocate_pins(P, P0, root, extra, changed=None):
    """Rewrite copied/generated metadata so the pin guard sees only packet-local identical-byte pins.

    A pin into the parent packet becomes the new packet's own copy only when that copy has the
    pinned bytes; otherwise it becomes {name, parent_relpath, parent_digest}. A packet-local
    sub-bundle seal (e.g. host-admission/seal.json) is re-bound only for siblings this run
    rewrote, with the parent binding kept as provenance. Shared immutable pins the guard allows
    outside both packets (packet49 oracle, model files, other packets' frozen binaries and
    completed evidence) are kept. Parent files are never modified."""
    guard = load_guard(); stage = root / 'experiments/own-xpu-runtime/stage2'
    changed = set() if changed is None else changed; log = []

    def rel(p):
        p = Path(p)
        return str(p.relative_to(root)) if p.is_relative_to(root) else str(p)

    def inside(p):
        return p.is_relative_to(P) and p.resolve().is_relative_to(P.resolve())

    def spell(name, manifest, target):
        if os.path.isabs(name):
            new = str(target)
        elif Path(name).parts and Path(name).parts[0] in {'stage1', 'stage2'}:
            new = str(target.relative_to(root / 'experiments/own-xpu-runtime'))
        elif Path(name).parts and Path(name).parts[0] in {'experiments', 'notes', 'scripts', 'data', 'ops'}:
            new = str(target.relative_to(root))
        else:
            base = P if manifest.parent.name in {'evidence', 'build'} else manifest.parent
            new = os.path.relpath(target, base)
        refuse(guard.pin_path(new, manifest, P, root) == target, f'pin respelling failed: {name} -> {new}')
        return new

    for _ in range(8):
        manifests, pins = guard_manifests(guard, P, root, extra)
        oracle = {(p, h) for p, h, s in pins if s.name == 'oracle-binding.json'}
        edits = 0
        for manifest in manifests:
            kind, row, direct, entries = manifest_entries(guard, manifest)
            actions = {}
            for name, digest in entries:
                target = guard.pin_path(name, manifest, P, root)
                if inside(target):
                    if target.is_file() and sha(target) == digest:
                        continue
                    parent = P0 / target.relative_to(P)
                    seal_local = (manifest.name == 'seal.json' and manifest.parent != P and manifest.parent.relative_to(P).parts[0] in COPY_DIRS
                                  and target.parent == manifest.parent and target in changed and target.is_file()
                                  and parent.is_file() and sha(parent) == digest)
                    if seal_local:
                        actions[(name, digest)] = ('digest', sha(target)); kind_ = 'rebound sub-bundle seal entry to the relocated sibling'
                    else:
                        actions[(name, digest)] = ('record', dict(name=target.name, parent_relpath=rel(parent), parent_digest=digest))
                        kind_ = 'provenance (packet copy missing or not byte-identical)'
                    log.append(dict(manifest=rel(manifest), pin=name, action=kind_, parent_relpath=rel(parent), parent_digest=digest,
                                    derived_relpath=rel(target), derived_digest=sha(target) if target.is_file() else None))
                elif target.is_relative_to(P0):
                    own = P / target.relative_to(P0)
                    if own.is_file() and sha(own) == digest:
                        actions[(name, digest)] = ('path', spell(name, manifest, own)); kind_ = 'repointed to identical packet copy'
                    else:
                        actions[(name, digest)] = ('record', dict(name=target.name, parent_relpath=rel(target), parent_digest=digest))
                        kind_ = 'provenance (parent file; no identical packet copy)'
                    log.append(dict(manifest=rel(manifest), pin=name, action=kind_, parent_relpath=rel(target), parent_digest=digest,
                                    derived_relpath=rel(own) if kind_.startswith('repointed') else None))
                elif not guard.immutable_reason(target, digest, P, oracle, stage):
                    actions[(name, digest)] = ('record', dict(name=target.name, parent_relpath=rel(target), parent_digest=digest))
                    log.append(dict(manifest=rel(manifest), pin=name, action='provenance (mutable file outside both packets)',
                                    parent_relpath=rel(target), parent_digest=digest))
            if not actions:
                continue
            refuse(inside(manifest), f'offending pins sit in a manifest outside the new packet: {manifest}')
            refuse(not manifest.name.endswith('.gz'), f'cannot relocate pins in compressed manifest {manifest}')
            fix = lambda n, d: actions.get((n, d))
            if kind == 'json':
                new = transform(row, fix, 'sources' if direct else '')
                put(manifest, json.dumps(new, indent=2, ensure_ascii=False) + '\n')
            else:
                out = []
                for line in row:
                    m = re.fullmatch(r'([0-9a-fA-F]{64})(\s+\*?)(.+)', line) if line.strip() and not line.startswith('#') else None
                    act = fix(m[3], m[1].lower()) if m else None
                    out.append(line if act is None else m[1] + m[2] + act[1] if act[0] == 'path' else act[1] + m[2] + m[3]
                               if act[0] == 'digest' else '# provenance ' + json.dumps(act[1], sort_keys=True))
                put(manifest, '\n'.join(out) + '\n')
            changed.add(manifest); edits += 1
        if not edits:
            return log
    raise Refused('pin relocation did not converge in 8 rounds')


def pin_audit(P, root, extra=(), parent=None):
    """Final audit: pin_guard semantics on the derived packet plus no pin into the parent packet."""
    guard = load_guard(); stage = root / 'experiments/own-xpu-runtime/stage2'
    manifests, pins = guard_manifests(guard, P, root, extra)
    oracle = {(p, h) for p, h, s in pins if s.name == 'oracle-binding.json'}
    bad = []
    for manifest in manifests:
        for name, digest in manifest_entries(guard, manifest)[3]:
            target = guard.pin_path(name, manifest, P, root)
            if target.is_relative_to(P) and target.resolve().is_relative_to(P.resolve()):
                if not (target.is_file() and sha(target) == digest):
                    bad.append(f'{manifest}: {name} (packet-local, missing or different bytes)')
            elif parent is not None and target.is_relative_to(parent):
                bad.append(f'{manifest}: {name} (pin into the parent packet)')
            elif not guard.immutable_reason(target, digest, P, oracle, stage):
                bad.append(f'{manifest}: {name} (cross-packet mutable pin)')
    return bad, manifests


def confirmation_of(last, root, bracket_packet, binary_sha):
    """A chain of the line that set the ledger's latest record is a confirmation, never a resubmission."""
    path = Path((last.get('result') or {}).get('path', ''))
    parts = path.parts
    pkt = parts[parts.index('stage2') + 1] if 'stage2' in parts[:-1] else None
    if not pkt:
        return None
    binary = root / 'experiments/own-xpu-runtime/stage2' / pkt / 'build/device/own-rt-iq3'
    same_binary = binary.is_file() and sha(binary) == binary_sha
    if pkt != bracket_packet.name and not same_binary:
        return None
    thr = last['threshold_tok_s']
    return dict(record_packet=pkt, reference_submission=last['reference_submission'], threshold_tok_s=thr,
                same_chain_binary=same_binary, chain_binary_sha256=binary_sha, resubmission=False,
                text=(f'Confirmation run, not a resubmission: the ledger\'s latest record {last["reference_submission"]} '
                      f'({thr:.3f} tok/s) came from {pkt}' + (f' with this same chain binary {binary_sha[:16]}' if same_binary else '')
                      + f'. This packet is a further fresh chain of that record line. The submission tool refuses unless fresh '
                      f'WS128 exceeds {thr} tok/s and the live ledger; a run at or below it is confirmation evidence only.'))


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


# 4a. Static runtime-read closure check ---------------------------------------
ROOT_EXPR = re.compile(r"Path\(__file__\)(?:\.resolve\(\))?\.(parent|parents\[(\d+)\])$")
OUTPUT_TOPS = {'evidence', 'build', 'submission', 'screen'}
RUNTIME_CREATED = {'queue.lock', 'window.lock'}     # opened with mode 'a' by queue_runner/window (created on use)


def _root_base(node, py, roots):
    """Base directory of a root expression: Path(__file__)...parent[s[N]], a known root name, or root.parents[N]."""
    import ast
    if isinstance(node, ast.Name):
        return roots.get(node.id)
    text = ast.unparse(node); m = ROOT_EXPR.match(text)
    if m:
        return py.parent if m[1] == 'parent' else py.parents[int(m[2])]
    if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Attribute) and node.value.attr == 'parents' \
            and isinstance(node.value.value, ast.Name) and node.value.value.id in roots and isinstance(node.slice, ast.Constant):
        return roots[node.value.value.id].parents[node.slice.value]
    if isinstance(node, ast.Attribute) and node.attr == 'parent' and isinstance(node.value, ast.Name) and node.value.id in roots:
        return roots[node.value.id].parent
    return None


def _joins(tree, py):
    """Constant path joins rooted at a packet/module root, and lineage/fixtures string literals."""
    import ast
    roots, found = {}, []
    for stmt in ast.walk(tree):
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                names = [target] if isinstance(target, ast.Name) else list(getattr(target, 'elts', []))
                values = [stmt.value] if isinstance(target, ast.Name) else list(getattr(stmt.value, 'elts', []))
                for n, v in zip(names, values):
                    if isinstance(n, ast.Name):
                        base = _root_base(v, py, roots)
                        if base is None and isinstance(v, ast.BinOp) and isinstance(v.op, ast.Div):
                            parts, left = [], v
                            while isinstance(left, ast.BinOp) and isinstance(left.op, ast.Div):
                                parts.insert(0, left.right); left = left.left
                            b = _root_base(left, py, roots)
                            if b is not None and parts and all(isinstance(x, ast.Constant) and isinstance(x.value, str) for x in parts):
                                base = b.joinpath(*[x.value for x in parts])
                        if base is not None:
                            roots[n.id] = base
    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            parts, left = [], node
            while isinstance(left, ast.BinOp) and isinstance(left.op, ast.Div):
                parts.insert(0, left.right); left = left.left
            base = _root_base(left, py, roots)
            consts = []
            for part in parts:
                if isinstance(part, ast.Constant) and isinstance(part.value, str):
                    consts.append(part.value)
                else:
                    break
            if base is not None and consts:
                found.append((base.joinpath(*consts), ast.unparse(node)[:120]))
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and re.match(r'(lineage|fixtures)/[\w.@+-]', node.value) and '\n' not in node.value:
            found.append((py.parent / node.value.split()[0], node.value[:120]))
    return found


def closure_check(P, P0, root):
    """Every packet file/dir a harness module names (constant joins under its root, lineage/fixtures
    literals) that the parent packet has must exist in the derived packet; lineage/fixtures bytes identical."""
    import ast
    missing, checked = [], 0
    modules = [f for f in P.rglob('*.py') if '__pycache__' not in f.parts and not f.name.startswith('test_')
               and f.relative_to(P).parts[0] not in {'lineage', 'frozen-inputs', 'build', 'evidence', 'submission'}]
    for py in sorted(modules):
        try:
            tree = ast.parse(py.read_text())
        except SyntaxError as e:
            missing.append(f'{py.relative_to(P)}: unparsable ({e})'); continue
        for target, where in _joins(tree, py):
            target = Path(os.path.normpath(target))
            if not target.is_relative_to(P):
                continue                      # shared repo paths resolve identically for parent and derived packet
            rel = target.relative_to(P); twin = P0 / rel
            if not twin.exists() or not rel.parts or rel.parts[0] in OUTPUT_TOPS or str(rel) in RUNTIME_CREATED:
                continue                      # run outputs, build tools' objects and sealed artifacts/gates are checked elsewhere
            checked += 1
            frozen = rel.parts[0] in ('lineage', 'fixtures') or 'fixtures' in rel.parts
            if twin.is_dir():
                for f in twin.rglob('*'):
                    if f.is_file() and '__pycache__' not in f.parts:
                        g = P / f.relative_to(P0)
                        if not g.is_file() or (frozen and sha(g) != sha(f)):
                            missing.append(f'{py.relative_to(P)}: {where} -> {g.relative_to(P)} (dir closure)')
            elif not target.is_file():
                missing.append(f'{py.relative_to(P)}: {where} -> {rel} (missing)')
            elif frozen and sha(target) != sha(twin):
                missing.append(f'{py.relative_to(P)}: {where} -> {rel} (bytes differ from parent)')
    return sorted(set(missing)), checked


# 4b. Pre-device window rehearsal (CPU) ---------------------------------------
# Runs every chain window's real Python entry (window.main with the queue_runner
# --plan argv) up to its first device-evidence boundary: K1a/K1b stop at the
# output-directory creation, KD..WS128 at the previous-window prerequisite.
# Executed for real: argparse, views.validate(view), authorization flag,
# closed_environment, build_gate, memory window_plan, storage, fault-review
# parsing, fault latch, record/digest construction. Simulated (coordinator and
# systemd properties): process priority, CPU affinity, the user-unit cgroup.
PREDEVICE = r"""
import json,os,sys,subprocess
from pathlib import Path
P=Path(sys.argv[1]);out=Path(sys.argv[2])
class Boundary(Exception):pass
sys.path.insert(0,str(P))
from launch_env import library_path   # the chain command's recorded oneAPI path (verify_ready binds it)
rows=[]
try:
    plan=subprocess.run([sys.executable,'-B',str(P/'queue_runner.py'),'--card','0','--view','down-tile16','--output-root',str(P/'evidence'/'.predevice-plan'),'--plan'],
                        stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=300,env=dict(os.environ,LD_LIBRARY_PATH=library_path()))
    cmds=json.loads(plan.stdout.strip().splitlines()[-1])['commands']
except Exception as e:
    print(json.dumps(dict(passed=False,reason='queue_runner --plan failed: '+repr(e)+' '+(plan.stderr[-600:] if 'plan' in dir() else ''))));sys.exit(3)
import window as W
real_mkdir=Path.mkdir
for name,cmd in cmds.items():
    argv=list(cmd[cmd.index(str(P/'window.py'))+1:])
    target=out/name;argv[argv.index('--output')+1]=str(target)
    mode=argv[argv.index('--window')+1]
    env={k:v for k,v in (a.split('=',1) for a in cmd[cmd.index('-i')+1:cmd.index('/usr/bin/python3')])}
    os.environ.clear();os.environ.update(env)
    W.os.getpriority=lambda *a,_m=mode:0 if _m.startswith('W') else 19
    W.os.sched_getaffinity=lambda *a,_m=mode:set(range(4))|set(range(16,20)) if _m.startswith('W') else set(range(8,16))|set(range(24,32))
    seen=[]
    W.user_unit_gate=lambda cgroup:seen.append('user_unit_gate (simulated)')
    def prerequisite(path,prev,identity):raise Boundary('previous-window prerequisite '+prev)
    W.prerequisite=prerequisite
    def mkdir(self,*a,**k):
        if Path(self)==target:raise Boundary('output directory creation')
        return real_mkdir(self,*a,**k)
    Path.mkdir=mkdir
    try:
        W.main(argv);rows.append(dict(window=name,passed=False,reason='window.main returned without reaching a device boundary'))
    except Boundary as b:
        rows.append(dict(window=name,mode=mode,passed=True,boundary=str(b),argv=argv,simulated=['priority','affinity','user_unit_gate']))
    except BaseException as e:
        rows.append(dict(window=name,mode=mode,passed=False,reason=type(e).__name__+': '+str(e)[:600],argv=argv))
    finally:
        Path.mkdir=real_mkdir
    if target.exists():rows[-1].update(passed=False,reason='rehearsal created '+str(target))
ok=len(rows)==7 and all(r['passed'] for r in rows)
print(json.dumps(dict(passed=ok,windows=[r['window'] for r in rows],records=rows)))
sys.exit(0 if ok else 3)
"""


def predevice_gate(P):
    """Every chain window's Python entry, on CPU, up to its device boundary; refuses on any pre-device failure."""
    with tempfile.TemporaryDirectory(prefix='derive-predevice-') as tmp:
        cp = subprocess.run([sys.executable, '-B', '-c', PREDEVICE, str(P), str(P / 'evidence' / ('.predevice-' + Path(tmp).name))],
                            cwd=P.parents[3], stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=1800,
                            env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
    for leftover in P.joinpath('evidence').glob('.predevice-*'):
        shutil.rmtree(leftover)
    try:
        row = json.loads(cp.stdout.strip().splitlines()[-1])
    except (IndexError, ValueError):
        raise Refused('pre-device window rehearsal crashed: ' + (cp.stderr or cp.stdout)[-1500:])
    failed = [f"{r['window']}: {r.get('reason')}" for r in row.get('records', []) if not r.get('passed')]
    refuse(cp.returncode == 0 and row.get('passed') is True,
           'REFUSED: pre-device window rehearsal failed: ' + ('; '.join(failed) or row.get('reason', '?'))[:2000])
    return row


def predevice_cli(argv):
    ap = argparse.ArgumentParser(prog='onecard_chain_derive.py --predevice-check',
                                 description='Run every chain window up to its device boundary on CPU (no launch).')
    ap.add_argument('packet', type=Path); a = ap.parse_args(argv)
    resource.setrlimit(resource.RLIMIT_AS, (2_000_000_000, 2_000_000_000))
    try:
        row = predevice_gate(a.packet.absolute())
    except Refused as e:
        print('onecard_chain_derive: ' + str(e), file=sys.stderr); return 2
    print(json.dumps(dict(passed=True, windows=row['windows'], boundaries={r['window']: r['boundary'] for r in row['records']})))
    return 0


# 4c. Post-native report rehearsal on REAL device evidence (CPU) ----------------
# window.main after the native child exits: native receipt checks, K1 summary,
# postload_observation (memory plan + seed observation), native file hashing and
# summary save, on a temp copy of a completed chain's evidence. The budget and
# memory admission come from that chain's own window.json records.
POSTNATIVE = r"""
import json,os,shutil,sys,tempfile
from pathlib import Path
P=Path(sys.argv[1]);src=Path(sys.argv[2]);tmp=Path(sys.argv[3])
sys.path.insert(0,str(P))
import window as W
ORDER=('K1a','K1b','KD','W2m','WS','WS128x','WS128');rows=[]
for i,name in enumerate(ORDER):
    mode='K1' if name.startswith('K1') else name;out=tmp/name
    try:
        shutil.copytree(src/name,out,symlinks=True,ignore=shutil.ignore_patterns('native-home'))
        row=json.loads((src/name/'window.json').read_text())
        W.require(row.get('passed') is True and row.get('device_executed') is True,'parent evidence window did not pass: '+name)
        if mode=='K1':
            summary=W.k1_summary(json.loads((out/'run/k1.json').read_text()))
            files={n:W.sha(out/n) for n in ('run/k1.json','run/k1-cases.jsonl')}
        else:
            prev=json.loads((src/ORDER[i-1]/'window.json').read_text())
            budget=W.M.window_plan(mode) if mode in ('KD','WS128') else W.M.window_plan(mode,prev['postload_memory'])
            receipt=json.loads((out/'run/receipt.json').read_text())
            W.require(receipt.get('passed') is True and receipt.get('safe_to_exit') is True and receipt.get('window')==mode,'native driver receipt incomplete')
            summary=json.loads((out/'run/summary.json').read_text())
            observation=W.postload_observation(out,budget,row['memory_admission'])
            files={str(p.relative_to(out)):W.sha(p) for p in (out/'run').rglob('*') if p.is_file()}
        summary['timing_claim_eligible']=mode=='WS128'
        W.save(out/'summary.json',summary)
        rows.append(dict(window=name,passed=True,native_files=len(files)))
    except BaseException as e:
        rows.append(dict(window=name,passed=False,reason=type(e).__name__+': '+str(e)[:600]))
    finally:
        shutil.rmtree(out,ignore_errors=True)
ok=len(rows)==7 and all(r['passed'] for r in rows)
print(json.dumps(dict(passed=ok,evidence=str(src),records=rows)));sys.exit(0 if ok else 3)
"""


def chain_evidence(*packets):
    """A completed one-card chain output (all 7 windows passed on the device) to rehearse reports on."""
    for packet in packets:
        for d in sorted((packet / 'evidence').glob('card0-*'), reverse=True):
            rows = [d / w / 'window.json' for w in ('K1a', 'K1b', *MODEL_WINDOWS)]
            if all(r.is_file() for r in rows) and all(read(r).get('passed') is True and read(r).get('device_executed') is True for r in rows):
                return d
    return None


def postnative_gate(P, evidence):
    refuse(evidence is not None and Path(evidence).is_dir(), 'no completed chain device evidence for the post-native rehearsal')
    with tempfile.TemporaryDirectory(prefix='derive-postnative-') as tmp:
        cp = subprocess.run([sys.executable, '-B', '-c', POSTNATIVE, str(P), str(evidence), tmp],
                            cwd=P.parents[3], stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=1800,
                            env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
    try:
        row = json.loads(cp.stdout.strip().splitlines()[-1])
    except (IndexError, ValueError):
        raise Refused('post-native rehearsal crashed: ' + (cp.stderr or cp.stdout)[-1500:])
    failed = [f"{r['window']}: {r.get('reason')}" for r in row.get('records', []) if not r.get('passed')]
    refuse(cp.returncode == 0 and row.get('passed') is True, 'REFUSED: post-native report rehearsal failed: ' + '; '.join(failed)[:2000])
    return row


def packet_parent(P, root):
    d = read(P / 'derived-chain.json'); P0 = P.parent / d['parent']['packet']
    bracket = root / d['bracket']['summary']['parent_relpath']
    bp = next((p for p in bracket.parents if p.parent.name == 'stage2'), None)
    return P0, bp


def checks_cli(argv):
    """--closure-check / --postnative-check <packet> [--evidence DIR] on an existing derived packet."""
    mode = argv[0]; ap = argparse.ArgumentParser(prog='onecard_chain_derive.py ' + mode)
    ap.add_argument('packet', type=Path); ap.add_argument('--evidence', type=Path); a = ap.parse_args(argv[1:])
    resource.setrlimit(resource.RLIMIT_AS, (2_000_000_000, 2_000_000_000))
    P = a.packet.absolute(); root = P.parents[3]; P0, bp = packet_parent(P, root)
    try:
        if mode == '--closure-check':
            missing, checked = closure_check(P, P0, root)
            refuse(not missing, f'REFUSED: runtime-read closure incomplete ({len(missing)}): ' + '; '.join(missing[:15]))
            print(json.dumps(dict(passed=True, checked=checked)))
        else:
            ev = a.evidence or chain_evidence(*(x for x in (bp, P0) if x))
            row = postnative_gate(P, ev)
            print(json.dumps(dict(passed=True, evidence=row['evidence'], windows=[r['window'] for r in row['records']])))
        return 0
    except Refused as e:
        print('onecard_chain_derive: ' + str(e), file=sys.stderr); return 2


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
        prefix_gate(P, O)
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
        sel = read(P / 'runtime-selection.json')            # written by bind_views (derive_packet)
        refuse(sel == dict(read(P0 / 'runtime-selection.json'), **selection_extra(flags)), 'runtime selection binding differs')
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
        confirmation = confirmation_of(last, root, bracket_packet, binary_sha)
        derived = dict(schema='onecard-chain-derive.v1', flags=flags, chain_command=chain_command,
                       chain_output=str((P / out).relative_to(root)), unit=a.unit,
                       boot_check='cpu-rehearsal' if a.cpu_rehearsal else 'current-boot',
                       bracket=dict(summary=record(summary, root), window=record(summary.parent / 'window.json', root),
                                    **{k: bracket[k] for k in ('rates', 'control_drift_fraction', 'minimum_gain', 'exact_requests', 'request_count', 'boot_id')}),
                       parent=dict(orchestration=record(O0 / 'READY-FOR-DEVICE.json', root), packet=P0.name),
                       identity_rewrites=[dict(parent=x, derived=y) for x, y in pairs], plan_output=plan_note,
                       confirmation=confirmation)
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
{confirmation['text'] if confirmation else ''}
Pin hygiene: copied parent metadata pins only this packet's identical-byte files or
carries {{name, parent_relpath, parent_digest}} provenance; evidence/pin-relocation.json.
''')
        # Pin relocation: no copied or generated manifest may pin the parent packet.
        gate_paths = [P / n for n in inherited_gates] + [P / 'evidence/chain-flags.json']
        relocation = relocate_pins(P, P0, root, gate_paths)
        save(P / 'evidence/pin-relocation.json', dict(
            schema='onecard-chain-derive.pin-relocation.v1', passed=True, device_executed=False, parent_packet=P0.name,
            rule='a pin into the parent packet is repointed only to an identical-byte copy in this packet; otherwise it '
                 'becomes {name, parent_relpath, parent_digest}; a packet-local sub-bundle seal is re-bound only for '
                 'siblings this run rewrote; shared immutable pins (oracle, models, frozen binaries) are kept',
            changes=relocation))
        # Seal: every packet-local file; inherited gates byte-identical to the parent.
        prc = read(P0 / 'build-receipt.json')
        excluded = {'build-receipt.json', 'submission-pins.json', 'ready.json', 'READY-FOR-DEVICE.json'}
        files = [f for f in P.glob('*') if f.is_file() and f.suffix in TEXT and f.name not in excluded]
        for d in COPY_DIRS:
            files += [f for f in (P / d).rglob('*') if f.is_file() and '__pycache__' not in f.parts]
        artifacts = {r: sha(P / r) for r in ('build/device/own-rt-iq3', 'build/device/p58-cache-fixtures', 'build/gnu-host/own-rt-iq3')}
        gates = {n: sha(P / n) for n in inherited_gates}; gates['evidence/chain-flags.json'] = sha(P / 'evidence/chain-flags.json')
        gates['evidence/pin-relocation.json'] = sha(P / 'evidence/pin-relocation.json')
        relocated_gates = sorted(n for n in inherited_gates if sha(P / n) != sha(P0 / n))
        relocated_manifests = sorted({c['manifest'] for c in relocation})
        for n in relocated_gates:
            refuse(str((P / n).relative_to(root)) in relocated_manifests, 'inherited gate copy differs without a pin relocation: ' + n)
        receipt = {k: v for k, v in prc.items() if k not in ('sources', 'artifacts', 'gates', 'bracket_native', 'superseded_bracket_objects', 'chain_interface_patch', 'closure_before_packet58asd')}
        receipt.update(sources={str(f.relative_to(root)): sha(f) for f in files}, artifacts=artifacts, gates=gates,
                       chain_flags=flags, native_recompiled=binary_sha != prc['artifacts'].get('build/device/own-rt-iq3'),
                       parent_build_receipt=record(P0 / 'build-receipt.json', root), revision='derived:' + P.name,
                       inherited_gates_from_parent=sorted(inherited_gates),
                       inherited_gate_parent_provenance=[record(P0 / n, root) for n in sorted(inherited_gates)],
                       relocated_gates=relocated_gates, copied_from_parent=copied)
        save(P / 'build-receipt.json', receipt)
        # Keys inherited from the parent receipt may pin parent files too: relocate the receipt alone.
        before = {f: sha(f) for f in P.rglob('*') if f.is_file() and 'build' not in f.relative_to(P).parts[:1]}
        late = relocate_pins(P, P0, root, gate_paths)
        refuse(all(sha(f) == h for f, h in before.items() if f != P / 'build-receipt.json'),
               'late pin relocation touched files other than build-receipt.json')
        if late:
            receipt = read(P / 'build-receipt.json'); receipt['receipt_pin_relocation'] = late
            save(P / 'build-receipt.json', receipt)
        names = [n for n in ('packet58_submission.py', 'composition.py', 'submission_cli.py', 'shared_submission_cli.py', 'suite_metrics.py', 'submission-policy.json', 'record-threshold.snapshot') if (P / n).is_file()]
        save(P / 'submission-pins.json', dict(schema=f'{P.name}.submission-pins.v1', build_receipt_sha256=sha(P / 'build-receipt.json'),
                                              sources={str((P / n).relative_to(root)): sha(P / n) for n in names}, artifacts=artifacts, finalized_before_chain=True))
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
        for args in (['seal.py', '--verify'], ['verify_ready.py', '--output', str(P / 'ready.json')]):
            cp = subprocess.run([sys.executable, '-B', str(P / args[0]), *args[1:]], cwd=root, stdin=subprocess.DEVNULL, capture_output=True, text=True, env=env, timeout=600)
            refuse(cp.returncode == 0, f'{args[0]} refused: ' + (cp.stdout + cp.stderr)[-1500:])
        ready = read(P / 'ready.json'); refuse(ready['ready'] is True and ready['chain_command'] == chain_command, 'ready.json not ready')
        bad, manifests = pin_audit(P, root, gate_paths, parent=P0)
        refuse(not bad, f'pin audit refused ({len(bad)} pins): ' + '; '.join(bad[:12]))
        missing, closure_checked = closure_check(P, P0, root)     # after seal/verify_ready: generated files exist
        refuse(not missing, f'REFUSED: runtime-read closure incomplete ({len(missing)}): ' + '; '.join(missing[:15]))
        predevice = predevice_gate(P)
        postnative = postnative_gate(P, chain_evidence(bracket_packet, P0))
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
        save(O / 'predevice-rehearsal.json', dict(schema='onecard-chain-derive.predevice.v1', device_executed=False, **predevice))
        save(O / 'postnative-rehearsal.json', dict(schema='onecard-chain-derive.postnative.v1', device_executed=False,
                                                   closure_check=dict(passed=True, checked=closure_checked), **postnative))
        shutil.copy2(Path(__file__), O / 'onecard_chain_derive.py')
        pfiles = ['build-receipt.json', 'submission-pins.json', 'ready.json', 'WINDOW.md', 'runtime-selection.json', 'submission-policy.json',
                  'record-threshold.snapshot', 'derived-chain.json', 'seal.py', 'verify_ready.py', 'fault_review.py', 'evidence/chain-flags.json']
        ofiles = ['entry-proposal.jsonl', 'queue-plan.log', 'help.json', 'predevice-rehearsal.json', 'postnative-rehearsal.json', 'onecard_chain_derive.py']
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
                   pin_audit=dict(passed=True, manifests=len(manifests), relocated=len(relocation), parent_pins=0,
                                  lanequeue_plan='passed (temporary queue dir)'),
                   confirmation_run=bool(confirmation), confirmation=confirmation,
                   predevice_rehearsal=dict(passed=True, windows=predevice['windows'],
                                            boundaries={r['window']: r['boundary'] for r in predevice['records']},
                                            simulated=['priority', 'affinity', 'user_unit_gate']),
                   runtime_closure_check=dict(passed=True, checked=closure_checked, copied_dirs=list(COPY_DIRS)),
                   postnative_rehearsal=dict(passed=True, evidence=str(Path(postnative['evidence']).relative_to(root)),
                                             windows=[r['window'] for r in postnative['records']]),
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
    if sys.argv[1:2] == ['--predevice-check']:
        raise SystemExit(predevice_cli(sys.argv[2:]))
    if sys.argv[1:2] in (['--closure-check'], ['--postnative-check']):
        raise SystemExit(checks_cli(sys.argv[1:]))
    raise SystemExit(main())
