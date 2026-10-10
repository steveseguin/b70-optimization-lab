#!/home/steve/.venvs/ltx25-baseline/bin/python -B
"""CPU-only packet134 client contract tests; no server, sockets, signals or GPU imports.

Run with bin/python -B tests/run_cpu_suites.py run_tests_134.py. Synthetic evidence
checks admission and binding; it proves neither numerical equality nor runtime timing.
"""
import atexit
import shutil
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
spec = importlib.util.spec_from_file_location('client134_test', HERE.parent / 'ltx_continuation_client.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
m.load_contract_modules(m.PACKETS[134]['dir'] / 'resolution/components', module_sha=m.PACKETS[134]['modules'])
TMP = Path(tempfile.mkdtemp(prefix='ltx-client134-cpu-'))
atexit.register(shutil.rmtree, TMP)
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


OPTIONS = {'text_residency': 'legacy', 'text_oracle_sha256': None, 'audio_residency': 'legacy', 'cone_capture_reserve': 'parent', 'cone_graph_memory': 'off', 'display_allocator_release': 'off', 'maintenance_mode': 'parent', 'snapshot_digest_cache': 0, 'storage_scan_mode': 'request', 'gc_interval_seconds': 10, 'display_worker': 'serial', 'run_write_allowance_bytes': 3 * 2**30, 'snapshot_mode': 'fingerprint', 'decoder_graph_pool_cap_bytes': 10**9, 'aux_residency': 'legacy', 'residency_qualification_id': 'residency-legacy',
           'display_schedule': 'eager-display', 'anchor_read_ahead': 0, 'snapshot_schedule': 'full', 'display_device': 'xpu:3'}
FEATURES = {k: True for k in ('decode_thread', 'async_preview', 'chain_reset', 'chunk_length_choice',
                            'sharpness_diagnostic', 'video_first_handoff', 'frame_anchor', 'decoder_graph',
                            'cone_anchor_decode', 'bencode_overlap', 'prep_ahead', 'chunk_121', 'chunk_145', 'timing_split',
                            'snapshot_fingerprint', 'decoder_graph_pool_cap')}
FEATURES.update(text_residency=True, audio_residency=True, cone_capture_reserve=True, cone_graph_memory=True, chunk_169=True, atomic_preview=True, atomic_evidence_publication=True)
FEATURES.update({k + '_anchor': False for k in ('mixed', 'latent', 'guide')})
FEATURES['chunk_arm'] = True
STATUS = dict(OPTIONS, chunk_arm='off', packet=134, runtime_manifest_sha256='m', frames=121, placement='two-way20-28',
              text_reuse=1, anchor='frame', decoder_graph=1, anchor_decode='cone', bencode_overlap=1,
              prep_ahead=1, server_identity_sha256='s', receipt_dir=str(TMP / 'receipts'),
              output_directory=str(TMP / 'output'), features=FEATURES, phase='stream', plan_sha256=m.PACKETS[134]['plan_sha256'])


def client():
    c = m.Client.__new__(m.Client)
    c.a = SimpleNamespace(packet=134, expect_text_residency='legacy', expect_audio_residency='legacy', expect_cone_capture_reserve='parent', expect_cone_graph_memory='off', manifest_sha256='m', expect_frames=None, expect_placement=None,
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



def candidate():
    return dict(STATUS, frames=145, text_residency='split36',
                text_oracle_sha256=sys.modules['text_residency133'].ORACLE_SHA256,
                cone_graph_memory='text-shift', decoder_graph_pool_cap_bytes=None,
                features=dict(FEATURES, decoder_graph_pool_cap=False))


def candidate_client(st=None):
    st = candidate() if st is None else st
    c = client()
    c.a.expect_text_residency = 'split36'
    c.a.expect_cone_graph_memory = 'text-shift'
    c.frames = 145
    c.server_options = c.status_server_options(st)
    return c


def run_checks():
    for attr in ('DECODER_GRAPH_PACKETS', 'DECODE_THREAD_PACKETS', 'RESET_PACKETS',
                 'LEVER_PACKETS', 'SERVER_OPTION_PACKETS'):
        check('134 participates in ' + attr, 134 in getattr(m, attr))
    check('string134 parser', m.packet_id('134') == 134)
    check('134 stream directory', m.STREAM_DIR_RE_134.fullmatch('stream134-s00000012') is not None)
    check('133 stream directory rejected', m.STREAM_DIR_RE_134.fullmatch('stream133-s00000012') is None)
    client().preflight(STATUS)
    check('legacy134 retains parent132 admission', True)
    parent = client(); parent.a.packet = 132
    check('off134 equals132 plus explicit residency fields',
          client().status_server_options(STATUS) == dict(parent.status_server_options(STATUS),
                                                        text_residency='legacy', text_oracle_sha256=None))
    st = candidate()
    candidate_client().preflight(st)
    check('split36 exact fixed scope accepted', True)
    native169 = dict(st, frames=169, chunk_arm='split36-169', decoder_graph=0, cone_graph_memory='off', features=dict(st['features'], decoder_graph=False))
    def client169():
        c = candidate_client(native169)
        c.a.expect_chunk_arm = 'split36-169'
        c.a.expect_cone_graph_memory = 'off'
        c.a.expect_decoder_graph = 0
        c.frames = 169
        return c
    client169().preflight(native169)
    check('169 split36 graph off accepted', True)
    check('169 chunk arm participates in server identity', client169().status_server_options(native169)['chunk_arm'] == 'split36-169')
    for key,value in dict(chunk_arm='off',frames=145,decoder_graph=1,cone_graph_memory='text-shift',display_device='xpu:2',text_residency='legacy',display_schedule='sampler-a',audio_residency='xpu2',display_worker='parallel').items():
        check('169 rejects changed '+key, stopped(8,lambda key=key,value=value:client169().preflight(dict(native169,**{key:value}))))
    for gc in (10,60):
        c=client169();c.a.expect_gc_interval_seconds=gc;c.preflight(dict(native169,gc_interval_seconds=gc))
        check('169 accepts boundedGC%d'%gc,True)
    for gc in (10, 60):
        for cache in (0, 1):
            for maintenance in ('parent', 'idle'):
                c = candidate_client()
                c.a.expect_gc_interval_seconds = gc
                c.a.expect_snapshot_digest_cache = cache
                c.a.expect_maintenance_mode = maintenance
                c.a.expect_storage_scan_mode = 'background'
                c.preflight(dict(st, gc_interval_seconds=gc, snapshot_digest_cache=cache,
                                 maintenance_mode=maintenance, storage_scan_mode='background'))
                check('candidate maintenance %d/%d/%s' % (gc, cache, maintenance), True)
    changes = {'frames': (121, 169), 'placement': ('two-way',), 'text_reuse': (0,),
               'anchor': ('latent',), 'decoder_graph': (0,), 'anchor_decode': ('full',),
               'bencode_overlap': (0,), 'prep_ahead': (0,), 'snapshot_mode': ('walk',),
               'snapshot_schedule': ('a-xpu3-sync',), 'anchor_read_ahead': (1,),
               'aux_residency': ('xpu2',), 'audio_residency': ('xpu2',),
               'cone_capture_reserve': ('scaled-476',), 'display_worker': ('parallel',),
               'display_device': ('xpu:2',), 'display_schedule': ('sampler-a', 'sampler-b'),
               'display_allocator_release': ('before-admission',),
               'decoder_graph_pool_cap_bytes': (2**30,), 'cone_graph_memory': ('off', 'replica-release')}
    for key, values in changes.items():
        for value in values:
            check('split36 rejects scope %s=%r' % (key, value),
                  stopped(8, lambda: candidate_client().preflight(dict(st, **{key: value}))))
    for value in (None, '', True, 36, 'split24', 'split36 ', 'legacy'):
        check('candidate rejects text option %r' % value,
              stopped(8, lambda: candidate_client().preflight(dict(st, text_residency=value))))
    for value in (None, '', '0'*64, True, 1):
        check('candidate rejects text oracle %r' % value,
              stopped(8, lambda: candidate_client().preflight(dict(st, text_oracle_sha256=value))))
    missing = dict(st); del missing['text_oracle_sha256']
    check('missing oracle field rejects', stopped(8, lambda: candidate_client().preflight(missing)))
    missing = copy.deepcopy(st); del missing['features']['text_residency']
    check('missing residency feature rejects', stopped(8, lambda: candidate_client().preflight(missing)))
    check('legacy text rejects text-shift admission', stopped(8, lambda: client().preflight(
          dict(STATUS, cone_graph_memory='text-shift'))))
    check('legacy rejects candidate oracle', stopped(8, lambda: client().preflight(
          dict(STATUS, text_oracle_sha256=st['text_oracle_sha256']))))
    for packet in (131, 132):
        old = client(); old.a.packet = packet
        check('historical%s has no text options' % packet,
              not {'text_residency', 'text_oracle_sha256'} & old.status_server_options(st).keys())
        with contextlib.redirect_stderr(io.StringIO()):
            try:
                m.main(['--work-dir', str(TMP/'args'), '--packet', str(packet), '--port', '18239',
                        '--expect-text-residency', 'split36'])
                okay = False
            except SystemExit as exc:
                okay = exc.code == 2
        check('historical%s rejects text flag before network' % packet, okay)
    for packet, sealed in m.PACKETS.items():
        if 'plan_sha256' not in sealed:
            continue
        raw = (sealed['dir']/'resolution/stream-plan.json').read_bytes()
        plan = json.loads(raw)
        check('packet%s all-pins inner identity' % packet, sealed['plan_sha256'] == plan['plan_sha256'])
        check('packet%s all-pins differs from file hash' % packet,
              sealed['plan_sha256'] != hashlib.sha256(raw).hexdigest())
    sealed = m.PACKETS[134]
    check('134 sealed text module path', Path(sys.modules['text_residency133'].__file__) ==
          sealed['dir']/'resolution/components/text_residency133.py')
    bad = dict(sealed['modules'], text_residency133='0'*64)
    check('text helper changed pin refuses before import', stopped(8, lambda: m.load_contract_modules(
          sealed['dir']/'resolution/components', module_sha=bad)))
    check('plan file hash cannot substitute inner identity', stopped(8, lambda: candidate_client().preflight(
          dict(st, plan_sha256=hashlib.sha256((sealed['dir']/'resolution/stream-plan.json').read_bytes()).hexdigest()))))
    launcher = (HERE.parent/'start-client-134.sh').read_text()
    check('wrapper pins bin/python -B', '/bin/python -B ' in launcher and '/bin/python3' not in launcher)
    check('wrapper caps OMP', '--setenv=OMP_NUM_THREADS=2' in launcher)
    check('wrapper workdir default134', 'LTX_STREAM_WORKDIR:-/home/steve/ltx-stream/s134-live01' in launcher)
    check('wrapper binds text', '--expect-text-residency "$TEXT"' in launcher and
          'LTX_TEXT_RESIDENCY:-legacy' in launcher)
    check('wrapper admits text-shift', '"$CONE" == text-shift' in launcher)
    check('wrapper preserves authority', 'reset-failed' not in launcher and 'Restart=no' in launcher)
    # Both records are structurally valid. Their modes must additionally bind
    # to the receipt; otherwise a release audit could impersonate text-shift.
    for first in (False, True):
        for record_mode in ('replica-release', 'text-shift'):
            gib = 2**30
            required = 9*gib + 3*gib//4 + (5*gib if first else 0)
            free = 20*gib
            admission = dict(schema='ltx.stream131.cone-memory.v1', mode=record_mode,
                first_capture=first, capture_reserve_bytes=5*gib if first else 0,
                floor_bytes=9*gib, screening_bytes=3*gib//4, required_bytes=required,
                free_bytes=free, margin_bytes=free-required, reserve_is_measured=False,
                allocator_release=None if record_mode == 'text-shift' else dict(
                    schema='ltx.stream130.allocator-release.v1', mode='before-admission',
                    scope='process-wide XPU allocator', reclaim_is_not_guaranteed=True,
                    required_bytes=required, phase='before-cone',
                    admission_free_before_bytes=free, admission_free_after_bytes=free,
                    release_called=False))
            sys.modules['cone_memory131'].validate_record(admission, reserve_mode='parent')
            for receipt_mode in ('replica-release', 'text-shift'):
                options = dict(OPTIONS, cone_graph_memory=receipt_mode)
                receipt = dict(kind='qualify-graph' if first else 'stream', chunk_index=0,
                               server_options=options)
                record = dict(display_device='xpu:3', server_options=options,
                              cone_graph_memory_admission=admission)
                try:
                    client().validate_decode_identity(record, receipt)
                    accepted = True
                except ValueError:
                    accepted = False
                check('admission mode bound %s/%s/first%s' % (record_mode, receipt_mode, first),
                      accepted == (record_mode == receipt_mode))
    native_options = client169().status_server_options(native169)
    native_receipt = dict(kind='stream',chunk_index=0,server_options=native_options)
    memory = {phase: sys.modules['text_residency133'].display_admission(20*2**30,before=before)
              for phase,before in (('before',True),('after',False))}
    native_record = dict(display_device='xpu:3',server_options=native_options,
                         cone_graph_memory_admission=None,native_display_memory134=memory)
    client169().validate_decode_identity(native_record,native_receipt)
    check('169 physical display receipt accepted',True)
    def rejects_memory(value):
        try: client169().validate_decode_identity(dict(native_record,native_display_memory134=value),native_receipt)
        except ValueError: return True
        return False
    check('169 missing memory evidence refuses',rejects_memory(None))
    for phase in ('before','after'):
        for key in memory[phase]:
            bad=copy.deepcopy(memory)
            value=bad[phase][key]
            bad[phase][key] = (not value) if type(value) is bool else (value+1 if type(value) is int else 'changed')
            check('169 memory tamper '+phase+'.'+key,rejects_memory(bad))
        for badfree in (True,-1,0,1.5,None):
            bad=copy.deepcopy(memory);bad[phase]['free_bytes']=badfree
            check('169 invalidphysical '+phase+repr(badfree),rejects_memory(bad))
    print('\n%d/%d passed' % (sum(ok for _, ok in RESULTS), len(RESULTS)))
    return 0 if all(ok for _, ok in RESULTS) else 1


if __name__ == '__main__':
    raise SystemExit(run_checks())
