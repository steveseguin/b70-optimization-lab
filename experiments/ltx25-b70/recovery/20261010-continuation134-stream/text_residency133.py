"""Packet133 startup-only text ownership. Stdlib only; no runtime device calls."""
import hashlib
import json
import os
from pathlib import Path

ENV = 'LTX_TEXT_RESIDENCY'
CHOICES = ('legacy', 'split36')
PARENT_MANIFEST_SHA256 = '67ec59a5b0c5131d0b129e4c0b9187386c29c0395ac225dc28422516684991ad'
ORACLE_SHA256 = '125750aa533d91d08aab7c47b416bc15e25a1371078425a4802e3cac762442c2'
SCOPE = {
    'LTX_STREAM_FRAMES': '145', 'LTX_SAMPLER_PLACEMENT': 'two-way20-28',
    'LTX_ANCHOR': 'frame', 'LTX_DECODER_GRAPH': '1', 'LTX_ANCHOR_DECODE': 'cone',
    'LTX_BENCODE_OVERLAP': '1', 'LTX_PREP_AHEAD': '1', 'LTX_STREAM_TEXT_REUSE': '1',
    'LTX_SNAPSHOT_MODE': 'fingerprint', 'LTX_SNAPSHOT_SCHEDULE': 'full',
    'LTX_ANCHOR_READ_AHEAD': '0', 'LTX_AUX_RESIDENCY': 'legacy',
    'LTX_AUDIO_RESIDENCY': 'legacy', 'LTX_DISPLAY_DEVICE': 'xpu:3',
    'LTX_DISPLAY_SCHEDULE': 'eager-display', 'LTX_DISPLAY_WORKER': 'serial',
    'LTX_DISPLAY_ALLOCATOR_RELEASE': 'off', 'LTX_CONE_GRAPH_MEMORY': 'text-shift',
    'LTX_CONE_CAPTURE_RESERVE': 'parent',
}
DEFAULTS = dict(LTX_SNAPSHOT_SCHEDULE='full', LTX_ANCHOR_READ_AHEAD='0',
    LTX_AUX_RESIDENCY='legacy', LTX_AUDIO_RESIDENCY='legacy', LTX_DISPLAY_WORKER='serial',
    LTX_DISPLAY_ALLOCATOR_RELEASE='off', LTX_CONE_CAPTURE_RESERVE='parent')

def require(ok, why):
    if not ok:
        raise ValueError('Text residency: ' + why)

def launch(env=None):
    env = os.environ if env is None else env
    mode = env.get(ENV, 'legacy')
    require(mode in CHOICES, 'unknown mode')
    return mode

def split_index(env=None):
    return 36 if launch(env) == 'split36' else 24

def chunk_arm(env=None):
    env = os.environ if env is None else env
    value = env.get('LTX_CHUNK_ARM', 'off')
    require(value in ('off', 'split36-169'), 'unknown chunk arm')
    return value

def validate_scope(env=None):
    env = os.environ if env is None else env
    mode = launch(env)
    arm = chunk_arm(env)
    require(arm == 'off' or mode == 'split36', '169 arm requires split36')
    scope = dict(SCOPE, LTX_STREAM_FRAMES='169', LTX_DECODER_GRAPH='0', LTX_CONE_GRAPH_MEMORY='off') if arm == 'split36-169' else SCOPE
    if mode == 'split36':
        require(all(env.get(k, DEFAULTS.get(k)) == v for k, v in scope.items()), 'fixed145 native display3 scope required')
        require(env.get('LTX_DECODER_GRAPH_POOL_CAP_GB') is None, 'pool cap must be unset')
        require(env.get('LTX_DISPLAY_REPLICA_TRANSIENT_GIB') is None, 'replica reserve must be unset')
    else:
        require(env.get('LTX_CONE_GRAPH_MEMORY', 'off') != 'text-shift', 'text-shift needs split36')
    return mode

def options(env=None):
    mode = validate_scope(env)
    result = dict(text_residency=mode, text_oracle_sha256=ORACLE_SHA256 if mode == 'split36' else None)
    if chunk_arm(env) != 'off':
        result['chunk_arm'] = chunk_arm(env)
    return result

def load_oracle(path=None):
    if path is None:
        path = Path(__file__).resolve().with_name('text-oracle133.json')
        if not path.is_file():
            path = Path(__file__).resolve().parents[2] / 'resolution/components/text-oracle133.json'
    raw = Path(path).read_bytes()
    require(hashlib.sha256(raw).hexdigest() == ORACLE_SHA256, 'oracle file hash changed')
    value = json.loads(raw)
    require(value.get('schema') == 'ltx.stream133.text-oracle.v1' and
            value.get('parent_manifest_sha256') == PARENT_MANIFEST_SHA256, 'oracle identity changed')
    require(len(value.get('prompts', {})) == 12 and len(value.get('window_probe', {}).get('rows', [])) == 40,
            'oracle coverage changed')
    return value

def check_conditioning(oracle, prompt_sha, rows):
    expected = oracle['prompts'].get(prompt_sha)
    require(expected is not None, 'prompt has no parent24/24 conditioning oracle')
    require(rows == expected['tensors'], 'conditioning differs from parent24/24 bytes')
    return dict(passed=True, oracle_sha256=ORACLE_SHA256, prompt_sha256=prompt_sha)

def check_window(oracle, report):
    expected = oracle['window_probe']
    require(report.get('passed') is True, 'window probe failed')
    for key in ('admitted', 'prompt_tokens', 'prompts_file_sha256'):
        require(report.get(key) == expected[key], 'window probe ' + key + ' differs')
    fields = ('prompt', 'real_tokens', 'window', 'full_sha256', 'window_sha256')
    actual = [{k: row.get(k) for k in fields} for row in report.get('rows', [])]
    require(actual == expected['rows'], 'full/window conditioning differs from parent24/24')
    return dict(passed=True, oracle_sha256=ORACLE_SHA256, prompt_count=len(actual))

def transform_node(raw):
    old = "SHARD = ('xpu:2', 'xpu:3', 24)"
    new = "import text_residency133\nSHARD = ('xpu:2', 'xpu:3', text_residency133.split_index())"
    text = raw.decode()
    require(text.count(old) == 1, 'startup shard source anchor differs')
    return text.replace(old, new).encode()

DISPLAY_RESERVE_169 = 13 * 2**29
DISPLAY_FLOOR = 9 * 2**30
SCREEN = 3 * 2**28

def display_admission(free_bytes, *, before):
    require(type(free_bytes) is int and type(before) is bool, 'invalid display reading')
    required = DISPLAY_FLOOR + SCREEN + (DISPLAY_RESERVE_169 if before else 0)
    record = dict(schema='ltx.stream134.native-display-memory.v1', before=before,
        free_bytes=free_bytes, floor_bytes=DISPLAY_FLOOR, screening_bytes=SCREEN,
        transient_reserve_bytes=DISPLAY_RESERVE_169 if before else 0,
        required_bytes=required, margin_bytes=free_bytes-required, reserve_is_measured=False)
    require(free_bytes >= required, 'native169 display memory refused: ' + repr(record))
    return record

def validate_display_evidence(options, decode):
    evidence = (decode or {}).get('native_display_memory134')
    if options.get('chunk_arm', 'off') != 'split36-169':
        require(evidence is None, 'unexpected native169 display evidence')
        return False
    require(type(evidence) is dict and set(evidence) == {'before', 'after'}, 'native169 display evidence missing')
    for phase, before in (('before', True), ('after', False)):
        row = evidence[phase]
        require(type(row) is dict, 'native169 display sample missing')
        expected = display_admission(row.get('free_bytes'), before=before)
        require(set(row) == set(expected) and all(type(row[k]) is type(v) and row[k] == v for k,v in expected.items()),
                'native169 display evidence differs')
    return True
