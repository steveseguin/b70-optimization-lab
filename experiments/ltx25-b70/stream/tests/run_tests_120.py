#!/usr/bin/env python3
"""CPU-only packet120 client contract tests; no server, sockets, signals or GPU imports.

Run with bin/python -B tests/run_cpu_suites.py run_tests_120.py. Synthetic evidence
checks admission and binding; it proves neither numerical equality nor runtime timing.
"""
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import sys
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('client120_test', HERE.parent / 'ltx_continuation_client.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
TMP = Path(tempfile.mkdtemp(prefix='ltx-client120-cpu-'))
RESULTS = []


def check(name, ok):
    RESULTS.append((name, bool(ok)))
    print(('PASS ' if ok else 'FAIL ') + name, flush=True)


def stopped(code, fn):
    try:
        fn()
    except m.Stop as exc:
        return exc.code == code
    return False


OPTIONS = {'snapshot_mode': 'fingerprint', 'decoder_graph_pool_cap_bytes': 10**9,
           'display_schedule': 'eager-display', 'anchor_read_ahead': 0, 'snapshot_schedule': 'full', 'display_device': 'xpu:3'}
FEATURES = {k: True for k in ('decode_thread', 'async_preview', 'chain_reset', 'chunk_length_choice',
                            'sharpness_diagnostic', 'video_first_handoff', 'frame_anchor', 'decoder_graph',
                            'cone_anchor_decode', 'bencode_overlap', 'prep_ahead', 'chunk_121', 'timing_split',
                            'snapshot_fingerprint', 'decoder_graph_pool_cap')}
FEATURES.update({k + '_anchor': False for k in ('mixed', 'latent', 'guide')})
STATUS = dict(OPTIONS, packet=120, runtime_manifest_sha256='m', frames=121, placement='two-way20-28',
              text_reuse=1, anchor='frame', decoder_graph=1, anchor_decode='cone', bencode_overlap=1,
              prep_ahead=1, server_identity_sha256='s', receipt_dir=str(TMP / 'receipts'),
              output_directory=str(TMP / 'output'), features=FEATURES, phase='stream', plan_sha256=m.PACKETS[120]['plan_sha256'])


def client():
    c = m.Client.__new__(m.Client)
    c.a = SimpleNamespace(packet=120, manifest_sha256='m', expect_frames=None, expect_placement=None,
                          expect_text_reuse=None, expect_anchor=None, expect_decoder_graph=None,
                          expect_anchor_decode=None, expect_bencode_overlap=None, expect_prep_ahead=None,
                          expect_snapshot_mode=None, expect_pool_cap_bytes=None, expect_pool_cap_gb=None,
                          expect_display_schedule=None, expect_anchor_read_ahead=None, expect_snapshot_schedule=None, expect_display_device=None)
    c.c = SimpleNamespace(FRAME_CHOICES=(49, 97, 121), PLACEMENTS=('two-way', 'two-way20-28'),
                          ANCHORS=('frame',), DECODER_GRAPH_CHOICES=(0, 1), SNAPSHOT_MODES=('walk', 'fingerprint'),
                          check_levers=lambda *x: x, qualification_id=lambda *x, **kw: None)
    c.bind_dirs = lambda st: None
    c.run_dir = TMP
    c.frames, c.placement, c.ident = 121, 'two-way20-28', 's'
    c.anchor, c.decoder_graph, c.levers = 'frame', 1, ('cone', 1, 1)
    c.server_options = OPTIONS.copy()
    c.verdict_sha = 'v'
    c.rc = SimpleNamespace(validate_receipt=lambda r: r)
    return c


for attr in ('DECODER_GRAPH_PACKETS', 'DECODE_THREAD_PACKETS', 'RESET_PACKETS', 'LEVER_PACKETS', 'SERVER_OPTION_PACKETS'):
    check('120 participates in ' + attr, 120 in getattr(m, attr))
check('numeric packet120 parser', m.packet_id('120') == 120)
check('120 stream directory accepted', m.STREAM_DIR_RE_120.fullmatch('stream120-s00000012') is not None)
check('118b stream directory refused', m.STREAM_DIR_RE_120.fullmatch('stream118b-s00000012') is None)
for ds in ('sampler-a', 'sampler-b', 'eager-display'):
    for ar in (0, 1):
        for ss in ('full', 'a-xpu3-sync'):
            st = copy.deepcopy(STATUS)
            st.update(display_schedule=ds, anchor_read_ahead=ar, snapshot_schedule=ss)
            try:
                client().preflight(st)
                ok = True
            except m.Stop:
                ok = False
            check('valid status %s/%s/%s' % (ds, ar, ss), ok)
for key, values in {'display_schedule': (None, '', 'other'), 'anchor_read_ahead': (None, True, '1', 2),
                    'snapshot_schedule': (None, '', 'other')}.items():
    for value in values:
        st = copy.deepcopy(STATUS)
        st[key] = value
        check('invalid status %s=%r' % (key, value), stopped(8, lambda: client().preflight(st)))
st = copy.deepcopy(STATUS)
st.update(snapshot_mode='walk', snapshot_schedule='a-xpu3-sync')
st['features']['snapshot_fingerprint'] = False
check('sparse barriers refuse walk snapshot mode', stopped(8, lambda: client().preflight(st)))
for key, value in (('display_schedule', 'sampler-b'), ('anchor_read_ahead', 1), ('snapshot_schedule', 'a-xpu3-sync'), ('display_device', 'xpu:2')):
    c = client()
    setattr(c.a, 'expect_' + key, value)
    check('expected %s mismatch refuses' % key, stopped(8, lambda: c.preflight(STATUS)))
    st = copy.deepcopy(STATUS)
    st[key] = value
    c.preflight(st)
    check('expected %s matching accepts' % key, True)
for packet in ('120', '118b', 118):
    st = copy.deepcopy(STATUS)
    st['packet'] = packet
    check('packet type/identity %r refuses' % packet, stopped(8, lambda: client().preflight(st)))
check('complete six-field options from status', client().status_server_options(STATUS) == OPTIONS)
c = client()
c.a.packet = '118b'
check('118b preserves its two-field options', c.status_server_options(STATUS) == {
    'snapshot_mode': 'fingerprint', 'decoder_graph_pool_cap_bytes': 10**9})

expect = {'run_name': 'stream120-s00000000', 'stream_seq': 0, 'predecessor': None}
receipt = dict(run_name=expect['run_name'], kind='stream', stream_seq=0, chunk_index=0, frames=121,
               placement='two-way20-28', committed=True, server_identity_sha256='s', anchor='frame',
               decoder_graph=1, levers=dict(anchor_decode='cone', bencode_overlap=1, prep_ahead=1),
               server_options=OPTIONS.copy())
c = client()
check('receipt consistent options accepts', c.verify_receipt(json.dumps(receipt).encode(), None, expect) == receipt)
for key, value in (('display_schedule', 'sampler-b'), ('anchor_read_ahead', 1), ('snapshot_schedule', 'a-xpu3-sync'),
                   ('display_device', 'xpu:2'), ('snapshot_mode', 'walk'), ('decoder_graph_pool_cap_bytes', None)):
    r = copy.deepcopy(receipt)
    r['server_options'][key] = value
    check('receipt %s drift refused' % key, stopped(12, lambda: c.verify_receipt(json.dumps(r).encode(), None, expect)))
for key in OPTIONS:
    r = copy.deepcopy(receipt)
    del r['server_options'][key]
    check('receipt missing %s refused' % key, stopped(12, lambda: c.verify_receipt(json.dumps(r).encode(), None, expect)))

for key in OPTIONS:
    c = client()
    v = {'passed': True, 'failures': [], 'exact_replay': [{'all_identical': True}] * 3,
         'plan_sha256': m.PACKETS[120]['plan_sha256'], 'server_options': OPTIONS.copy()}
    del v['server_options'][key]
    raw = json.dumps(v).encode()
    (TMP / 'stream-qualification-verdict.json').write_bytes(raw)
    st = dict(STATUS, qualification_verdict_sha256=hashlib.sha256(raw).hexdigest())
    check('verdict missing %s refused before gate' % key, stopped(13, lambda: c.verify_qualification(st)))

for key in OPTIONS:
    c = client()
    v = {'passed': True, 'failures': [], 'exact_replay': [{'all_identical': True}] * 3,
         'plan_sha256': m.PACKETS[120]['plan_sha256'], 'server_options': OPTIONS.copy()}
    raw = json.dumps(v).encode()
    (TMP / 'stream-qualification-verdict.json').write_bytes(raw)
    st = dict(STATUS, qualification_verdict_sha256=hashlib.sha256(raw).hexdigest())
    r = copy.deepcopy(receipt)
    del r['server_options'][key]
    c.qual_params = lambda status: [{}]
    c.c.run_name = lambda params: 'qualification-fixture'
    c.fetch_receipt_raw = lambda name: json.dumps(r).encode()
    check('qualification receipt missing %s refused' % key, stopped(13, lambda: c.verify_qualification(st)))

for flag, value in (('--expect-display-schedule', 'sampler-b'), ('--expect-anchor-read-ahead', '1'),
                    ('--expect-snapshot-schedule', 'a-xpu3-sync')):
    with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
        try:
            m.main(['--work-dir', str(TMP / 'args'), '--packet', '118b', '--port', '18196', flag, value])
            ok = False
        except SystemExit as exc:
            ok = '--packet 119 or 120' in str(exc)
    check('new flag %s refused for118b' % flag, ok)

for value in (None, '', 'cpu', 'xpu:0', 2):
    st = dict(STATUS, display_device=value)
    check('invalid display device %r refused' % value, stopped(8, lambda: client().preflight(st)))
for key, value in (('frames', 97), ('anchor', 'latent'), ('anchor_decode', 'full'), ('display_schedule', 'sampler-a')):
    st = dict(STATUS, display_device='xpu:2')
    st[key] = value
    check('replica invalid combination %s refused' % key, stopped(8, lambda: client().preflight(st)))
st = dict(STATUS, plan_sha256='wrong-plan')
check('unrecognized plan refuses', stopped(8, lambda: client().preflight(st)))
for kind, configured, actual, passes in (
    ('stream', 'xpu:3', 'xpu:3', True), ('stream', 'xpu:2', 'xpu:2', True),
    ('stream', 'xpu:2', 'xpu:3', False), ('stream', 'xpu:3', None, False),
    ('qualify-eager', 'xpu:2', 'xpu:3', True), ('qualify-eager', 'xpu:2', 'xpu:2', False),
    ('qualify-graph', 'xpu:2', 'xpu:2', True), ('qualify-repeat', 'xpu:2', 'xpu:3', False)):
    r = {'kind': kind, 'server_options': {'display_device': configured}}
    try:
        client().validate_decode_identity({'display_device': actual}, r)
        ok = True
    except ValueError:
        ok = False
    check('decode device binding %s/%s/%s' % (kind, configured, actual), ok == passes)
c = client()
c.a.packet = 119
check('119 option identity remains five fields', c.status_server_options(STATUS) ==
      {key: value for key, value in OPTIONS.items() if key != 'display_device'})
check('119 decode records do not gain a required120 field', c.validate_decode_identity({}, {}) == {})
with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
    try:
        m.main(['--work-dir', str(TMP / 'args'), '--packet', '119', '--port', '18197', '--expect-display-device', 'xpu:2'])
        ok = False
    except SystemExit as exc:
        ok = '--packet 120' in str(exc)
check('119 refuses120 display device flag', ok)

# Audit events exercise the guard without calling open(), stat() or any device API.
for device_path in ('/dev/dri/renderD128', '/dev/dri', b'/dev/dri/card0'):
    try:
        sys.audit('open', device_path, 'r', 0)
        blocked = False
    except RuntimeError as exc:
        blocked = 'CPU suite refused device open' in str(exc)
    check('CPU runner blocks synthetic device-open audit %r' % device_path, blocked)

launcher = (HERE.parent / 'start-client-120.sh').read_text()
check('client wrapper uses fingerprint-pinned bin/python -B', '/bin/python -B ' in launcher and '/bin/python3' not in launcher)
check('client wrapper caps OMP', '--setenv=OMP_NUM_THREADS=4' in launcher)
check('client wrapper binds all three options', all(flag in launcher for flag in (
    '--expect-display-schedule', '--expect-anchor-read-ahead', '--expect-snapshot-schedule', '--expect-display-device')))
check('client wrapper workdir uses120 default', 'LTX_STREAM_WORKDIR:-/home/steve/ltx-stream/s120-live01' in launcher)
check('client wrapper clears only its own failed state and never restarts automatically',
      'systemctl --user reset-failed ltx120-stream-client-20261010 2>/dev/null' in launcher
      and '--property=Restart=no' in launcher
      and 'systemctl --user restart ' not in launcher and 'systemctl --user stop ' not in launcher)
bad = [name for name, ok in RESULTS if not ok]
print('\n%d/%d passed; CPU-only files in %s' % (len(RESULTS)-len(bad), len(RESULTS), TMP))
raise SystemExit(1 if bad else 0)
