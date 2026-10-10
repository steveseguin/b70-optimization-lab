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

def validate_scope(env=None):
    env = os.environ if env is None else env
    mode = launch(env)
    if mode == 'split36':
        require(all(env.get(k, DEFAULTS.get(k)) == v for k, v in SCOPE.items()), 'fixed145 native display3 scope required')
        require(env.get('LTX_DECODER_GRAPH_POOL_CAP_GB') is None, 'pool cap must be unset')
        require(env.get('LTX_DISPLAY_REPLICA_TRANSIENT_GIB') is None, 'replica reserve must be unset')
    else:
        require(env.get('LTX_CONE_GRAPH_MEMORY', 'off') != 'text-shift', 'text-shift needs split36')
    return mode

def options(env=None):
    mode = validate_scope(env)
    return dict(text_residency=mode, text_oracle_sha256=ORACLE_SHA256 if mode == 'split36' else None)

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
