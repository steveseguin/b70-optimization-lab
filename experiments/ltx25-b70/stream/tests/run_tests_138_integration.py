#!/home/steve/.venvs/ltx25-baseline/bin/python -B
"""Packet138 in-process protocol tests. No sockets, server, GPU or signals.

The sealed schemas/math are tested by the runtime suite. These synthetic rows
isolate client status/receipt/decode/preview/verdict option and hash bindings.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('client138_fixtures', HERE/'run_tests_138.py')
f = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f)
m, TMP, check, stopped = f.m, f.TMP, f.check, f.stopped


def row_for(st, index=0, kind='stream'):
    return dict(run_name='stream138-s%08d' % index, kind=kind, stream_seq=index,
                chunk_index=index % 3, frames=st['frames'], placement=st['placement'], committed=True,
                server_identity_sha256='s', anchor='frame', decoder_graph=st['decoder_graph'],
                levers=dict(anchor_decode='cone', bencode_overlap=1, prep_ahead=1),
                server_options=f.client().status_server_options(st))


def verdict_fixture(st):
    c = f.candidate_client(st) if st['text_residency']=='split36' else f.client()
    c.a.expect_f32_scan = st['f32_scan']
    c.a.expect_text_prefetch = st['text_prefetch']
    c.server_options = c.status_server_options(st)
    c.frames = st['frames']
    c.state = {}
    rows = [row_for(st, k, 'qualify-eager') for k in range(9)]
    decodes = {r['run_name']: dict(run_name=r['run_name'], display_device='xpu:3',
                                 server_options=dict(r['server_options'])) for r in rows}
    raw_rows = {r['run_name']: json.dumps(r).encode() for r in rows}
    raw_decodes = {name: json.dumps(r).encode() for name, r in decodes.items()}
    c.qual_params = lambda status: rows
    c.c.run_name = lambda params: params['run_name']
    c.fetch_receipt_raw = lambda name: raw_rows[name]
    c.fetch_record_raw = lambda kind, name, code: raw_decodes[name]
    c.rc.validate_decode_record = lambda record, receipt: record
    pairs = [dict(chunk=k, all_identical=True) for k in range(3)]
    calls = []
    def decide(receipts, records, captures, plan, *args, **kwargs):
        calls.append((receipts, records, plan, kwargs['server_options']))
        return dict(passed=True, failures=[], signatures_per_route=4, exact_replay=pairs)
    c.gate = SimpleNamespace(decide=decide)
    c.reference_hashes = lambda: {}
    verdict = dict(passed=True, failures=[], exact_replay=pairs, plan_sha256=st['plan_sha256'],
                   server_options=c.status_server_options(st),
                   receipts={name: {'sha256': hashlib.sha256(raw).hexdigest()} for name, raw in raw_rows.items()},
                   decode_records={name: {'sha256': hashlib.sha256(raw).hexdigest()} for name, raw in raw_decodes.items()})
    return c, verdict, raw_rows, raw_decodes, calls


def write_verdict(st, v):
    raw = json.dumps(v).encode()
    (TMP/'stream-qualification-verdict.json').write_bytes(raw)
    return dict(st, qualification_verdict_sha256=hashlib.sha256(raw).hexdigest())


for st in (dict(base, f32_scan=mode, text_prefetch=pf) for base in (f.STATUS, f.candidate()) for mode in ('parent', 'bulk') for pf in (('off', 'scheduled') if base['text_residency']=='split36' else ('off',))):
    label = st['text_residency'] + '/' + st['f32_scan']
    c = f.candidate_client(st) if st['text_residency']=='split36' else f.client()
    c.a.expect_f32_scan = st['f32_scan']
    c.a.expect_text_prefetch = st['text_prefetch']
    c.frames = st['frames']
    options = c.status_server_options(st)
    c.server_options = options
    c.preflight(st)
    receipt = row_for(st)
    expect = dict(run_name=receipt['run_name'], stream_seq=0, predecessor=None)
    check(label+' receipt accepts matching residency',
          c.verify_receipt(json.dumps(receipt).encode(), None, expect) == receipt)
    for key in options:
        changed = copy.deepcopy(receipt)
        del changed['server_options'][key]
        check(label+' receipt missing '+key, stopped(12, lambda: c.verify_receipt(
              json.dumps(changed).encode(), None, expect)))
        record = dict(display_device='xpu:3', server_options=changed['server_options'])
        try:
            c.validate_decode_identity(record, receipt)
            okay = False
        except ValueError:
            okay = True
        check(label+' decode missing '+key, okay)
    eager = dict(receipt, kind='qualify-eager')
    record = dict(display_device='xpu:3', server_options=dict(options))
    check(label+' eager decode accepts matching residency', c.validate_decode_identity(record, eager)==record)
    for key, value in (('text_residency', 'legacy' if st['text_residency']=='split36' else 'split36'),
                       ('text_oracle_sha256', '0'*64), ('f32_scan', 'parent' if st['f32_scan']=='bulk' else 'bulk')):
        changed = copy.deepcopy(receipt); changed['server_options'][key] = value
        check(label+' receipt drift '+key, stopped(12, lambda: c.verify_receipt(
              json.dumps(changed).encode(), None, expect)))
    vclient, v, raw_rows, raw_decodes, calls = verdict_fixture(st)
    vclient.verify_qualification(write_verdict(st, v))
    check(label+' verdict rederives nine receipts and decodes', len(calls)==1 and
          len(calls[0][0])==len(calls[0][1])==9 and calls[0][3]==options)
    check(label+' verdict persists verified identity', vclient.state['qualification']['server_identity_sha256']=='s')
    for key in options:
        bad = copy.deepcopy(v); del bad['server_options'][key]
        check(label+' verdict missing '+key, stopped(13, lambda: vclient.verify_qualification(write_verdict(st, bad))))
    for key in ('text_residency', 'text_oracle_sha256', 'f32_scan', 'text_prefetch'):
        for index in range(9):
            vc, good, rr, dd, ignored = verdict_fixture(st)
            name = list(rr)[index]
            bad_row = json.loads(rr[name]); del bad_row['server_options'][key]
            rr[name] = json.dumps(bad_row).encode()
            good['receipts'][name]['sha256'] = hashlib.sha256(rr[name]).hexdigest()
            check(label+' qualification receipt%d missing %s' % (index,key),
                  stopped(13, lambda: vc.verify_qualification(write_verdict(st,good))))
            vc, good, rr, dd, ignored = verdict_fixture(st)
            name = list(dd)[index]
            bad_decode = json.loads(dd[name]); del bad_decode['server_options'][key]
            dd[name] = json.dumps(bad_decode).encode()
            good['decode_records'][name]['sha256'] = hashlib.sha256(dd[name]).hexdigest()
            check(label+' qualification decode%d missing %s' % (index,key),
                  stopped(13, lambda: vc.verify_qualification(write_verdict(st,good))))
    for key in ('text_residency', 'text_oracle_sha256', 'f32_scan', 'text_prefetch'):
        vc = f.client(); vc.server_options=options
        vc.output_dir=TMP/'output'; vc.a.save_wait=1
        vc.check_fault_files=lambda name: None
        vc.rc.validate_preview_record=lambda record, receipt: record
        bad_options=dict(options); del bad_options[key]
        vc.api=SimpleNamespace(get=lambda route: (200,json.dumps(dict(server_options=bad_options)).encode()))
        preview=dict(receipt,preview={'path':str(vc.output_dir/receipt['run_name']/'preview_00001_.mp4')})
        check(label+' preview missing '+key, stopped(7,lambda:vc.wait_preview(preview)))

print('\n%d/%d passed' % (sum(ok for _,ok in f.RESULTS), len(f.RESULTS)))
raise SystemExit(0 if all(ok for _,ok in f.RESULTS) else 1)
