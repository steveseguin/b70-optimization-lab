#!/usr/bin/env python3
"""CPU-only packet124 client contract tests; no server, sockets, signals or GPU imports.

Run with bin/python -B tests/run_cpu_suites.py run_tests_124.py. Synthetic evidence
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
spec = importlib.util.spec_from_file_location('client124_test', HERE.parent / 'ltx_continuation_client.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
TMP = Path(tempfile.mkdtemp(prefix='ltx-client124-cpu-'))
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


OPTIONS = {'display_worker': 'serial', 'run_write_allowance_bytes': 3 * 2**30, 'snapshot_mode': 'fingerprint', 'decoder_graph_pool_cap_bytes': 10**9, 'aux_residency': 'legacy', 'residency_qualification_id': 'residency-legacy',
           'display_schedule': 'eager-display', 'anchor_read_ahead': 0, 'snapshot_schedule': 'full', 'display_device': 'xpu:3'}
FEATURES = {k: True for k in ('decode_thread', 'async_preview', 'chain_reset', 'chunk_length_choice',
                            'sharpness_diagnostic', 'video_first_handoff', 'frame_anchor', 'decoder_graph',
                            'cone_anchor_decode', 'bencode_overlap', 'prep_ahead', 'chunk_121', 'chunk_145', 'timing_split',
                            'snapshot_fingerprint', 'decoder_graph_pool_cap')}
FEATURES.update(chunk_169=True, atomic_preview=True)
FEATURES.update({k + '_anchor': False for k in ('mixed', 'latent', 'guide')})
STATUS = dict(OPTIONS, packet=124, runtime_manifest_sha256='m', frames=121, placement='two-way20-28',
              text_reuse=1, anchor='frame', decoder_graph=1, anchor_decode='cone', bencode_overlap=1,
              prep_ahead=1, server_identity_sha256='s', receipt_dir=str(TMP / 'receipts'),
              output_directory=str(TMP / 'output'), features=FEATURES, phase='stream', plan_sha256=m.PACKETS[124]['plan_sha256'])


def client():
    c = m.Client.__new__(m.Client)
    c.a = SimpleNamespace(packet=124, manifest_sha256='m', expect_frames=None, expect_placement=None,
                          expect_text_reuse=None, expect_anchor=None, expect_decoder_graph=None,
                          expect_anchor_decode=None, expect_bencode_overlap=None, expect_prep_ahead=None,
                          expect_snapshot_mode=None, expect_pool_cap_bytes=None, expect_pool_cap_gb=None,
                          expect_display_schedule=None, expect_anchor_read_ahead=None, expect_snapshot_schedule=None, expect_display_device=None)
    c.c = SimpleNamespace(FRAME_CHOICES=(49, 97, 121, 145, 169), PLACEMENTS=('two-way', 'two-way20-28'),
                          ANCHORS=('frame',), DECODER_GRAPH_CHOICES=(0, 1), SNAPSHOT_MODES=('walk', 'fingerprint'),
                          display_transient_bytes=lambda f: 13 * 2**29 if f == 169 else (4 * 2**30 * (((f - 1) // 8 + 1) ** 2) + 255) // 256,
                          check_levers=lambda *x: x, qualification_id=lambda *x, **kw: None,
                          residency_qualification_id=lambda qid, mode: 'residency-' + mode)
    c.bind_dirs = lambda st: None
    c.run_dir = TMP
    c.frames, c.placement, c.ident = 121, 'two-way20-28', 's'
    c.anchor, c.decoder_graph, c.levers = 'frame', 1, ('cone', 1, 1)
    c.server_options = OPTIONS.copy()
    c.verdict_sha = 'v'
    c.rc = SimpleNamespace(validate_receipt=lambda r: r)
    return c


for attr in ('DECODER_GRAPH_PACKETS', 'DECODE_THREAD_PACKETS', 'RESET_PACKETS', 'LEVER_PACKETS', 'SERVER_OPTION_PACKETS'):
    check('123 participates in ' + attr, 124 in getattr(m, attr))
check('numeric packet123 parser', m.packet_id('124') == 124)
check('123 stream directory accepted', m.STREAM_DIR_RE_124.fullmatch('stream124-s00000012') is not None)
check('118b stream directory refused', m.STREAM_DIR_RE_124.fullmatch('stream118b-s00000012') is None)
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
for packet in ('123', '118b', 118):
    st = copy.deepcopy(STATUS)
    st['packet'] = packet
    check('packet type/identity %r refuses' % packet, stopped(8, lambda: client().preflight(st)))
check('complete six-field options from status', client().status_server_options(STATUS) == OPTIONS)
c = client()
c.a.packet = '118b'
check('118b preserves its two-field options', c.status_server_options(STATUS) == {
    'snapshot_mode': 'fingerprint', 'decoder_graph_pool_cap_bytes': 10**9})

expect = {'run_name': 'stream124-s00000000', 'stream_seq': 0, 'predecessor': None}
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
         'plan_sha256': m.PACKETS[124]['plan_sha256'], 'server_options': OPTIONS.copy()}
    del v['server_options'][key]
    raw = json.dumps(v).encode()
    (TMP / 'stream-qualification-verdict.json').write_bytes(raw)
    st = dict(STATUS, qualification_verdict_sha256=hashlib.sha256(raw).hexdigest())
    check('verdict missing %s refused before gate' % key, stopped(13, lambda: c.verify_qualification(st)))

for key in OPTIONS:
    c = client()
    v = {'passed': True, 'failures': [], 'exact_replay': [{'all_identical': True}] * 3,
         'plan_sha256': m.PACKETS[124]['plan_sha256'], 'server_options': OPTIONS.copy()}
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
            ok = '--packet 119 or 120 or 121' in str(exc)
    check('new flag %s refused for118b' % flag, ok)

for value in (None, '', 'cpu', 'xpu:0', 2):
    st = dict(STATUS, display_device=value)
    check('invalid display device %r refused' % value, stopped(8, lambda: client().preflight(st)))
for key, value in (('frames', 97), ('anchor', 'latent'), ('anchor_decode', 'full'), ('display_schedule', 'sampler-a')):
    st = dict(STATUS, display_device='xpu:2', decoder_graph=0)
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
        client().validate_decode_identity({'display_device': actual, 'server_options': r['server_options']}, r)
        ok = True
    except ValueError:
        ok = False
    check('decode device binding %s/%s/%s' % (kind, configured, actual), ok == passes)
c = client()
c.a.packet = 119
check('119 option identity remains five fields', c.status_server_options(STATUS) ==
      {key: value for key, value in OPTIONS.items() if key not in ('display_device', 'aux_residency', 'residency_qualification_id', 'run_write_allowance_bytes', 'display_worker')})
check('119 decode records do not gain a required123 field', c.validate_decode_identity({}, {}) == {})
with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
    try:
        m.main(['--work-dir', str(TMP / 'args'), '--packet', '119', '--port', '18197', '--expect-display-device', 'xpu:2'])
        ok = False
    except SystemExit as exc:
        ok = '--packet 120 or 121' in str(exc)
check('119 refuses123 display device flag', ok)

# Audit events exercise the guard without calling open(), stat() or any device API.
for device_path in ('/dev/dri/renderD128', '/dev/dri', b'/dev/dri/card0'):
    try:
        sys.audit('open', device_path, 'r', 0)
        blocked = False
    except RuntimeError as exc:
        blocked = 'CPU suite refused device open' in str(exc)
    check('CPU runner blocks synthetic device-open audit %r' % device_path, blocked)

launcher = (HERE.parent / 'start-client-124.sh').read_text()
check('client wrapper uses fingerprint-pinned bin/python -B', '/bin/python -B ' in launcher and '/bin/python3' not in launcher)
check('client wrapper caps OMP', '--setenv=OMP_NUM_THREADS=4' in launcher)
check('client wrapper binds all three options', all(flag in launcher for flag in (
    '--expect-display-schedule', '--expect-anchor-read-ahead', '--expect-snapshot-schedule', '--expect-display-device')))
check('client wrapper workdir uses123 default', 'LTX_STREAM_WORKDIR:-/home/steve/ltx-stream/s124-live01' in launcher)
check('client wrapper does not reset units', 'reset-failed' not in launcher)
for frames in (121, 145):
    for device in ('xpu:3', 'xpu:2'):
        st = copy.deepcopy(STATUS)
        st.update(frames=frames, display_device=device)
        if frames >= 145 and device == 'xpu:2':
            st.update(decoder_graph=0, decoder_graph_pool_cap_bytes=None)
            st['features'].update(decoder_graph=False, decoder_graph_pool_cap=False)
        client().preflight(st)
        check('length %d display %s admitted' % (frames, device), True)
for feature in ('chunk_145',):
    st = copy.deepcopy(STATUS)
    del st['features'][feature]
    check('missing long-chunk feature %s refuses' % feature, stopped(8, lambda: client().preflight(st)))
for frames in (145,):
    for packet in ('117', '118b', '119', '120'):
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            try:
                m.main(['--work-dir', str(TMP / 'args'), '--packet', packet, '--port', '18198',
                        '--expect-frames', str(frames)])
                ok = False
            except SystemExit as exc:
                ok = '--expect-frames 145 needs --packet 121 or 122' in str(exc)
        check('old packet %s refuses frames%d before network' % (packet, frames), ok)
c = client()
c.a.packet = 120
st = dict(STATUS, packet=120, frames=145, display_device='xpu:2', plan_sha256=m.PACKETS[120]['plan_sha256'])
check('packet120 still refuses long replica configuration', stopped(8, lambda: c.preflight(st)))
# The override is optional in123; historical identities and defaults omit it.
budget_key = 'display_replica_transient_budget_bytes'
for frames, gib in ((121, 4), (145, 6), (145, 8)):
    c = client()
    c.a.expect_display_transient_bytes = gib * 2**30
    st = copy.deepcopy(STATUS)
    st.update(frames=frames, display_device='xpu:2', **{budget_key: gib * 2**30})
    if frames >= 145:
        st.update(decoder_graph=0, decoder_graph_pool_cap_bytes=None)
        st['features'].update(decoder_graph=False, decoder_graph_pool_cap=False)
    c.preflight(st)
    check('explicit budget %s GiB at%d accepts and binds' % (gib, frames),
          c.status_server_options(st)[budget_key] == gib * 2**30)
for budget in (None, True, '6442450944', 4 * 2**30, 8 * 2**30 + 1):
    c = client()
    c.a.expect_display_transient_bytes = budget
    st = dict(STATUS, frames=145, display_device='xpu:2', **{budget_key: budget})
    check('invalid145 transient budget %r refuses' % budget, stopped(8, lambda: c.preflight(st)))
c = client()
c.a.expect_display_transient_bytes = 6 * 2**30
st = dict(STATUS, frames=145, **{budget_key: 6 * 2**30})
check('explicit budget on xpu3 refuses', stopped(8, lambda: c.preflight(st)))
st['display_device'] = 'xpu:2'
check('unrequested override refuses', stopped(8, lambda: client().preflight(st)))
st[budget_key] = 7 * 2**30
check('override expectation mismatch refuses', stopped(8, lambda: c.preflight(st)))
check('required override absent refuses', stopped(8, lambda: c.preflight(STATUS)))
check('default options omit budget field', budget_key not in client().status_server_options(STATUS))
for packet in (120, 121):
    c = client()
    c.a.packet = packet
    check('historical%d options ignore new field' % packet, budget_key not in c.status_server_options(st))
for value in ('NaN', 'Infinity', '-1', '0', '9', '0.00000000001'):
    with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
        try:
            m.main(['--work-dir', str(TMP / 'args'), '--packet', '124', '--port', '18199',
                    '--expect-display-transient-gib', value])
            ok = False
        except SystemExit as exc:
            ok = '--expect-display-transient-gib must be finite' in str(exc)
    check('CLI invalid transient budget %s refuses before network' % value, ok)
with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
    try:
        m.main(['--work-dir', str(TMP / 'args'), '--packet', '121', '--port', '18199',
                '--expect-display-transient-gib', '6'])
        ok = False
    except SystemExit as exc:
        ok = '--expect-display-transient-gib needs --packet 122' in str(exc)
check('old packet refuses explicit transient flag before network', ok)
check('wrapper binds explicit transient environment option',
      'LTX_DISPLAY_REPLICA_TRANSIENT_GIB' in launcher and '--expect-display-transient-gib' in launcher)
r = copy.deepcopy(receipt)
c = client()
c.server_options[budget_key] = 6 * 2**30
r['server_options'][budget_key] = 6 * 2**30
check('receipt explicit budget agrees', c.verify_receipt(json.dumps(r).encode(), None, expect) == r)
r['server_options'][budget_key] += 1
check('receipt budget drift refuses', stopped(12, lambda: c.verify_receipt(json.dumps(r).encode(), None, expect)))
del r['server_options'][budget_key]
check('receipt budget missing refuses', stopped(12, lambda: c.verify_receipt(json.dumps(r).encode(), None, expect)))


# Residency binding and169 admission are independent of the existing numerical QID.
for mode in ('legacy', 'xpu2'):
    st = copy.deepcopy(STATUS)
    st.update(aux_residency=mode, residency_qualification_id='residency-' + mode)
    if mode == 'xpu2':
        st.update(frames=145, decoder_graph=0, decoder_graph_pool_cap_bytes=None)
        st['features'].update(decoder_graph=False, decoder_graph_pool_cap=False)
    client().preflight(st)
    check('auxiliary residency %s accepts its identity' % mode, True)
    st['residency_qualification_id'] = 'wrong'
    check('auxiliary residency %s rejects drifted identity' % mode,
          stopped(8, lambda: client().preflight(st)))
for mode in (None, '', 'cpu', 'xpu:2', 1):
    st = dict(STATUS, aux_residency=mode)
    check('invalid auxiliary residency %r refuses' % mode, stopped(8, lambda: client().preflight(st)))
st = copy.deepcopy(STATUS)
st.update(frames=169, decoder_graph=0, decoder_graph_pool_cap_bytes=None,
          aux_residency='xpu2', residency_qualification_id='residency-xpu2')
st['features'].update(decoder_graph=False, decoder_graph_pool_cap=False)
client().preflight(st)
check('169 xpu2 dg0 accepts', True)
for key, value in (('aux_residency', 'legacy'), ('decoder_graph', 1), ('placement', 'two-way'),
                   ('anchor', 'latent'), ('anchor_decode', 'full'), ('display_device', 'xpu:2')):
    bad169 = copy.deepcopy(st)
    bad169[key] = value
    check('169 refuses unsafe %s' % key, stopped(8, lambda: client().preflight(bad169)))
for feature in ('chunk_169', 'atomic_preview'):
    bad169 = copy.deepcopy(st)
    bad169['features'].pop(feature)
    check('123 refuses missing %s feature' % feature, stopped(8, lambda: client().preflight(bad169)))
for frames in (145, 169):
    st = dict(STATUS, frames=frames, display_device='xpu:2')
    check('long dg1 replica f%d refuses' % frames, stopped(8, lambda: client().preflight(st)))
c = client()
c.a.expect_aux_residency = 'xpu2'
check('expected auxiliary residency mismatch refuses', stopped(8, lambda: c.preflight(STATUS)))
check('client wrapper binds residency environment', 'LTX_AUX_RESIDENCY:-legacy' in launcher
      and '--expect-aux-residency' in launcher)

# Exit7 diagnostic never retries the preview, restarts anything, or masks the failure.
for label, response, error in (
    ('healthy', (200, {'phase': 'stream', 'halted': None, 'fault': None,
                      'decode_worker': {'completed': 165}, 'preview_writer': {'failed': None}}), None),
    ('fault', (200, {'phase': 'stream', 'halted': 'device fault', 'fault': {'message': 'fault'}}), None),
    ('unavailable', None, TimeoutError('bounded status timeout')),
    ('status500', (500, {'error': 'status route failed'}), None),
):
    c = client()
    calls = []
    def raw(method, path, timeout):
        calls.append((method, path, timeout))
        if error is not None:
            raise error
        return response[0], json.dumps(response[1]).encode()
    c.api = SimpleNamespace(_raw=raw, parse=m.Api.parse)
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        snapshot = c.failure_status_snapshot()
    check('exit7 %s makes exactly one bounded status observation' % label,
          calls == [('GET', '/ltx-stream/status', 2.0)] and snapshot['request_count'] == 1)
    check('exit7 %s is logged' % label, 'exit-7 server status' in stdout.getvalue())
    if label in ('healthy', 'fault'):
        check('exit7 %s preserves fault and health evidence' % label,
              snapshot['available'] and snapshot['status']['halted'] == response[1]['halted']
              and snapshot['status']['fault'] == response[1]['fault'])
    else:
        check('exit7 %s records unavailable without throwing' % label, not snapshot['available'])

# Actual sealed dependency closure and reference pins: CPU imports/read-only only.
sealed = m.PACKETS[124]
modules = m.load_contract_modules(sealed['dir'] / 'resolution/components', module_sha=sealed['modules'])
check('sealed123 imports hash-pinned residency helper before receipt and gate modules',
      modules[0].PACKET == 124 and Path(sys.modules['residency123'].__file__) ==
      sealed['dir'] / 'resolution/components/residency123.py')
c = client()
c.a.reference_hashes = None
reference = c.reference_hashes()
check('sealed123 reference pin verifies and includes145 legacy qualification',
      '145/two-way20-28/frame' in reference['variants'])
bad_pins = dict(sealed['modules'], residency123='0' * 64)
check('changed residency helper pin refuses before import', stopped(8, lambda: m.load_contract_modules(
      sealed['dir'] / 'resolution/components', module_sha=bad_pins)))

# The default expectation is 3 GiB; an explicit larger launch requires a match.
for gib in (1, 3, 8, 64):
    c = client()
    c.a.expect_run_write_allowance_bytes = gib * 2**30
    st = dict(STATUS, run_write_allowance_bytes=gib * 2**30)
    c.preflight(st)
    check('allowance %d GiB accepts and binds' % gib, c.status_server_options(st)['run_write_allowance_bytes'] == gib * 2**30)
for value in (None, True, '3221225472', 0, 2**30+1, 65*2**30, 8*2**30):
    st = dict(STATUS, run_write_allowance_bytes=value)
    check('invalid or unrequested allowance %r refuses' % value, stopped(8, lambda: client().preflight(st)))
for value in ('', '0', '65', '3.0', '-1', '03', ' 3', '+3'):
    with contextlib.redirect_stderr(io.StringIO()):
        try:
            m.main(['--work-dir', str(TMP / 'args'), '--packet', '124', '--port', '18205', '--expect-run-write-allowance-gib', value])
            ok = False
        except SystemExit as exc:
            ok = exc.code == 2
    check('invalid allowance CLI %r refuses before network' % value, ok)
r = copy.deepcopy(receipt)
r['server_options']['run_write_allowance_bytes'] = 4*2**30
check('receipt allowance drift refuses exit12', stopped(12, lambda: client().verify_receipt(json.dumps(r).encode(), None, expect)))
del r['server_options']['run_write_allowance_bytes']
check('missing receipt allowance refuses exit12', stopped(12, lambda: client().verify_receipt(json.dumps(r).encode(), None, expect)))
check('client launcher binds write allowance', '--expect-run-write-allowance-gib "$WA"' in launcher)

# Packet124 parallel display only runs on the admitted long eager replica path.
for frames in (145, 169):
    for worker in ('serial', 'parallel'):
        st = copy.deepcopy(STATUS)
        st.update(frames=frames, decoder_graph=0, decoder_graph_pool_cap_bytes=None,
                  display_device='xpu:2', display_worker=worker)
        st['features'].update(decoder_graph=False, decoder_graph_pool_cap=False)
        c = client()
        c.a.expect_display_worker = worker
        c.preflight(st)
        check('124 f%d legacy replica %s admitted' % (frames, worker),
              c.status_server_options(st)['display_worker'] == worker)
        wrong = copy.deepcopy(st)
        wrong['display_worker'] = 'parallel' if worker == 'serial' else 'serial'
        check('worker expectation mismatch rejects', stopped(8, lambda: c.preflight(wrong)))
        if worker == 'parallel':
            for key, value in (('frames', 121), ('display_device', 'xpu:3'), ('aux_residency', 'xpu2'),
                               ('decoder_graph', 1), ('placement', 'two-way'), ('anchor', 'latent'),
                               ('anchor_decode', 'full'), ('display_schedule', 'sampler-a')):
                bad = copy.deepcopy(st)
                bad[key] = value
                check('parallel refuses %s=%s' % (key, value), stopped(8, lambda: c.preflight(bad)))
for value in (None, '', 1, True, 'other'):
    st = dict(STATUS, display_worker=value)
    check('invalid worker %r refuses' % value, stopped(8, lambda: client().preflight(st)))
for packet in (123, '123b'):
    c = client()
    c.a.packet = packet
    check('historical packet%s keeps worker absent' % packet, 'display_worker' not in c.status_server_options(STATUS))
with contextlib.redirect_stderr(io.StringIO()):
    try:
        m.main(['--work-dir', str(TMP / 'args'), '--packet', '123b', '--port', '18219',
                '--expect-display-worker', 'parallel'])
        ok = False
    except SystemExit as exc:
        ok = exc.code == 2
check('historical packet refuses124 worker option before network', ok)
check('wrapper binds worker environment option', 'LTX_DISPLAY_WORKER:-serial' in launcher
      and '--expect-display-worker "$DW"' in launcher)

# Read every sealed packet with a plan pin; never confuse its JSON file hash
# with the canonical inner identity that the actual server advertises.
for packet, sealed in m.PACKETS.items():
    if 'plan_sha256' not in sealed:
        continue
    raw = (sealed['dir'] / 'resolution/stream-plan.json').read_bytes()
    plan = json.loads(raw)
    check('packet%s pin equals sealed inner plan_sha256' % packet,
          sealed['plan_sha256'] == plan['plan_sha256'])
    check('packet%s pin does not equal plan file byte hash' % packet,
          sealed['plan_sha256'] != hashlib.sha256(raw).hexdigest())
st = dict(STATUS, plan_sha256=hashlib.sha256(
    (m.PACKETS[124]['dir'] / 'resolution/stream-plan.json').read_bytes()).hexdigest())
check('server file-byte plan hash refuses instead of inner plan', stopped(8, lambda: client().preflight(st)))

bad = [name for name, ok in RESULTS if not ok]
print('\n%d/%d passed; CPU-only files in %s' % (len(RESULTS)-len(bad), len(RESULTS), TMP))
raise SystemExit(1 if bad else 0)
