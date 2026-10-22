"""Packet184 production-shape rehearsal of the two-card checkpoint (CPU only, no payload).

Builds two fixtures from generated mocks of the REAL v5 entry sources (p184_shape_mock.py: numerical
device addresses, no device memory, no model payload; bundle-8 selection and dispatch, context 4096,
draft on rank 1, the real suite plan.tsv / identity.tsv / mtp-manifest.tsv):
  * fixture-p184   packet184's v5/native-src (+ v5/native/checkpoint_*.hpp) -- modes fresh/save/restore
  * fixture-parent packet184's copy-time sources (v5/lineage/parent-src, = packet153 with the copy
                   rewrites) -- mode fresh only
Each fixture process is ONE rank, as on device. Steps:
  1 fresh startup + request reset + admit N, both ranks, both fixtures: the prepared-command capture
    digests (every bank pair, extents, draft commands) must be EQUAL -> the delta changes no allocation
    and no prepared command of a fresh session at production shape;
  2 save at N = 342 (the smoke row's K=256 boundary of the 87-token incident prompt), both ranks
    (separate processes) inside the coordinator's exclusive lock, then the device-free commit tool,
    then the full inspect: real classification at production shape, real manifest, real bytes per
    buffer (blob contents are mock zeros);
  3 coverage at production shape: the labels the checkpoint classifies equal the engine's own
    request_state_inventory + state_dump enumeration + draft dump_all_state (both ranks, both ways);
  4 restore in FRESH processes (resume of the original prompt, M=128; and an append of a 126-token
    delta), each rank: request reset -> verify -> apply -> capture digest == step-1 capture of a fresh
    process admitted at N (the restore leaves prepared commands exactly as a fresh engine has them)
    -> one real half step at N on the restored engine (rank 1 runs the draft step first; rank 0 swaps
    its recurrent banks), all through the production prepared commands (mock compute).
Receipt: v5/evidence/production-shape.json (also the per-rank byte table for the README).
CPU limits: nice 19, cores 8-15,24-31, CPU disk stop 27 GB; each fixture process has a 300 s bound
(packet183 recorded 1.5-2.7 s per production-shape fixture run, v5/evidence/full-shape.json there).
"""
import hashlib, json, os, resource, shutil, struct, subprocess, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from p184_build_checkpoint import P, LOCAL, ROOT, B, CHECKED, sha, save, limits, compiler_turn
from p184_shape_mock import generate, body, once
import tp2_checkpoint as T

OUT = B / 'production-shape'
TOOL = B / 'tool/own-rt-ckpt-tool'
SUITE = LOCAL / 'lineage-inputs/vendor/repo/experiments/own-xpu-runtime/stage2/suite-inputs-20261012/incident-retrospective'
K, M, DELTA = 256, 128, 126


def mirror_sources(kind):
    """main.cpp/mtp.hpp/rank.hpp (+ native_controller.hpp for the parent) of one source set."""
    if kind == 'p184':
        src = dict(main=P / 'native-src/main.cpp', mtp=P / 'native-src/mtp.hpp', rank=P / 'native-src/rank.hpp', controller=None)
    else:
        d = P / 'lineage/parent-src'
        rows = json.loads((d / 'PARENT-SOURCES.json').read_text())['files']
        for name, row in rows.items():
            assert sha(d / name) == row['sha256'], 'parent source changed: ' + name
        src = dict(main=d / 'main.cpp', mtp=d / 'mtp.hpp', rank=d / 'rank.hpp', controller=d / 'native_controller.hpp')
    return src


def build(kind):
    src = mirror_sources(kind)
    S = OUT / ('fixture-' + kind)
    shutil.rmtree(S, ignore_errors=True)
    M_ = OUT / ('mirror-' + kind) / 'checked' / LOCAL.relative_to(ROOT)
    shutil.rmtree(OUT / ('mirror-' + kind), ignore_errors=True)
    M_.mkdir(parents=True)
    main = src['main'].read_text()
    main = once(main, '#include ' + json.dumps(str(P / 'native-src/mtp.hpp')), '#include ' + json.dumps(str(M_ / 'mtp.hpp')))
    main = once(main, '#include ' + json.dumps(str(P / 'native-src/rank.hpp')), '#include ' + json.dumps(str(S / 'rank.hpp')))
    (M_ / 'main.cpp').write_text(main)
    (M_ / 'mtp.hpp').write_text(src['mtp'].read_text())
    out = generate(M_, S, LOCAL)
    t = (out / 'main.cpp').read_text()
    # Packet111's shared-down functor names its extent 'capacity', which the inherited CPU capture
    # audit does not serialize; the test-only copy renames it to n (packet153/183 precedent).
    fusion = (CHECKED / 'p109_fusion.hpp').read_text()
    fusion = once(fusion, 'struct SharedDown final:p49c::Base {\n unsigned capacity;', 'struct SharedDown final:p49c::Base {\n unsigned n;')
    fusion = fusion.replace('auto b=bind(p,capacity);', 'auto b=bind(p,n);').replace('k.capacity=capacity', 'k.n=capacity')
    (out / 'p109_fusion.hpp').write_text(fusion)
    t = once(t, json.dumps(str(CHECKED / 'p109_fusion.hpp')), json.dumps(str(out / 'p109_fusion.hpp')))
    (out / 'main.cpp').write_text(t)
    rank = src['rank'].read_text()
    rank = body(rank, 'static void state_dump(Engine& e,int sequence)', '')   # its enumeration is recomputed by the fixture
    if src['controller'] is not None:
        rank = once(rank, json.dumps(str(CHECKED / 'native_controller.hpp')), json.dumps(str(out / 'native_controller.hpp')))
        (out / 'native_controller.hpp').write_text(src['controller'].read_text())
    (out / 'rank.hpp').write_text(rank)
    (out / 'entry.cpp').write_text((P / 'native/checkpoint_shape_entry.cpp').read_text().replace('P184_PACKET_PATH', json.dumps(str(LOCAL))))
    prior = json.loads((P / 'engine-commands.json').read_text())
    args = next(r['command'] for r in prior if r['name'] == 'gnu-host-entry-main')
    args = args[:args.index('-c')] if '-c' in args else args[:args.index('-o')]
    args = [v for v in args if not v.startswith('-O')] + ['-O0'] + (['-DP184_PARENT'] if kind == 'parent' else [])
    audit_p60 = out / 'audit-p60.cpp'
    audit_p60.write_text((CHECKED / 'p60_submit.cpp').read_text().replace('capacity', 'n'))
    (out / 'audit-parser.cpp').write_text('#include ' + json.dumps(str(CHECKED / 'p49d_small.hpp')) + '\n#include ' +
                                          json.dumps(str(P / 'native/audit_small.hpp')) + '\n#include ' + json.dumps(str(CHECKED / 'p49d_submit.cpp')) + '\n')
    link = list(next(r['command'] for r in prior if r['name'] == 'gnu-host-link'))
    link = [str(out / 'entry.o') if a.endswith('/entry-main.o') else a for a in link if not a.endswith('own-rt-iq3-entry.cpp.o')]
    link = [str(out / 'audit-p60.o') if Path(a).name.endswith(('p60_submit.o', 'p60_submit.cpp.o')) else a for a in link]
    link = [str(out / 'audit-dispatch.o') if a.endswith('/p49d_submit.o') else a for a in link]
    link[link.index('-o') + 1] = str(out / 'fixture')
    commands = [('compile', [*args, '-c', str(out / 'entry.cpp'), '-o', str(out / 'entry.o')]),
                ('audit-p60', [*args, '-c', str(audit_p60), '-o', str(out / 'audit-p60.o')]),
                ('audit-dispatch', [*args, '-c', str(out / 'audit-parser.cpp'), '-o', str(out / 'audit-dispatch.o')]),
                ('link', link)]
    with compiler_turn():
        for name, cmd in commands:
            limits()
            with (out / (name + '.log')).open('w') as log:
                subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=600)
            assert 'warning' not in (out / (name + '.log')).read_text().lower(), 'fixture build warning: ' + name
    return out / 'fixture', [c for _, c in commands]


def run(fixture, *args):
    limits()
    started = time.monotonic()
    cp = subprocess.run([str(fixture), *map(str, args)], stdin=subprocess.DEVNULL, capture_output=True, text=True,
                        timeout=300, env=dict(PATH='/usr/bin:/bin', OMP_NUM_THREADS='2'))
    assert cp.returncode == 0, (args, cp.stderr[-3000:])
    out = Path(args[2])
    return dict(json.loads((out / 'result.json').read_text()), wall_seconds=round(time.monotonic() - started, 2))


def main():
    limits()
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True)
    fixture, commands = build('p184')
    parent, parent_commands = build('parent')
    prompt = json.loads((SUITE / 'input.json').read_text())['tokens']
    assert len(prompt) == 87, len(prompt)
    N = len(prompt) + K - 1
    generated = [(17 * i + 5) % 248000 + 11 for i in range(K)]      # synthetic ids (no payload exists)
    history, pending = prompt + generated[:-1], generated[-1]
    assert len(history) == N
    rows = dict(position=N, prompt_length=len(prompt), K=K, M=M, fresh={}, save={}, restore={})
    # 1 fresh captures, packet184 vs parent, both ranks
    for rank in (0, 1):
        a = run(fixture, 'fresh', rank, OUT / f'fresh-p184-rank{rank}', N)
        b = run(parent, 'fresh', rank, OUT / f'fresh-parent-rank{rank}', N)
        assert a['capture'] == b['capture'], f'rank{rank}: packet184 changes a fresh prepared command or allocation'
        assert a['owned_bytes'] == b['owned_bytes'] and a['allocations'] == b['allocations'], f'rank{rank}: device allocation differs'
        rows['fresh'][rank] = dict(capture=a['capture'], owned_bytes=a['owned_bytes'], allocations=a['allocations'], equal_to_parent=True)
        print('fresh capture rank', rank, '== parent PASS', flush=True)
    # 2 save at production shape under the coordinator's exclusive lock, then commit + inspect
    root = OUT / 'ckpt'
    root.mkdir()
    cid = 'shape-s1'
    with T.Lock(root, cid, True, 'save'):
        d = root / cid
        d.mkdir()
        (d / 'rank0').mkdir()
        (d / 'rank1').mkdir()
        T.write_tokens(d / 'tokens.bin', history)
        for rank in (0, 1):
            rows['save'][rank] = run(fixture, 'save', rank, OUT / f'save-rank{rank}', d, N, pending)
            print('save rank', rank, 'PASS', rows['save'][rank]['bytes'], 'bytes', flush=True)
        code, commit = T.tool(TOOL, '--checkpoint-commit', d, '--tokenizer-identity', P / 'tokenizer-identity.tsv', '--prompt-length', len(prompt))
        assert code == 0 and commit['ok'], commit
    code, inspect = T.tool(TOOL, '--checkpoint-inspect', d)
    assert code == 0 and inspect['ok'], inspect
    manifest = inspect['manifest']
    # 3 coverage at production shape
    coverage = {}
    for rank in (0, 1):
        o = OUT / f'save-rank{rank}'
        labels = set(json.loads((o / 'state-labels.json').read_text()))
        inv = json.loads((o / 'request-state-inventory.json').read_text())
        labels |= set(inv['standalone_target_mutable'])
        if rank == 1:
            labels |= set(json.loads((o / 'draft-final-state/all-state.json').read_text())['mutable_sha256'])
        cov = rows['save'][rank]['coverage']
        covered = [c['label'] for c in cov]
        assert len(covered) == len(set(covered)) and set(covered) == labels, (rank, sorted(labels - set(covered))[:5], sorted(set(covered) - labels)[:5])
        host = {h['field'] for h in rows['save'][rank]['host_fields']}
        assert set(inv) - {'standalone_target_mutable'} <= host, rank
        by_rule = {}
        for c in cov:
            key = c['source'] + ' | ' + (c['rule'] if c['rule'].startswith('saved') else c['rule'].split(',')[0][:70])
            by_rule[key] = by_rule.get(key, 0) + 1
        coverage[rank] = dict(labels=len(labels), saved=sum(1 for c in cov if c['rule'].startswith('saved')), by_rule=by_rule)
        print('production coverage rank', rank, '== inventory PASS', len(labels), flush=True)
    # per-rank byte table (real extents at N; contents are mock zeros)
    table = []
    for rs in manifest['ranks']:
        groups = {}
        for b in rs['blobs']:
            n = b['name']
            group = ('draft ' if b['source'] == 'draft' else '') + (
                'QSA keys+values' if n.endswith(('.qsa.keys', '.qsa.values')) else 'QSA raw' if n.endswith('.qsa.raw') else
                'QSA pooled' if n.endswith('.qsa.pooled') else 'GDN state' if n.endswith('.gdn.state') else
                'GDN history' if n.endswith('.gdn.history') else 'PLE history' if n.endswith('.ple.history') else
                'token_history' if n.endswith('token_history') else 'boundary hidden stream' if n == 'streams' else 'controls')
            if b['source'] in ('spare', 'reserve'):
                group += ' (' + b['source'] + ' bank)'
            g = groups.setdefault(group, dict(blobs=0, bytes=0))
            g['blobs'] += 1
            g['bytes'] += b['bytes']
        table.append(dict(rank=rs['rank'], qsa_layers=rs['qsa_layers'], gdn_layers=rs['gdn_layers'], groups=groups,
                          total=sum(b['bytes'] for b in rs['blobs']), skipped=len(rs['skipped'])))
    # 4 restore in fresh processes: resume and append, capture == fresh, then one real half step
    inp_resume = OUT / 'input-resume.txt'
    inp_resume.write_text(' '.join(map(str, prompt)) + '\n')
    inp_append = OUT / 'input-append.txt'
    inp_append.write_text(' '.join(map(str, history + [pending] + [(7 * i + 3) % 248000 + 11 for i in range(DELTA)])) + '\n')
    for label, inp, count in (('resume', inp_resume, M), ('append', inp_append, M)):
        with T.Lock(root, cid, False, 'restore'):
            for rank in (0, 1):
                r = run(fixture, 'restore', rank, OUT / f'restore-{label}-rank{rank}', d, inp, count, P / 'tokenizer-identity.tsv')
                assert r['capture'] == rows['fresh'][rank]['capture'], f'{label} rank{rank}: restored prepared commands differ from a fresh engine at N'
                assert r['verify']['operation'] == ('same-generation-resume' if label == 'resume' else 'append'), r['verify']
                assert r['continue']['half_launches_issued'] > 0
                if rank == 0:
                    assert r['continue']['bank_parity_after'] != r['continue']['bank_parity_before']
                rows['restore'].setdefault(label, {})[rank] = r
                print('restore', label, 'rank', rank, 'PASS', flush=True)
    for rank in (0, 1):
        for k in ('coverage', 'host_fields'):
            rows['save'][rank].pop(k)
    save(P / 'evidence/production-shape.json', dict(
        passed=True, device_executed=False, model_payload_read=False,
        scope='production geometry (bundle-8 selection, context 4096, 24/24 split, MTP draft on rank 1), numerical device addresses, no payload; blob contents are mock zeros, extents and paths are real; not a device result',
        fixture_sha256=sha(fixture), parent_fixture_sha256=sha(parent), tool_sha256=sha(TOOL), commands=commands, parent_commands=parent_commands,
        checkpoint=dict(manifest_sha256=inspect['manifest_sha256'], save_bytes=manifest['measurements']['save_bytes'], ranks=table,
                        blobs_verified=inspect['verified']['blobs_verified'], commit=commit),
        coverage=coverage, **rows,
        payload_mocks=['numerical device addresses (no device memory)', 'weight and draft-head upload elision', 'zero rows for host lookups',
                       'value-tracking readback for allocations whose last upload was <= 64 bytes at offset 0; zeros otherwise', 'state_dump payload write elided (its enumeration recomputed)'],
        real_paths=['initialize', 'p105 split-head runtime', 'banks (three-bank miss path)', 'p149 probe allocation', 'SpeculativeImage',
                    'DraftRuntime', 'request_reset', 'request_state_inventory', 'DraftRuntime::dump_all_state', 'ckpt184 stage/commit/inspect/verify/apply',
                    'admit_position', 'DraftRuntime::run (draft step)', 'half_step + recurrent bank swap'],
        sources={str(f.relative_to(ROOT)): sha(f) for f in [Path(__file__).resolve(), P / 'p184_shape_mock.py', P / 'native/checkpoint_shape_entry.cpp',
                 *(P / 'lineage/parent-src').iterdir(), *P.glob('native-src/*'), P / 'native/checkpoint_tp2.hpp', P / 'native/checkpoint_format.hpp']}))
    shutil.rmtree(OUT)   # ~210 MB of fixtures and zero blobs; the receipt keeps every result (packet build cap 300 MB)
    print('production-shape checkpoint rehearsal PASS')


if __name__ == '__main__':
    resource.setrlimit(resource.RLIMIT_AS, (8 * 1024**3, 8 * 1024**3))
    main()
