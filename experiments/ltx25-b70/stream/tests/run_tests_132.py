#!/home/steve/.venvs/ltx25-baseline/bin/python -B
"""CPU-only packet132 client contract tests; no server, sockets, signals or GPU imports.

Run with bin/python -B tests/run_cpu_suites.py run_tests_132.py. Synthetic evidence
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
spec = importlib.util.spec_from_file_location('client132_test', HERE.parent / 'ltx_continuation_client.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
m.load_contract_modules(m.PACKETS[132]['dir'] / 'resolution/components', module_sha=m.PACKETS[132]['modules'])
TMP = Path(tempfile.mkdtemp(prefix='ltx-client132-cpu-'))
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


OPTIONS = {'audio_residency': 'legacy', 'cone_capture_reserve': 'parent', 'cone_graph_memory': 'off', 'display_allocator_release': 'off', 'maintenance_mode': 'parent', 'snapshot_digest_cache': 0, 'storage_scan_mode': 'request', 'gc_interval_seconds': 10, 'display_worker': 'serial', 'run_write_allowance_bytes': 3 * 2**30, 'snapshot_mode': 'fingerprint', 'decoder_graph_pool_cap_bytes': 10**9, 'aux_residency': 'legacy', 'residency_qualification_id': 'residency-legacy',
           'display_schedule': 'eager-display', 'anchor_read_ahead': 0, 'snapshot_schedule': 'full', 'display_device': 'xpu:3'}
FEATURES = {k: True for k in ('decode_thread', 'async_preview', 'chain_reset', 'chunk_length_choice',
                            'sharpness_diagnostic', 'video_first_handoff', 'frame_anchor', 'decoder_graph',
                            'cone_anchor_decode', 'bencode_overlap', 'prep_ahead', 'chunk_121', 'chunk_145', 'timing_split',
                            'snapshot_fingerprint', 'decoder_graph_pool_cap')}
FEATURES.update(audio_residency=True, cone_capture_reserve=True, cone_graph_memory=True, chunk_169=True, atomic_preview=True, atomic_evidence_publication=True)
FEATURES.update({k + '_anchor': False for k in ('mixed', 'latent', 'guide')})
STATUS = dict(OPTIONS, packet=132, runtime_manifest_sha256='m', frames=121, placement='two-way20-28',
              text_reuse=1, anchor='frame', decoder_graph=1, anchor_decode='cone', bencode_overlap=1,
              prep_ahead=1, server_identity_sha256='s', receipt_dir=str(TMP / 'receipts'),
              output_directory=str(TMP / 'output'), features=FEATURES, phase='stream', plan_sha256=m.PACKETS[132]['plan_sha256'])


def client():
    c = m.Client.__new__(m.Client)
    c.a = SimpleNamespace(packet=132, expect_audio_residency='legacy', expect_cone_capture_reserve='parent', expect_cone_graph_memory='off', manifest_sha256='m', expect_frames=None, expect_placement=None,
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
    check('123 participates in ' + attr, 132 in getattr(m, attr))
check('numeric packet123 parser', m.packet_id('132') == 132)
check('123 stream directory accepted', m.STREAM_DIR_RE_132.fullmatch('stream132-s00000012') is not None)
check('118b stream directory refused', m.STREAM_DIR_RE_132.fullmatch('stream118b-s00000012') is None)
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

expect = {'run_name': 'stream132-s00000000', 'stream_seq': 0, 'predecessor': None}
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
         'plan_sha256': m.PACKETS[132]['plan_sha256'], 'server_options': OPTIONS.copy()}
    del v['server_options'][key]
    raw = json.dumps(v).encode()
    (TMP / 'stream-qualification-verdict.json').write_bytes(raw)
    st = dict(STATUS, qualification_verdict_sha256=hashlib.sha256(raw).hexdigest())
    check('verdict missing %s refused before gate' % key, stopped(13, lambda: c.verify_qualification(st)))

for key in OPTIONS:
    c = client()
    v = {'passed': True, 'failures': [], 'exact_replay': [{'all_identical': True}] * 3,
         'plan_sha256': m.PACKETS[132]['plan_sha256'], 'server_options': OPTIONS.copy()}
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
      {key: value for key, value in OPTIONS.items() if key not in ('display_device', 'aux_residency', 'residency_qualification_id', 'run_write_allowance_bytes', 'display_worker', 'gc_interval_seconds', 'storage_scan_mode', 'snapshot_digest_cache', 'maintenance_mode', 'display_allocator_release', 'cone_graph_memory', 'audio_residency', 'cone_capture_reserve')})
check('119 decode records do not gain a required123 field', c.validate_decode_identity({}, {}) == {})
with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
    try:
        m.main(['--work-dir', str(TMP / 'args'), '--packet', '119', '--port', '18197', '--expect-display-device', 'xpu:2'])
        ok = False
    except SystemExit as exc:
        ok = '--packet 120 or 121' in str(exc)
check('119 refuses123 display device flag', ok)

# Audit events exercise the guard without calling open(), stat() or any device API.
for device_path in ('/dev/dri/renderD132', '/dev/dri', b'/dev/dri/card0'):
    try:
        sys.audit('open', device_path, 'r', 0)
        blocked = False
    except RuntimeError as exc:
        blocked = 'CPU suite refused device open' in str(exc)
    check('CPU runner blocks synthetic device-open audit %r' % device_path, blocked)

launcher = (HERE.parent / 'start-client-132.sh').read_text()
check('client wrapper uses fingerprint-pinned bin/python -B', '/bin/python -B ' in launcher and '/bin/python3' not in launcher)
check('client wrapper caps OMP', '--setenv=OMP_NUM_THREADS=2' in launcher)
check('client wrapper binds all three options', all(flag in launcher for flag in (
    '--expect-display-schedule', '--expect-anchor-read-ahead', '--expect-snapshot-schedule', '--expect-display-device')))
check('client wrapper workdir uses123 default', 'LTX_STREAM_WORKDIR:-/home/steve/ltx-stream/s132-live01' in launcher)
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
            m.main(['--work-dir', str(TMP / 'args'), '--packet', '132', '--expected-cone-graph-memory', 'off', '--port', '18199',
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
sealed = m.PACKETS[132]
modules = m.load_contract_modules(sealed['dir'] / 'resolution/components', module_sha=sealed['modules'])
check('132 sealed comparison identity is new', modules[0].COMPARISON_MODE == 'stream-candidate-132-v1')
check('132 sealed qualification clip base is new', modules[0].QUALIFICATION_CLIP_BASE == 13200000)
check('132 sealed stream clip base is new', modules[0].STREAM_CLIP_BASE == 13201000)
check('sealed123 imports hash-pinned residency helper before receipt and gate modules',
      modules[0].PACKET == 132 and Path(sys.modules['residency123'].__file__) ==
      sealed['dir'] / 'resolution/components/residency123.py')
c = client()
c.a.reference_hashes = None
reference = c.reference_hashes()
check('sealed123 reference pin verifies and includes145 legacy qualification',
      '145/two-way20-28/frame' in reference['variants'])
bad_pins = dict(sealed['modules'], residency123='0' * 64)
check('changed residency helper pin refuses before import', stopped(8, lambda: m.load_contract_modules(
      sealed['dir'] / 'resolution/components', module_sha=bad_pins)))

check('132 hash-pinned publication helper loaded from sealed packet',
      Path(sys.modules['evidence_publication'].__file__) ==
      sealed['dir'] / 'resolution/components/evidence_publication.py')
bad_pins = dict(sealed['modules'], evidence_publication='0' * 64)
check('changed publication helper pin refuses before import', stopped(8, lambda: m.load_contract_modules(
      sealed['dir'] / 'resolution/components', module_sha=bad_pins)))

check('132 hash-pinned allocator helper loaded from sealed packet',
      Path(sys.modules['allocator_release130'].__file__) ==
      sealed['dir'] / 'resolution/components/allocator_release130.py')
bad_pins = dict(sealed['modules'], allocator_release130='0' * 64)
check('changed allocator helper pin refuses before import', stopped(8, lambda: m.load_contract_modules(
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
            m.main(['--work-dir', str(TMP / 'args'), '--packet', '132', '--expected-cone-graph-memory', 'off', '--port', '18205', '--expect-run-write-allowance-gib', value])
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

# Packet132 parallel display only runs on the admitted long eager replica path.
for frames in (145, 169):
    for worker in ('serial', 'parallel'):
        st = copy.deepcopy(STATUS)
        st.update(frames=frames, decoder_graph=0, decoder_graph_pool_cap_bytes=None,
                  display_device='xpu:2', display_worker=worker)
        st['features'].update(decoder_graph=False, decoder_graph_pool_cap=False)
        c = client()
        c.a.expect_display_worker = worker
        c.preflight(st)
        check('132 f%d legacy replica %s admitted' % (frames, worker),
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
check('historical packet refuses126 worker option before network', ok)
check('wrapper binds worker environment option', 'LTX_DISPLAY_WORKER:-serial' in launcher
      and '--expect-display-worker "$DW"' in launcher)

# Packet132 admission is narrow;10 retains the parent's application cadence.
for aux in ('legacy', 'xpu2'):
    for interval in (10, 60):
        st = copy.deepcopy(STATUS)
        st.update(frames=145, decoder_graph=0, decoder_graph_pool_cap_bytes=None,
                  display_schedule='sampler-a', gc_interval_seconds=interval,
                  aux_residency=aux, residency_qualification_id='residency-' + aux)
        st['features'].update(decoder_graph=False, decoder_graph_pool_cap=False)
        c = client()
        c.a.expect_gc_interval_seconds = interval
        c.preflight(st)
        check('132 %s/%ss maintenance admitted and bound' % (aux, interval),
              c.status_server_options(st)['gc_interval_seconds'] == interval)
        other = dict(st, gc_interval_seconds=10 if interval == 60 else 60)
        check('maintenance expectation mismatch refuses', stopped(8, lambda: c.preflight(other)))
        if interval == 60:
            for key, value in (('frames', 121), ('frames', 169), ('placement', 'two-way'),
                               ('anchor', 'latent'), ('decoder_graph', 1), ('anchor_decode', 'full'),
                               ('prep_ahead', 0), ('bencode_overlap', 0), ('display_worker', 'parallel'),
                               ('display_device', 'xpu:2'), ('display_schedule', 'sampler-b'),
                               ('display_schedule', 'eager-display'), ('anchor_read_ahead', 1),
                               ('snapshot_schedule', 'a-xpu3-sync')):
                bad_interval = dict(st, **{key: value})
                check('60-second maintenance refuses %s=%r' % (key, value),
                      stopped(8, lambda: c.preflight(bad_interval)))
for interval in (None, '', '60', 1, True, 10.0, 60.0, 0, 30, 600):
    check('invalid gc_interval_seconds %r refuses' % interval,
          stopped(8, lambda: client().preflight(dict(STATUS, gc_interval_seconds=interval))))
for packet in (123, '123b', 124):
    c = client()
    c.a.packet = packet
    check('historical packet%s keeps maintenance option absent' % packet,
          'gc_interval_seconds' not in c.status_server_options(STATUS))
    with contextlib.redirect_stderr(io.StringIO()):
        try:
            m.main(['--work-dir', str(TMP / 'args'), '--packet', str(packet), '--port', '18229',
                    '--expect-gc-interval-seconds', '60'])
            ok = False
        except SystemExit as exc:
            ok = exc.code == 2
    check('historical packet%s refuses maintenance option before network' % packet, ok)
check('wrapper binds maintenance environment option', 'LTX_GC_INTERVAL_SECONDS:-10' in launcher
      and '--expect-gc-interval-seconds "$GC"' in launcher)

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
    (m.PACKETS[132]['dir'] / 'resolution/stream-plan.json').read_bytes()).hexdigest())
check('server file-byte plan hash refuses instead of inner plan', stopped(8, lambda: client().preflight(st)))

for mode in ('request', 'background'):
    c = client()
    c.a.expect_storage_scan_mode = mode
    st = dict(STATUS, storage_scan_mode=mode)
    c.preflight(st)
    check('storage mode accepts matching ' + mode, c.status_server_options(st)['storage_scan_mode'] == mode)
    c.a.expect_storage_scan_mode = 'background' if mode == 'request' else 'request'
    check('storage mode rejects mismatched ' + mode, stopped(8, lambda: c.preflight(st)))
for mode in (None, '', 'walk', True):
    check('invalid storage mode %r refused' % mode,
          stopped(8, lambda: client().preflight(dict(STATUS, storage_scan_mode=mode))))

# Packet132 caches only derived digests; option is bound throughout the protocol.
cache_status = dict(STATUS, frames=145, decoder_graph=0, decoder_graph_pool_cap_bytes=None,
                    snapshot_digest_cache=1, display_schedule='sampler-a',
                    features=dict(FEATURES, decoder_graph=False, decoder_graph_pool_cap=False))
for interval in (10, 60):
    c = client()
    c.a.expect_snapshot_digest_cache = 1
    c.a.expect_gc_interval_seconds = interval
    st = dict(cache_status, gc_interval_seconds=interval)
    c.preflight(st)
    check('cache1 admitted with GC%d and option bound' % interval,
          c.status_server_options(st)['snapshot_digest_cache'] == 1)
    c.a.expect_snapshot_digest_cache = 0
    check('cache1 rejects parent expectation GC%d' % interval,
          stopped(8, lambda: c.preflight(st)))
for key, value in (('frames', 121), ('frames', 169), ('placement', 'two-way'), ('anchor', 'mixed'),
                   ('decoder_graph', 1), ('anchor_decode', 'full'), ('prep_ahead', 0),
                   ('bencode_overlap', 0), ('display_worker', 'parallel'), ('display_device', 'xpu:2'),
                   ('display_schedule', 'eager-display'), ('anchor_read_ahead', 1),
                   ('snapshot_schedule', 'a-xpu3-sync'), ('snapshot_mode', 'walk'), ('aux_residency', 'xpu2')):
    c = client()
    c.a.expect_snapshot_digest_cache = 1
    check('cache1 refuses changed scope %s=%r' % (key, value),
          stopped(8, lambda: c.preflight(dict(cache_status, **{key: value}))))
for value in (None, '', '1', True, False, 1.0, -1, 2):
    check('cache rejects non-integer option %r' % value,
          stopped(8, lambda: client().preflight(dict(STATUS, snapshot_digest_cache=value))))
for packet in (125, 126):
    c = client()
    c.a.packet = packet
    check('historical packet%d excludes new cache option' % packet,
          'snapshot_digest_cache' not in c.status_server_options(STATUS))
    with contextlib.redirect_stderr(io.StringIO()):
        try:
            m.main(['--work-dir', str(TMP / 'args'), '--packet', str(packet), '--port', '18229',
                    '--expect-snapshot-digest-cache', '1'])
            ok = False
        except SystemExit as exc:
            ok = exc.code == 2
    check('historical packet%d refuses cache option before network' % packet, ok)
check('wrapper binds snapshot digest cache option', 'LTX_SNAPSHOT_DIGEST_CACHE:-0' in launcher
      and '--expect-snapshot-digest-cache "$CACHE"' in launcher)

# Packet132 mode is explicit and bound on every protocol record.
idle_status = dict(STATUS, frames=145, decoder_graph=0, decoder_graph_pool_cap_bytes=None,
                   display_schedule='sampler-a', maintenance_mode='idle',
                   features=dict(FEATURES, decoder_graph=False, decoder_graph_pool_cap=False))
for frames, worker, display, schedule in ((145, 'serial', 'xpu:3', 'sampler-a'),
                                         (145, 'parallel', 'xpu:2', 'eager-display'),
                                         (169, 'parallel', 'xpu:2', 'eager-display')):
    c = client()
    c.a.expect_maintenance_mode = 'idle'
    st = dict(idle_status, frames=frames, display_worker=worker,
              display_device=display, display_schedule=schedule)
    c.preflight(st)
    check('idle mode admits inherited safe %d/%s' % (frames, worker),
          c.status_server_options(st)['maintenance_mode'] == 'idle')
    c.a.expect_maintenance_mode = 'parent'
    check('idle mode refuses parent expectation %d/%s' % (frames, worker),
          stopped(8, lambda: c.preflight(st)))
    if frames == 169:
        c.a.expect_maintenance_mode = 'idle'
        for key, value in (('snapshot_digest_cache', 1), ('gc_interval_seconds', 60)):
            setattr(c.a, 'expect_' + key, value)
            check('169 idle preserves inherited refusal ' + key,
                  stopped(8, lambda: c.preflight(dict(st, **{key: value}))))
            setattr(c.a, 'expect_' + key, 0 if key == 'snapshot_digest_cache' else 10)
for key, value in (('frames', 121), ('placement', 'two-way'), ('anchor', 'mixed'),
                   ('decoder_graph', 1), ('anchor_decode', 'full'), ('prep_ahead', 0),
                   ('bencode_overlap', 0), ('display_schedule', 'sampler-b'),
                   ('anchor_read_ahead', 1), ('snapshot_schedule', 'a-xpu3-sync'),
                   ('snapshot_mode', 'walk'), ('aux_residency', 'xpu2')):
    c = client()
    c.a.expect_maintenance_mode = 'idle'
    check('idle refuses changed scope %s=%r' % (key, value),
          stopped(8, lambda: c.preflight(dict(idle_status, **{key: value}))))
for value in (None, '', 'thread', True, 0):
    check('maintenance rejects invalid mode %r' % value,
          stopped(8, lambda: client().preflight(dict(STATUS, maintenance_mode=value))))
for packet in (125, 126, 127):
    c = client()
    c.a.packet = packet
    check('historical packet%d excludes132 maintenance option' % packet,
          'maintenance_mode' not in c.status_server_options(STATUS))
    with contextlib.redirect_stderr(io.StringIO()):
        try:
            m.main(['--work-dir', str(TMP / 'args'), '--packet', str(packet), '--port', '18229',
                    '--expect-maintenance-mode', 'idle'])
            ok = False
        except SystemExit as exc:
            ok = exc.code == 2
    check('historical packet%d refuses132 option before network' % packet, ok)
for value in ('bad', '0', 'IDLE', ''):
    with contextlib.redirect_stderr(io.StringIO()):
        try:
            m.main(['--work-dir', str(TMP / 'args'), '--packet', '132', '--expected-cone-graph-memory', 'off', '--port', '18229',
                    '--expect-maintenance-mode', value])
            ok = False
        except SystemExit as exc:
            ok = exc.code == 2
    check('invalid maintenance CLI %r refuses before network' % value, ok)
c = client()
c.a.packet = 127
check('off132 options equal127 plus explicit parent identity',
      client().status_server_options(STATUS) == dict(c.status_server_options(STATUS), maintenance_mode='parent', display_allocator_release='off', cone_graph_memory='off', audio_residency='legacy', cone_capture_reserve='parent'))
r = copy.deepcopy(receipt)
r['server_options']['maintenance_mode'] = 'idle'
check('receipt maintenance drift rejected',
      stopped(12, lambda: client().verify_receipt(json.dumps(r).encode(), None, expect)))
for value in (None, 'idle'):
    record = dict(display_device='xpu:3', server_options=dict(OPTIONS))
    if value is None:
        del record['server_options']['maintenance_mode']
    else:
        record['server_options']['maintenance_mode'] = value
    try:
        client().validate_decode_identity(record, receipt)
        ok = False
    except ValueError:
        ok = True
    check('decode maintenance missing/drift %r rejected' % value, ok)
for value in (None, 'idle'):
    c = client()
    c.output_dir = TMP / 'output'
    c.a.save_wait = 1
    c.check_fault_files = lambda name: None
    c.rc.validate_preview_record = lambda record, receipt: record
    record = dict(server_options=dict(OPTIONS))
    if value is None:
        del record['server_options']['maintenance_mode']
    else:
        record['server_options']['maintenance_mode'] = value
    c.api = SimpleNamespace(get=lambda route: (200, json.dumps(record).encode()))
    r = dict(receipt, preview={'path': str(c.output_dir / receipt['run_name'] / 'preview_00001_.mp4')})
    try:
        c.wait_preview(r)
        ok = False
    except m.Stop as exc:
        ok = exc.code == 7 and 'server_options differ' in str(exc)
    check('preview maintenance missing/drift %r rejected' % value, ok)
check('wrapper binds maintenance mode with parent default', 'LTX_MAINTENANCE_MODE:-parent' in launcher
      and '--expect-maintenance-mode "$MAINT"' in launcher)

# Packet132's writer protocol is mandatory and has no separate launch option.
for value in (None, False, 0, 1, 'true'):
    st = copy.deepcopy(STATUS)
    if value is None:
        st['features'].pop('atomic_evidence_publication')
    else:
        st['features']['atomic_evidence_publication'] = value
    check('atomic publication feature invalid %r refused' % value,
          stopped(8, lambda: client().preflight(st)))
c = client()
c.a.packet = 129
check('132 off server options add only release identity to129',
      client().status_server_options(STATUS) == dict(c.status_server_options(STATUS), display_allocator_release='off', cone_graph_memory='off', audio_residency='legacy', cone_capture_reserve='parent'))
check('132 wrapper exposes no publication toggle', 'ATOMIC_EVIDENCE' not in launcher)


# Every byte-bound record carries the allocation policy, including its off form.
st = copy.deepcopy(STATUS)
st.update(frames=169, decoder_graph=0, decoder_graph_pool_cap_bytes=None,
          display_worker='parallel', display_device='xpu:2', display_allocator_release='before-admission')
st['features'].update(decoder_graph=False, decoder_graph_pool_cap=False)
c = client()
c.a.expect_display_allocator_release = 'before-admission'
c.preflight(st)
check('169 release admits only explicitly matching expectation',
      c.status_server_options(st)['display_allocator_release'] == 'before-admission')
check('unrequested release refuses', stopped(8, lambda: client().preflight(st)))
check('requested release absent refuses', stopped(8, lambda: c.preflight(STATUS)))
for budget, allowed in ((13 * 2**29, True), (6 * 2**30, False)):
    reserve_status = copy.deepcopy(st)
    reserve_status['display_replica_transient_budget_bytes'] = budget
    c.a.expect_display_transient_bytes = budget
    if allowed:
        c.preflight(reserve_status)
        ok = c.status_server_options(reserve_status)['display_replica_transient_budget_bytes'] == budget
    else:
        ok = stopped(8, lambda: c.preflight(reserve_status))
    check('allocator release keeps6.5GiB transient minimum at %r' % budget, ok)
c.a.expect_display_transient_bytes = None
for key, value in (('frames',145), ('placement','two-way'), ('anchor','latent'), ('decoder_graph',1),
                   ('anchor_decode','full'), ('bencode_overlap',0), ('prep_ahead',0),
                   ('snapshot_mode','walk'), ('snapshot_schedule','a-xpu3-sync'),
                   ('anchor_read_ahead',1), ('aux_residency','xpu2'), ('display_worker','serial'),
                   ('display_device','xpu:3'), ('display_schedule','sampler-a')):
    drift=copy.deepcopy(st)
    drift[key]=value
    check('release scope refuses %s=%r' % (key,value), stopped(8, lambda: c.preflight(drift)))
for value in (None, '', True, 0, 'on', 'before'):
    drift=copy.deepcopy(STATUS)
    drift['display_allocator_release']=value
    check('invalid release %r refuses' % value, stopped(8, lambda: client().preflight(drift)))
for packet in (112, 120, 128, 129):
    c=client()
    c.a.packet=packet
    check('historical packet%d release identity remains absent' % packet,
          'display_allocator_release' not in c.status_server_options(STATUS))
    with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
        try:
            m.main(['--work-dir',str(TMP/'args'),'--packet',str(packet),'--port','18231',
                    '--expect-display-allocator-release','off'])
            ok=False
        except SystemExit as exc:
            ok=exc.code == 2
    check('historical packet%d refuses release CLI before network' % packet,ok)
for value in (None,'before-admission'):
    r=copy.deepcopy(receipt)
    if value is None: del r['server_options']['display_allocator_release']
    else: r['server_options']['display_allocator_release']=value
    check('receipt release missing/drift %r refuses' % value,
          stopped(12,lambda:client().verify_receipt(json.dumps(r).encode(),None,expect)))
    record=dict(display_device='xpu:3',server_options=r['server_options'])
    try:
        client().validate_decode_identity(record,receipt)
        ok=False
    except ValueError: ok=True
    check('decode release missing/drift %r refuses' % value,ok)
check('132 wrapper binds off-default allocator release',
      'LTX_DISPLAY_ALLOCATOR_RELEASE:-off' in launcher and '--expect-display-allocator-release "$RELEASE"' in launcher)

# Packet132 new option and exact narrow graph/replica admission.
candidate = dict(STATUS, frames=145, decoder_graph=1, decoder_graph_pool_cap_bytes=None,
                 display_device='xpu:2', display_schedule='eager-display', cone_graph_memory='replica-release',
                 features=dict(FEATURES, decoder_graph_pool_cap=False))
def candidate_client():
    c = client()
    c.a.expect_cone_graph_memory = 'replica-release'
    return c
for interval in (10, 60):
    for cache in (0, 1):
        for mode in ('parent', 'idle'):
            c = candidate_client()
            c.a.expect_gc_interval_seconds = interval
            c.a.expect_snapshot_digest_cache = cache
            c.a.expect_maintenance_mode = mode
            st = dict(candidate, gc_interval_seconds=interval, snapshot_digest_cache=cache, maintenance_mode=mode)
            c.preflight(st)
            check('132 candidate supports GC%d/cache%d/%s' % (interval, cache, mode),
                  c.status_server_options(st)['cone_graph_memory'] == 'replica-release')
for key, value in (('frames', 121), ('frames', 169), ('placement', 'two-way'), ('anchor', 'latent'),
                   ('decoder_graph', 0), ('anchor_decode', 'full'), ('bencode_overlap', 0), ('prep_ahead', 0),
                   ('snapshot_mode', 'walk'), ('snapshot_schedule', 'a-xpu3-sync'), ('anchor_read_ahead', 1),
                   ('aux_residency', 'xpu2'), ('display_worker', 'parallel'), ('display_device', 'xpu:3'),
                   ('display_schedule', 'sampler-a'), ('display_allocator_release', 'before-admission'),
                   ('decoder_graph_pool_cap_bytes', 10**9)):
    check('132 candidate rejects changed scope %s=%r' % (key,value),
          stopped(8, lambda: candidate_client().preflight(dict(candidate, **{key:value}))))
for value in (None, '', True, 1, 'on', 'replica'):
    check('132 rejects invalid mode %r' % value,
          stopped(8, lambda: client().preflight(dict(STATUS, cone_graph_memory=value))))
check('132 off expectation refuses candidate', stopped(8, lambda: client().preflight(candidate)))
check('132 candidate expectation refuses off', stopped(8, lambda: candidate_client().preflight(STATUS)))
check('132 missing new feature refuses', stopped(8, lambda: client().preflight(
    dict(STATUS, features=dict(FEATURES, cone_graph_memory=False)))))
for packet, args in ((132, []), (130, ['--expected-cone-graph-memory','off']),
                     (129, ['--expected-cone-graph-memory','replica-release'])):
    with contextlib.redirect_stderr(io.StringIO()):
        try:
            m.main(['--packet',str(packet),'--work-dir',str(TMP/'args'),'--port','18233', *args])
            ok=False
        except SystemExit as exc:
            ok=exc.code==2
    check('132 required mode/historical CLI rejects packet%s %r' % (packet,args),ok)
check('132 wrapper binds mandatory off-default cone option',
      'LTX_CONE_GRAPH_MEMORY:-off' in launcher and '--expected-cone-graph-memory "$CONE"' in launcher)
check('132 sealed cone module hash pin loads before receipts',
      Path(sys.modules['cone_memory131'].__file__) == sealed['dir']/'resolution/components/cone_memory131.py')
bad_pins=dict(sealed['modules'],cone_memory131='0'*64)
check('132 changed cone helper pin refuses',stopped(8,lambda:m.load_contract_modules(
      sealed['dir']/'resolution/components',module_sha=bad_pins)))
# Admission mutation checks run the same sealed CPU validator as the client.
cm=sys.modules['cone_memory131']
for first in (True, False):
    required=cm.FLOOR+cm.SCREEN+(cm.CAPTURE_RESERVE if first else 0)
    adm=dict(schema='ltx.stream131.cone-memory.v1', mode='replica-release', first_capture=first,
             capture_reserve_bytes=cm.CAPTURE_RESERVE if first else 0, floor_bytes=cm.FLOOR,
             screening_bytes=cm.SCREEN, required_bytes=required, free_bytes=required,
             margin_bytes=0,reserve_is_measured=False,
             allocator_release=dict(schema='ltx.stream130.allocator-release.v1',mode='before-admission',
                 scope='process-wide XPU allocator',reclaim_is_not_guaranteed=True,required_bytes=required, phase='before-cone',
                 admission_free_before_bytes=required, admission_free_after_bytes=required, release_called=False))
    r=dict(kind='qualify-graph' if first else 'stream',chunk_index=0,
           server_options=dict(OPTIONS,cone_graph_memory='replica-release',display_device='xpu:2'))
    d=dict(display_device='xpu:2',server_options=r['server_options'],cone_graph_memory_admission=adm)
    check('132 client validates admitted capture=%s' % first, candidate_client().validate_decode_identity(d,r)==d)
    try:
        candidate_client().validate_decode_identity(d,dict(r,kind='stream' if first else 'qualify-graph'));ok=False
    except ValueError:ok=True
    check('132 capture phase drift refuses first=%s' % first,ok)
    for key in adm:
        broken=copy.deepcopy(d);del broken['cone_graph_memory_admission'][key]
        try:
            candidate_client().validate_decode_identity(broken,r);ok=False
        except ValueError:ok=True
        check('132 missing admission field %s capture=%s refuses' % (key,first),ok)
    for kind, enabled in (('qualify-eager',True),('stream',False)):
        badr=dict(r,kind=kind,server_options=dict(r['server_options'],cone_graph_memory='replica-release' if enabled else 'off'))
        badd=dict(d,display_device='xpu:3' if kind=='qualify-eager' else 'xpu:2',server_options=badr['server_options'])
        try:
            candidate_client().validate_decode_identity(badd,badr);ok=False
        except ValueError:ok=True
        check('132 unexpected admission kind=%s enabled=%s refuses' % (kind,enabled),ok)


# Packet132 exact identities and independent audio option.
audio_candidate = dict(candidate, audio_residency='xpu2')
def audio_client():
    c = candidate_client()
    c.a.expect_audio_residency = 'xpu2'
    return c
c = audio_client()
c.preflight(audio_candidate)
check('132 audio candidate accepted with parent capture reserve', c.status_server_options(audio_candidate)['audio_residency']=='xpu2')
check('132 unrequested audio move refuses', stopped(8, lambda: candidate_client().preflight(audio_candidate)))
check('132 absent requested audio move refuses', stopped(8, lambda: audio_client().preflight(candidate)))
for key in ('audio_residency', 'cone_capture_reserve'):
    for value in (None, False, 0, 1, 'true'):
        st = copy.deepcopy(STATUS)
        st['features'][key] = value
        check('132 feature %s=%r refuses' % (key,value), stopped(8, lambda: client().preflight(st)))
    for value in (None, '', True, 0, 'other'):
        check('132 invalid identity %s=%r refuses' % (key,value), stopped(8,lambda:client().preflight(dict(STATUS,**{key:value}))))
for frames in (121,169):
    check('132 audio move fixed145 refuses%d' % frames, stopped(8,lambda:audio_client().preflight(dict(audio_candidate,frames=frames))))
c = candidate_client()
c.a.expect_cone_capture_reserve='scaled-476'
check('132 lower reserve fails closed even with matching expectation', stopped(8,lambda:c.preflight(dict(candidate,cone_capture_reserve='scaled-476'))))
for packet in (112,130,131):
    c=client(); c.a.packet=packet
    check('historical packet%d omits132 identities' % packet, all(k not in c.status_server_options(STATUS) for k in ('audio_residency','cone_capture_reserve')))
    for flag in ('--expect-audio-residency','--expect-cone-capture-reserve'):
        with contextlib.redirect_stderr(io.StringIO()):
            try:
                m.main(['--packet',str(packet),'--work-dir',str(TMP/'args'),'--port','18235',flag,'legacy' if flag.endswith('residency') else 'parent']); ok=False
            except SystemExit as exc: ok=exc.code==2
        check('historical packet%d refuses132 flag%s' % (packet,flag),ok)
check('132 wrapper uses new folder and pinned python', 's132-live01' in launcher and '/bin/python -B' in launcher)
check('132 wrapper defaults separate audio and parent reserve', 'LTX_AUDIO_RESIDENCY:-legacy' in launcher and 'LTX_CONE_CAPTURE_RESERVE:-parent' in launcher)
check('132 audio module sealed pin loaded',Path(sys.modules['audio_residency132'].__file__)==sealed['dir']/'resolution/components/audio_residency132.py')
bad_pins=dict(sealed['modules'],audio_residency132='0'*64)
check('132 changed audio helper pin refuses',stopped(8,lambda:m.load_contract_modules(sealed['dir']/'resolution/components',module_sha=bad_pins)))

diagnostic_audio = dict(audio_candidate, decoder_graph=0, cone_graph_memory='off',
                        features=dict(FEATURES, decoder_graph=False, decoder_graph_pool_cap=False))
c=client(); c.a.expect_audio_residency='xpu2'
c.preflight(diagnostic_audio)
check('132 audio dg0 diagnostic accepts matched off cone identity',True)
for key,value in (('frames',121),('frames',169),('display_worker','parallel'),('display_device','xpu:3'),('aux_residency','xpu2'),('cone_graph_memory','replica-release')):
    check('132 audio dg0 diagnostic rejects %s=%r' % (key,value),stopped(8,lambda:c.preflight(dict(diagnostic_audio,**{key:value}))))

for key, changed in (('audio_residency','xpu2'),('cone_capture_reserve','scaled-476')):
    for value in (None,changed):
        r=copy.deepcopy(receipt)
        if value is None: r['server_options'].pop(key)
        else: r['server_options'][key]=value
        check('132 receipt option missing/drift %s=%r refuses' % (key,value),
              stopped(12,lambda:client().verify_receipt(json.dumps(r).encode(),None,expect)))

# Same-waveform gate survives transport through the client decode validator.
ar=sys.modules['audio_residency132']
def audio_fixture():
    run='stream132-qref-c000000'; options=dict(OPTIONS,audio_residency='xpu2',display_device='xpu:2')
    receipt=dict(run_name=run,prompt_id='p',kind='qualify-eager',chunk_index=0,server_options=options)
    released=dict(device='cpu',active=False,calls=1,resident_bytes_on_xpu3=0,weight_sha256='b'*64)
    def ws(device,resident=0):
        return dict(before=ar.check_workspace(24*2**30,device,True,resident),after=ar.check_workspace(24*2**30,device,False))
    wave=dict(sha256='a'*64,shape=[1,2,288480],dtype='torch.float32')
    row=dict(mode='xpu2',device='xpu:2',kind=receipt['kind'],run_name=run,workspace=ws('xpu:2'),
        candidate_native_node_seconds=0.001,reference_released=released,
        cross_card=dict(equal=True,device='xpu:2',reference_device='xpu:3',mode='native-eager-uncached',
            sample_rate=48000,shape=wave['shape'],dtype=wave['dtype'],waveform_sha256='a'*64,reference_waveform_sha256='a'*64),
        reference=dict(workspace=ws('xpu:3',364666868),released=dict(released),seconds={k:0.001 for k in
            ('reference_weight_and_latent_copy','reference_decode','reference_output_copy','reference_unload','reference_total')}))
    record=dict(receipt,display_device='xpu:3',audio_residency='xpu2',audio_device='xpu:2',
        audio_residency_evidence=row,tensors={'waveform':wave},sample_rate=48000,cone_graph_memory_admission=None)
    return receipt,record
r,d=audio_fixture()
check('132 client accepts same-waveform cross-card evidence',audio_client().validate_decode_identity(d,r)==d)
for path,value in ((('audio_device',),'xpu:3'),(('prompt_id',),'different'),(('audio_residency_evidence',),None),
    (('audio_residency_evidence','cross_card','equal'),False),
    (('audio_residency_evidence','cross_card','reference_waveform_sha256'),'c'*64),
    (('audio_residency_evidence','reference_released','resident_bytes_on_xpu3'),364666868),
    (('audio_residency_evidence','reference_released','calls'),0),
    (('audio_residency_evidence','candidate_native_node_seconds'),float('nan')),
    (('audio_residency_evidence','workspace','before','free_bytes'),0)):
    r,d=audio_fixture(); node=d
    for key in path[:-1]: node=node[key]
    node[path[-1]]=value
    try: audio_client().validate_decode_identity(d,r);ok=False
    except ValueError:ok=True
    check('132 client rejects audio evidence drift '+'.'.join(path),ok)
bad = [name for name, ok in RESULTS if not ok]
print('\n%d/%d passed; CPU-only files in %s' % (len(RESULTS)-len(bad), len(RESULTS), TMP))
raise SystemExit(1 if bad else 0)
