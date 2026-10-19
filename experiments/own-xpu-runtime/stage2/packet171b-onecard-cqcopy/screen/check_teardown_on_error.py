#!/usr/bin/env python3
"""Read-only inventory of the v1 teardown-on-error helper AND its wiring.

No imports from the scanned packet. An exact known integration is CARRIED;
missing or changed files require review. This is not a runtime/quality seal.
"""
import argparse
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TEMPLATES = Path(__file__).with_name('teardown-templates.json')


def digest(path):
    if path.is_symlink() or not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect_packet(packet, kind=None):
    packet = Path(packet)
    if packet.is_symlink() or not packet.is_dir():
        raise ValueError('packet must be a real directory')
    manifest = json.loads(TEMPLATES.read_text())
    if kind is None:
        kinds = [name for name, marker in (('chain', 'window_adapter.py'), ('screen', 'screen.py'))
                 if (packet / marker).exists()]
        # Screen wrappers also carry an unused window_adapter.py. Their actual
        # entry is screen.py; ask explicitly for chain to audit that spare copy.
        if 'screen' in kinds:
            kinds = ['screen']
    else:
        kinds = [kind]
    files = {'teardown_on_error.py': manifest['helper_sha256']}
    for name in kinds:
        files.update({path: row['after_sha256'] for path, row in
                      manifest['integrations'][name]['template_paths'].items()})
    rows = []
    for path, expected in files.items():
        actual = digest(packet / path)
        rows.append(dict(path=path, expected_sha256=expected, sha256=actual,
                         status='MATCH' if actual == expected else 'MISSING' if actual is None else 'DIFFERS'))
    carried = bool(kinds) and all(row['status'] == 'MATCH' for row in rows)
    return dict(schema='own-runtime.teardown-on-error.inventory.v1', packet=str(packet),
                integrations=kinds, status='CARRIED' if carried else 'NOT_VERIFIED',
                passed=carried, device_executed=False, files=rows,
                scope='Exact v1 helper and known entry wiring only; resealing and device qualification remain separate.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('packet', type=Path)
    parser.add_argument('--kind', choices=('chain', 'screen'))
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    try:
        report = inspect_packet(args.packet, args.kind)
    except (OSError, ValueError) as error:
        print('teardown-on-error inventory failed: ' + str(error))
        return 2
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(report['status'] + ' ' + report['packet'])
        for row in report['files']:
            print('  ' + row['status'] + ' ' + row['path'])
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
