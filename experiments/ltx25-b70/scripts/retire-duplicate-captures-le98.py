#!/usr/bin/env python3
"""Tier B retirement of duplicate tensor captures from packets <= 98 (2026-10-08 plan).

Owner approval 2026-10-08: "I give you approval to run the verify then delete script."
Scope: repeat captures from timed/endurance (throughput) arms of packets <= 98 whose
four tensor hashes AND whole file equal a protected keeper or the first-in-arm keeper,
which stays. Never proof/warm-up/probe/self arms, references, receipt keepers, anything
created on/after 2026-10-08 00:00 UTC, packets >= 99, or anything CURRENT.md names.

  census  [--packet N]                          read-only metadata selection, no hashing
  plan    --packet N --out PLAN.json            fresh scan + hash pass 1 (whole file and
                                                per-tensor vs summary.json) of every
                                                candidate and keeper; exclusive, fsynced
  apply   --plan P --sha256 S --receipt R       re-scan must reproduce the plan rows; hash
                                                pass 2 (pinned primitive) of every candidate
                                                and keeper; /proc fd scan; intent; per-file
                                                events; unlink (pass 3 inside the primitive)
  restore --plan P --sha256 S --receipt R       exclusive ordinary copies keeper -> path

Only tensors.safetensors is unlinked; summary.json and the run dir stay. No service,
device, GPU, endpoint, or host-setting operation. No retry: any error halts the batch
and the receipt records the completed prefix.
"""
import argparse
import concurrent.futures as cf
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
LANE = HERE.parent
REPO = LANE.parents[1]
PRIMITIVES = LANE / 'recovery/20261007-resolution103-retirement/retire103.py'
PRIMITIVES_SHA = '043912bdf375d36f0691cfa3d000a66a48408747d5837871b3d1af8da76150bb'
HEADROOM = REPO / 'scripts/check-storage-headroom.py'
SCHEMA = 'ltx.le98-duplicate-capture-retirement.v1'
FLOOR = 50 * 1024**3
CUTOFF_NS = int(dt.datetime(2026, 10, 8, tzinfo=dt.timezone.utc).timestamp()) * 10**9
TENSORS = ('audio_latent', 'images', 'video_latent', 'waveform')

# Overridable for CPU tests only.
ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
DATA = LANE / 'data'
RECEIPT_DIRS = [LANE / 'data/resume-20261007', LANE / 'data/resume-20261008']
CURRENT = REPO / 'CURRENT.md'
WORKERS = 2


def pinned(path, digest, name):
    if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise RuntimeError('reviewed helper source differs: ' + str(path))
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


H = pinned(PRIMITIVES, PRIMITIVES_SHA, 'le98_file_safety')
need, fp, canonical, safe = H.need, H.fp, H.canonical, H.safe
exclusive_json, fsync_dir, unlink_exact, restore_one = H.exclusive_json, H.fsync_dir, H.unlink_exact, H.restore_one
STAT_KEYS = H.STAT_KEYS

NAME_RE = re.compile(r'^([fs])(\d+)([a-z]*)-(.+)-(\d+)$')
EXCLUDED_ARM = re.compile(r'(^|-)(probe|self|wself|proofs|proofn|proof|warm|repro|ref|cap\d+|stream\d*)(-|$)')
PROTECTED_NAME = re.compile(r'^(stability-01-|continuation|stream1\d\d)|-ref-|-ref$|archive-')


def utc():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def validation():
    return ROOT / 'output/validation'


def tensor_path(name):
    return validation() / name / 'tensors.safetensors'


def git_tracked():
    """Paths (absolute) of tracked files under the lane data directory."""
    out = subprocess.run(['git', '-C', str(REPO), 'ls-files', '-z', '--', str(DATA)],
                         capture_output=True, check=True).stdout
    return [REPO / p for p in out.decode().split('\0') if p]


def load_json(path):
    with open(path, 'rb') as f:
        return json.loads(f.read())


def summary_key(name):
    """Four-tensor key from summary.json, or None if unreadable/incomplete."""
    try:
        s = load_json(validation() / name / 'summary.json')
        t = s['tensors']
        if sorted(t) != list(TENSORS) or s.get('run_name') != name:
            return None
        return tuple((k, t[k]['dtype'], tuple(t[k]['shape']), t[k]['sha256']) for k in TENSORS)
    except Exception:
        return None


def receipt_paths():
    """Every tensors.safetensors path named by a lab receipt/plan, with recorded hashes."""
    named, hashes = set(), {}
    def walk(v):
        if isinstance(v, dict):
            p = v.get('path')
            if isinstance(p, str) and p.endswith('/tensors.safetensors') and isinstance(v.get('sha256'), str):
                hashes.setdefault(p, set()).add(v['sha256'])
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)
        elif isinstance(v, str) and v.endswith('/tensors.safetensors'):
            named.add(v)
    for d in RECEIPT_DIRS:
        if not d.is_dir():
            continue
        for p in sorted(d.rglob('*.json')):
            if p.stat().st_size > 256 * 1024**2:
                continue
            try:
                doc = load_json(p)
            except Exception:
                continue
            # This helper's own plans/intents/receipts list candidates; they must not
            # protect the rows they plan (keepers there are protected by rule anyway).
            if isinstance(doc, dict) and doc.get('schema') == SCHEMA:
                continue
            walk(doc)
    named |= set(hashes)
    return named, hashes


def open_files():
    """(dev, ino) of every file open by any process whose fds this user can read."""
    seen, unreadable = set(), 0
    for pid in os.listdir('/proc'):
        if not pid.isdigit():
            continue
        try:
            fds = os.listdir(f'/proc/{pid}/fd')
        except OSError:
            unreadable += 1
            continue
        for fd in fds:
            try:
                s = os.stat(f'/proc/{pid}/fd/{fd}')
            except OSError:
                continue
            seen.add((s.st_dev, s.st_ino))
    return seen, unreadable


def process_cmdlines():
    own = {os.getpid(), os.getppid()}
    lines = []
    for pid in os.listdir('/proc'):
        if not pid.isdigit() or int(pid) in own:
            continue
        try:
            lines.append(Path(f'/proc/{pid}/cmdline').read_bytes().replace(b'\0', b' ').decode('utf-8', 'replace'))
        except OSError:
            continue
    return lines


def hash_capture(path):
    """Pass 1: independent reader. Whole-file SHA-256 plus per-tensor raw SHA-256,
    with fp()-identical stat-stability rules and record shape."""
    path = safe(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1, 'regular nlink1 file required')
        data = stream.read()
        after = os.fstat(stream.fileno())
        current = safe(path).stat()
        need(all(getattr(before, k) == getattr(after, k) == getattr(current, k) for k in STAT_KEYS),
             'file changed while hashing')
    need(len(data) == after.st_size and len(data) > 8, 'short read')
    n = int.from_bytes(data[:8], 'little')
    need(8 + n <= len(data), 'bad safetensors header')
    header = json.loads(data[8:8 + n])
    tensors = {}
    for k in TENSORS:
        a, b = header[k]['data_offsets']
        tensors[k] = hashlib.sha256(memoryview(data)[8 + n + a:8 + n + b]).hexdigest()
    record = {'path': str(path), 'sha256': hashlib.sha256(data).hexdigest(),
              **{k: getattr(after, k) for k in STAT_KEYS}}
    return record, tensors


def pmap(func, items):
    items = list(items)
    if WORKERS <= 1 or len(items) < 2:
        return [func(x) for x in items]
    with cf.ProcessPoolExecutor(max_workers=WORKERS) as pool:
        return list(pool.map(func, items, chunksize=4))


def census(packet=None):
    """Read-only, metadata-only selection. Deterministic for a given tree."""
    tracked = git_tracked()
    by_base = {}
    for p in tracked:
        by_base.setdefault(p.name, []).append(p)
    current_text = CURRENT.read_text(errors='replace') if CURRENT.exists() else ''
    named, recorded = receipt_paths()
    cmdlines = process_cmdlines()
    protected_keys, families, skipped = {}, {}, []
    out_of_scope = {}
    for name in sorted(os.listdir(validation())):
        t = tensor_path(name)
        if not t.exists():
            continue
        m = NAME_RE.match(name)
        is_protected = bool(PROTECTED_NAME.search(name)) or str(t) in named
        if is_protected:
            key = summary_key(name)
            if key is not None:
                protected_keys.setdefault(key, []).append(name)
            continue
        if not m or m.group(1) not in 'fs' or int(m.group(2)) > 98:
            continue
        pk = int(m.group(2))
        if packet is not None and pk != packet:
            continue
        family = name[:name.rfind('-')]
        arm = m.group(4)
        if EXCLUDED_ARM.search(arm):
            out_of_scope[family] = out_of_scope.get(family, 0) + 1
            continue
        families.setdefault(family, []).append(name)
    rows = []
    for family, names in sorted(families.items()):
        reason = None
        thr = by_base.get(family + '-throughput.json', [])
        if not thr:
            reason = 'no timed/throughput record in Git for this arm'
        else:
            try:
                docs = [load_json(p) for p in thr]
                if any(d.get('prefix') != family for d in docs):
                    reason = 'throughput record prefix differs'
                elif any(d.get('all_exact') is False for d in docs):
                    reason = 'throughput record says all_exact=false (possible failure evidence)'
            except Exception:
                reason = 'throughput record unreadable'
        if reason is None and family in current_text:
            reason = 'family named in CURRENT.md'
        if reason is None and any(family in c for c in cmdlines):
            reason = 'a running process names this family'
        if reason is not None:
            skipped.append({'family': family, 'captures': len(names), 'reason': reason})
            continue
        caps = []
        for name in names:
            t = tensor_path(name)
            s = os.lstat(t)
            caps.append((s.st_mtime_ns, name, s))
        caps.sort(key=lambda x: (x[0], x[1]))
        first = {}
        for _, name, s in caps:
            key = summary_key(name)
            if key is None:
                skipped.append({'path': str(tensor_path(name)), 'reason': 'summary.json missing/unreadable; stays'})
                continue
            if key not in first:
                first[key] = name                       # first-in-arm keeper stays
                continue
            why = None
            sp = validation() / name / 'summary.json'
            if not stat.S_ISREG(s.st_mode) or s.st_nlink != 1:
                why = 'not a regular nlink1 file'
            elif max(s.st_mtime_ns, s.st_ctime_ns, os.lstat(sp).st_mtime_ns) >= CUTOFF_NS:
                why = 'created/changed on or after 2026-10-08 UTC'
            elif name in current_text:
                why = 'run named in CURRENT.md'
            else:
                par = by_base.get(name + '-parity.json', [])
                ok = False
                try:
                    docs = [load_json(p) for p in par]
                    ok = bool(docs) and all(d.get('status') == 'passed' and
                                            any(e.get('name') == name for e in d.get('executions', []))
                                            for d in docs)
                except Exception:
                    ok = False
                if not ok:
                    why = 'no passed parity JSON for this run in Git'
            if why:
                skipped.append({'path': str(tensor_path(name)), 'reason': why})
                continue
            # Durable references first, then receipt-named keepers, then the first-in-arm keeper.
            prot = sorted(protected_keys.get(key, []), key=lambda n: (not PROTECTED_NAME.search(n), n))
            options = [('protected-reference' if PROTECTED_NAME.search(n) else 'receipt-keeper', n) for n in prot] + \
                      [('family-first', first[key])]
            rows.append({'name': name, 'family': family, 'packet': int(NAME_RE.match(name).group(2)),
                         'key': [list(x[:2]) + [list(x[2]), x[3]] for x in key],
                         'candidate_path': str(tensor_path(name)),
                         'summary_path': str(sp),
                         'parity_paths': sorted(str(p) for p in by_base[name + '-parity.json']),
                         'keeper_options': [{'kind': k, 'path': str(tensor_path(n))} for k, n in options]})
    return {'rows': rows, 'skipped': skipped, 'out_of_scope_arm_captures': out_of_scope,
            'receipt_named_count': len(named), 'recorded': {k: sorted(v) for k, v in recorded.items()}}


def _hash_job(path):
    try:
        return path, hash_capture(path), None
    except Exception as exc:
        return path, None, type(exc).__name__ + ': ' + str(exc)


def _fp_job(path):
    try:
        return path, fp(path), None
    except Exception as exc:
        return path, None, type(exc).__name__ + ': ' + str(exc)


def build_plan(packet):
    c = census(packet)
    rows, skipped = c['rows'], list(c['skipped'])
    keeper_paths = sorted({o['path'] for r in rows for o in r['keeper_options']})
    keepers = {}
    for path, res, err in pmap(_hash_job, keeper_paths):
        need(err is None, 'keeper unreadable: ' + path + ' ' + str(err))
        rec, tensors = res
        rec_hashes = c['recorded'].get(path)
        need(rec_hashes is None or rec['sha256'] in rec_hashes, 'KEEPER DIFFERS FROM ITS RECEIPT: ' + path)
        key = summary_key(Path(path).parent.name)
        need(key is not None and {k[0]: k[3] for k in key} == tensors, 'keeper payload differs from its summary: ' + path)
        keepers[path] = {'record': rec, 'receipt_sha256': rec_hashes}
    opened, unreadable = open_files()
    out = []
    results = dict((p, (res, err)) for p, res, err in pmap(_hash_job, [r['candidate_path'] for r in rows]))
    for r in rows:
        res, err = results[r['candidate_path']]
        if err is not None:
            skipped.append({'path': r['candidate_path'], 'reason': 'hash pass 1 failed: ' + err}); continue
        rec, tensors = res
        if {k[0]: k[3] for k in r['key']} != tensors:
            skipped.append({'path': r['candidate_path'], 'reason': 'payload differs from its summary.json'}); continue
        if (rec['st_dev'], rec['st_ino']) in opened:
            skipped.append({'path': r['candidate_path'], 'reason': 'file is open by a process'}); continue
        chosen = None
        for opt in r['keeper_options']:
            k = keepers[opt['path']]['record']
            if k['sha256'] == rec['sha256'] and k['st_size'] == rec['st_size'] and \
                    (k['st_dev'], k['st_ino']) != (rec['st_dev'], rec['st_ino']):
                chosen = opt; break
        if chosen is None:
            skipped.append({'path': r['candidate_path'], 'reason': 'tensor key matches but no whole-file-identical keeper'}); continue
        k = keepers[chosen['path']]
        out.append({'name': r['name'], 'family': r['family'], 'key': r['key'],
                    'candidate': rec, 'retained': k['record'], 'keeper_kind': chosen['kind'],
                    'keeper_receipt_sha256': sorted(k['receipt_sha256']) if k['receipt_sha256'] else None,
                    'summary': fp(r['summary_path']),
                    'parity': [fp(p) for p in r['parity_paths']],
                    'restore': {'destination': rec['path'], 'source': k['record']['path'],
                                'sha256': k['record']['sha256'], 'bytes': k['record']['st_size']}})
    used = sorted({r['retained']['path'] for r in out})
    return {'schema': SCHEMA, 'packet': packet, 'root': str(ROOT), 'created_utc': utc(),
            'helper_sha256': fp(Path(__file__).resolve())['sha256'], 'primitives_sha256': PRIMITIVES_SHA,
            'cutoff_utc': '2026-10-08T00:00:00Z',
            'approval': 'owner 2026-10-08: "I give you approval to run the verify then delete script." (Tier B)',
            'retire': out, 'skipped': skipped, 'out_of_scope_arm_captures': c['out_of_scope_arm_captures'],
            'keepers': [keepers[p]['record'] for p in used],
            'keepers_with_receipt_hash': sum(1 for p in used if keepers[p]['receipt_sha256']),
            'fd_scan': {'unreadable_pids': unreadable},
            'free_bytes_at_plan': free_bytes(),
            'reclaim_logical_bytes': sum(r['candidate']['st_size'] for r in out),
            'reclaim_allocated_bytes': sum(r['candidate']['st_blocks'] * 512 for r in out),
            'proof_status': 'hash pass 1: whole file + per-tensor vs summary.json; keeper whole-file identical'}


def free_bytes():
    v = os.statvfs(ROOT)
    return v.f_bavail * v.f_frsize


def checked_plan(path, digest):
    need(fp(path)['sha256'] == digest, 'explicit plan SHA mismatch')
    plan = load_json(path)
    need(plan['schema'] == SCHEMA and plan['root'] == str(ROOT) and plan['primitives_sha256'] == PRIMITIVES_SHA and
         plan['helper_sha256'] == fp(Path(__file__).resolve())['sha256'], 'plan/helper identity differs')
    for r in plan['retire']:
        a, b = r['candidate'], r['retained']
        need(a['sha256'] == b['sha256'] and a['st_size'] == b['st_size'] and a['st_nlink'] == b['st_nlink'] == 1 and
             a['path'] == str(tensor_path(r['name'])) and Path(a['path']).is_relative_to(validation()) and
             not PROTECTED_NAME.search(r['name']) and int(NAME_RE.match(r['name']).group(2)) == plan['packet'] <= 98 and
             r['restore'] == {'destination': a['path'], 'source': b['path'], 'sha256': b['sha256'], 'bytes': b['st_size']},
             'plan row inconsistent: ' + r['name'])
    need(len({r['candidate']['path'] for r in plan['retire']}) == len(plan['retire']), 'duplicate rows')
    need(not ({r['candidate']['path'] for r in plan['retire']} & {r['retained']['path'] for r in plan['retire']}),
         'a keeper is also a candidate')
    return plan


def verify_again(plan):
    """Fresh census must reproduce every row; hash pass 2 with the pinned primitive."""
    c = census(plan['packet'])
    fresh = {r['candidate_path']: r for r in c['rows']}
    for r in plan['retire']:
        f = fresh.get(r['candidate']['path'])
        need(f is not None, 'no longer a candidate on fresh scan (re-plan): ' + r['name'])
        need(r['retained']['path'] in [o['path'] for o in f['keeper_options']] and f['key'] == r['key'],
             'fresh mapping differs: ' + r['name'])
        need(sorted(p['path'] for p in r['parity']) == f['parity_paths'], 'parity evidence set differs: ' + r['name'])
        rec = c['recorded'].get(r['retained']['path'])
        need(rec is None or r['retained']['sha256'] in rec, 'KEEPER DIFFERS FROM ITS RECEIPT: ' + r['retained']['path'])
    keepers = {r['retained']['path']: r['retained'] for r in plan['retire']}
    for path, rec, err in pmap(_fp_job, sorted(keepers)):
        need(err is None and rec == keepers[path], 'keeper changed since plan (pass 2): ' + path + ' ' + str(err))
    cands = {r['candidate']['path']: r['candidate'] for r in plan['retire']}
    for path, rec, err in pmap(_fp_job, sorted(cands)):
        need(err is None and rec == cands[path], 'candidate changed since plan (pass 2): ' + path + ' ' + str(err))
    for r in plan['retire']:
        for e in [r['summary'], *r['parity']]:
            need(fp(e['path']) == e, 'summary/parity evidence changed: ' + e['path'])
    opened, unreadable = open_files()
    for r in plan['retire']:
        for x in (r['candidate'], r['retained']):
            need((x['st_dev'], x['st_ino']) not in opened, 'file is open by a process: ' + x['path'])
    return {'fresh_rows': len(c['rows']), 'keepers_rehashed': len(keepers), 'candidates_rehashed': len(cands),
            'fd_scan_unreadable_pids': unreadable, 'utc': utc()}


def stat_same(record):
    s = os.stat(record['path'], follow_symlinks=False)
    return stat.S_ISREG(s.st_mode) and all(getattr(s, k) == record[k] for k in STAT_KEYS)


def operate(mode, plan_path, digest, receipt):
    need(mode in ('apply', 'restore'), 'unsupported operation')
    plan = checked_plan(plan_path, digest)
    receipt = safe(Path(receipt).resolve(), False)
    need(not receipt.is_relative_to(ROOT), 'control output must be outside the artifact root')
    intent = receipt.with_name(receipt.name + '.intent.json')
    events = receipt.with_name(receipt.name + '.events.jsonl')
    need(not any(p.exists() for p in (receipt, intent, events)), 'operation output exists; no automatic retry')
    rows = plan['retire']
    admission = None
    if mode == 'apply':
        verification = verify_again(plan)
    else:
        verification = None
        for r in rows:
            need(fp(r['retained']['path']) == r['retained'], 'retained source changed: ' + r['retained']['path'])
            need(not os.path.lexists(r['candidate']['path']), 'restore destination exists; no overwrite/resume')
        module = H.load(HEADROOM, 'le98_headroom')
        planned = sum((r['candidate']['st_size'] + 4095) // 4096 * 4096 for r in rows) + 16 * 1024**2
        admission = module.inspect_destination(validation(), FLOOR, planned)
        need(admission['admitted'] is True, 'restore storage admission refused')
    free_before = free_bytes()
    exclusive_json(intent, {'schema': SCHEMA, 'mode': mode, 'plan': str(Path(plan_path).resolve()),
                            'plan_sha256': digest, 'packet': plan['packet'], 'rows': len(rows),
                            'verification_pass2': verification, 'storage_admission': admission,
                            'free_bytes_before': free_before, 'started_utc': utc(),
                            'restore_map': [r['restore'] for r in rows],
                            'status': 'intent-before-any-file-change'})
    with events.open('xb') as s:
        s.flush(); os.fsync(s.fileno())
    fsync_dir(events.parent)
    def event(v):
        with events.open('ab') as s:
            s.write(canonical(v) + b'\n'); s.flush(); os.fsync(s.fileno())
    completed, rmdirs, error = [], [], None
    try:
        for i, r in enumerate(rows):
            if mode == 'apply' and i and i % 50 == 0:
                opened, _ = open_files()
                need(not any((x['st_dev'], x['st_ino']) in opened for rr in rows[i:] for x in (rr['candidate'], rr['retained'])),
                     'a remaining candidate/keeper became open')
            need(stat_same(r['retained']), 'keeper stat changed: ' + r['retained']['path'])
            event({'phase': 'file-intent', 'mode': mode, 'candidate': r['candidate'], 'restore': r['restore'],
                   'utc': utc()})
            if mode == 'apply':
                unlink_exact(r['candidate'])          # re-hashes (pass 3) and re-stats before unlink
                actual = None
                parent = Path(r['candidate']['path']).parent
                with os.scandir(parent) as it:
                    empty = not any(it)
                if empty:
                    os.rmdir(parent); rmdirs.append(str(parent))
            else:
                actual = restore_one(r)
            completed.append(r['candidate']['path'])
            event({'phase': 'file-completed', 'mode': mode, 'path': completed[-1], 'restored_stat': actual})
    except BaseException as exc:
        error = type(exc).__name__ + ': ' + str(exc)
        raise
    finally:
        exclusive_json(receipt, {'schema': SCHEMA, 'mode': mode, 'packet': plan['packet'],
            'plan': str(Path(plan_path).resolve()), 'plan_sha256': digest,
            'status': 'completed' if error is None else 'incomplete-no-automatic-retry', 'error': error,
            'completed_count': len(completed), 'completed': completed, 'rmdir': rmdirs,
            'reclaim_allocated_bytes_completed': sum(r['candidate']['st_blocks'] * 512 for r in rows
                                                     if r['candidate']['path'] in set(completed)),
            'free_bytes_before': free_before, 'free_bytes_after': free_bytes(),
            'keepers_verified': len({r['retained']['path'] for r in rows}),
            'intent_sha256': fp(intent)['sha256'], 'events_sha256': fp(events)['sha256'],
            'finished_utc': utc(),
            'restore': 'restore --plan PLAN --sha256 PLAN_SHA --receipt NEW: exclusive ordinary copies from keepers',
            'proof_status': ('three whole-file SHA-256 passes equal to a retained keeper; keeper rehashed; '
                             'summary.json and Git parity JSON kept' if mode == 'apply'
                             else 'ordinary copies restored and hash-verified')})


def main():
    global WORKERS
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--workers', type=int, default=WORKERS)
    sub = p.add_subparsers(dest='mode', required=True)
    s = sub.add_parser('census'); s.add_argument('--packet', type=int); s.add_argument('--out', type=Path)
    s = sub.add_parser('plan'); s.add_argument('--packet', type=int, required=True); s.add_argument('--out', type=Path, required=True)
    for mode in ('apply', 'restore'):
        s = sub.add_parser(mode); s.add_argument('--plan', type=Path, required=True)
        s.add_argument('--sha256', required=True); s.add_argument('--receipt', type=Path, required=True)
    a = p.parse_args()
    WORKERS = a.workers
    if a.mode == 'census':
        c = census(a.packet)
        by = {}
        for r in c['rows']:
            by.setdefault(r['packet'], [0, 0])
            by[r['packet']][0] += 1
            by[r['packet']][1] += os.lstat(r['candidate_path']).st_blocks * 512
        summary = {'by_packet': {k: {'files': v[0], 'gib': round(v[1] / 2**30, 3)} for k, v in sorted(by.items())},
                   'skipped': c['skipped'], 'out_of_scope_arm_captures': c['out_of_scope_arm_captures']}
        if a.out:
            need(not a.out.resolve().is_relative_to(ROOT), 'output outside artifact root')
            a.out.write_text(json.dumps(summary, indent=1, sort_keys=True))
        print(json.dumps(summary['by_packet'], sort_keys=True))
        print('skipped', len(c['skipped']), 'out_of_scope_families', len(c['out_of_scope_arm_captures']))
    elif a.mode == 'plan':
        out = a.out.resolve()
        need(not out.is_relative_to(ROOT), 'plan must be outside the artifact root')
        plan = build_plan(a.packet)
        exclusive_json(out, plan)
        print(fp(out)['sha256'], 'rows', len(plan['retire']), 'skipped', len(plan['skipped']),
              'gib', round(plan['reclaim_allocated_bytes'] / 2**30, 3))
    else:
        operate(a.mode, a.plan, a.sha256, a.receipt)


if __name__ == '__main__':
    main()
