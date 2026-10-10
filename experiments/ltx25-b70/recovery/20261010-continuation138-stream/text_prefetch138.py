"""Scheduled text handoff. Pure protocol helpers; importing never touches devices."""
import hashlib
import json
import os
from pathlib import Path

CHOICES = ('off', 'scheduled')
SCHEMA = 'ltx.stream138.text-prefetch.v1'
SCHEDULE_SHA256 = '06c2357414cc4bc0672310eab9562239e75475eed2ee8d081da81e59cc777012'
MAX_BUFFER_BYTES = 1376256
BOUND_SECONDS = 30.0
_CONSUMER = None


def require(value, message):
    if not value:
        raise RuntimeError(message)


def launch(environ=None):
    mode = (os.environ if environ is None else environ).get('LTX_TEXT_PREFETCH', 'off')
    require(mode in CHOICES, 'LTX_TEXT_PREFETCH must be off or scheduled')
    return mode


def validate_scope(environ=None):
    env = os.environ if environ is None else environ
    mode = launch(env)
    if mode == 'scheduled':
        import text_residency133
        require(text_residency133.validate_scope(env) == 'split36',
                'Scheduled text prefetch requires qualified split36 and its parent oracle')
        require(env.get('LTX_STREAM_TEXT_REUSE', '1') == '1', 'Scheduled text prefetch requires scene text reuse')
    return mode


def load_schedule(path=None):
    path = Path(path) if path is not None else Path(__file__).with_name('prefetch-scenes138.json')
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == SCHEDULE_SHA256, 'Prefetch scene table changed')
    rows = json.loads(raw)['fixtures']
    require(len(rows) == 10 and len({row['prompt'] for row in rows}) == 10,
            'Prefetch requires the ten distinct admitted scenes')
    return rows


def prediction(params, scenes):
    """A schedule hint authorizes candidates, never changes the actual request."""
    position = params.get('schedule_position', -1)
    if (params.get('kind') != 'stream' or params.get('reset') or
            params.get('schedule_sha256') != SCHEDULE_SHA256 or type(position) is not int or
            not 0 <= position < 40 or position % 4 != 3 or
            params.get('prompt') != scenes[position // 4]['prompt']):
        return None
    following = (position + 1) % 40
    return {'prompt': scenes[following // 4]['prompt'], 'schedule_position': following,
            'schedule_sha256': SCHEDULE_SHA256, 'stream_seq': params['stream_seq'] + 1,
            'chunk_index': params['chunk_index'] + 1}


def matches(entry, *, chain, params, run_name):
    if not entry or params.get('reset') or params.get('reuse_text'):
        return False
    return (entry['source_chain'] == chain and entry['target_run_name'] == run_name and
            entry['target_chunk_index'] == params['chunk_index'] and
            entry['target_stream_seq'] == params['stream_seq'] and
            entry['prompt_sha256'] == hashlib.sha256(params['prompt'].encode()).hexdigest() and
            (params['kind'] != 'stream' or
             (entry['schedule_position'] == params.get('schedule_position') and
              entry['schedule_sha256'] == params.get('schedule_sha256'))))


def install_consumer(callback):
    global _CONSUMER
    require(callable(callback) and _CONSUMER is None, 'Prefetch consumer is one-shot')
    _CONSUMER = callback


def consume_prefetch(clip, text, mode, clip_index, run_name):
    return None if _CONSUMER is None else _CONSUMER(clip, text, mode, clip_index, run_name)


def validate_evidence(record):
    import text_residency133
    require(type(record) is dict and record.get('schema') == SCHEMA and record.get('consumed') is True,
            'Prefetch consumption evidence missing')
    require(record.get('storage_device') == 'cpu' and type(record.get('buffer_bytes')) is int and
            0 < record['buffer_bytes'] <= MAX_BUFFER_BYTES, 'Prefetch buffer exceeds one admitted conditioning')
    require(record.get('captured_graphs_before') == record.get('captured_graphs_after') and
            type(record.get('captured_graphs_before')) is int and record['captured_graphs_before'] > 0,
            'Prefetch changed the qualified text graph set')
    require(record.get('tls_clear') is True and record.get('native_streams_restored') is True,
            'Prefetch left worker window or stream state active')
    require(str(record.get('worker', '')).startswith('ltx-encode-') and record.get('tensor_rows'),
            'Prefetch did not use an admitted encoder worker')
    require(type(record.get('started_ns')) is int and type(record.get('done_ns')) is int and
            record['done_ns'] >= record['started_ns'], 'Prefetch timing differs')
    for name in ('prompt_sha256', 'oracle_sha256'):
        value = record.get(name)
        require(type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value),
                'Prefetch identity missing: ' + name)
    require(record['oracle_sha256'] == text_residency133.ORACLE_SHA256, 'Prefetch oracle identity differs')
    require(type(record.get('window')) is dict and record['window'].get('captured_graphs') == 0 and
            record['window'].get('window') == 64, 'Prefetch window or no-capture state differs')
    for key in ('memory_before', 'memory_after'):
        memory = record.get(key)
        require(type(memory) is dict and set(memory) == {'xpu:2', 'xpu:3'}, 'Prefetch memory evidence missing')
        for card, floor in (('xpu:2', 2), ('xpu:3', 9)):
            require(type(memory[card]) is int and memory[card] >= int((floor + 0.75) * 1024 ** 3),
                    'Prefetch memory screen failed on ' + card)
    return record
