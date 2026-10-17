"""One hash-pinned stopped chain may coexist with a fresh packet70 reseal."""
import json
from pathlib import Path
from storage import digest
P = Path(__file__).resolve().parent
ARCHIVE = 'device-cards01-a-k2fail-20261017T1933'


def verify_archive(root):
    root = Path(root)
    if root.is_symlink() or root.name != ARCHIVE:
        raise ValueError('unregistered stopped archive')
    pin = json.loads((P/'archived-chains.json').read_text())
    manifest = P/pin['manifest']
    if digest(manifest) != pin['sha256']:
        raise ValueError('archive manifest changed')
    row = json.loads(manifest.read_text())
    if row['name'] != root.name or any(f.is_symlink() for f in root.rglob('*')):
        raise ValueError('archive path changed')
    actual = {str(f.relative_to(root)):digest(f) for f in sorted(root.rglob('*')) if f.is_file()}
    if actual != row['files']:
        raise ValueError('stopped archive inventory changed')
    if (root/'STOP').read_text() != 'K2 exited 1; no retry\n':
        raise ValueError('archive STOP changed')
    window = json.loads((root/'K2/window.json').read_text())
    if window['passed'] is not False or window['error'] != 'selection must name exactly route/recurrence/hc':
        raise ValueError('not the registered K2 wrapper failure')
    for name in ('run0', 'round3-timing'):
        receipt = json.loads((root/'K2'/name/'receipt.json').read_text())
        rows = receipt['teardown']
        rows = rows if isinstance(rows, list) else [rows]
        if not receipt['passed'] or not rows or not all(r['safe_to_exit'] is True and r['exit_code'] == r['live_bytes'] == r['in_flight'] == 0 for r in rows):
            raise ValueError('archive device work or teardown incomplete')
    return row


def require_fresh_chain(build):
    for root in Path(build).glob('device-cards01-*'):
        if root.name != ARCHIVE:
            raise ValueError('chain started; selection frozen: '+root.name)
        verify_archive(root)
