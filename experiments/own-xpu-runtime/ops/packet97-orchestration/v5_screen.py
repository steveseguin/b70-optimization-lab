"""Pinned v5 entry. Unsupported choices refuse in --plan before device admission."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from v5_jobs import V5, ROOT, admission, read, sha


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--lane', choices=('A', 'B'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--plan', action='store_true')
    parser.add_argument('--fault-review', type=Path)
    parser.add_argument('--authorized-device-window', action='store_true')
    args = parser.parse_args(argv)
    assert sha(args.manifest) == args.manifest_sha256, 'manifest changed'
    config = read(args.manifest)
    assert config['lane'] == args.lane, 'lane differs'
    result = admission(config)
    if not result['admitted']:
        print(json.dumps(result, sort_keys=True))
        return 2
    # Separate interpreter: frozen wrapper modules use common global names.
    # The original config paths and native binary are never patched/relabelled.
    command = [sys.executable, '-B', str(V5/'screen.py'), '--lane', args.lane,
               '--placement', '1', '--lineage', str(V5/'lineage'),
               '--bracket', str(V5/'configs/bracket.json'), '--output', str(args.output)]
    if args.plan:
        command.append('--plan')
    else:
        assert args.authorized_device_window and args.fault_review
        # Reuse the frozen smoke validator on the actual retained receipt.
        check = subprocess.run([sys.executable, '-B', str(Path(__file__).with_name('v5_evidence.py')),
                                '--smoke', str(V5/'evidence/p98-smoke-B')],
                               cwd=ROOT, stdin=subprocess.DEVNULL)
        assert check.returncode == 0, 'same-wrapper/binary smoke required'
        command += ['--authorized-device-window', '--fault-review', str(args.fault_review)]
    return subprocess.run(command, cwd=ROOT, stdin=subprocess.DEVNULL).returncode


if __name__ == '__main__':
    raise SystemExit(main())
