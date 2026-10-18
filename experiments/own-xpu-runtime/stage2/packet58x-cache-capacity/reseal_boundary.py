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
    assert not (P/'evidence/card0-capacity-c').exists(), 'fresh output already consumed'
