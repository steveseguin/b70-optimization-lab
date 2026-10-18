"""The owner permits this minimal reseal only before any timing/native model window."""
from pathlib import Path
import json

P = Path(__file__).resolve().parent


def check():
    old = P/'evidence/card0-capacity-a/smoke'
    if old.exists():
        row = json.loads((old/'queue.json').read_text())
        assert row['passed'] is False and row['completed'] == ['K1a', 'K1b']
        assert row['child_still_running'] is False
        assert not (old/'WSCREEN').exists(), 'timing window already created'
        assert 'identity changed:' in (old/'WSCREEN.log').read_text()
    assert not (P/'evidence/card0-capacity-a/max').exists()
    failed = P/'evidence/card0-capacity-c/smoke'
    if failed.exists():
        queue = json.loads((failed/'queue.json').read_text())
        window = json.loads((failed/'WSCREEN/window.json').read_text())
        assert queue['passed'] is False and queue['completed'] == ['K1a', 'K1b']
        assert queue['child_still_running'] is False
        assert window['passed'] is False and window['returncode'] == 1
        assert 'anonymous-memory sensor unavailable: DRM occupancy malformed' in window['stop_reasons']
        for name in ('timings.jsonl', 'prefill-timings.jsonl'):
            assert (failed/'WSCREEN/run/run'/name).read_bytes() == b'', 'timing already ran'
    assert not (P/'evidence/card0-capacity-c/max').exists()
    assert not (P/'evidence/card0-ports-a').exists(), 'fresh output already consumed'
