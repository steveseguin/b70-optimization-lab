#!/usr/bin/env python3
"""Print the one-layer command only; reuse the existing admitted-container printer."""
import argparse
import re
import shlex
from container_command import command as slab_command


def command(render_node, health, receipts, overlay_sha256):
    if not re.fullmatch(r'[0-9a-f]{64}', overlay_sha256):
        raise ValueError('an exact overlay manifest SHA-256 is required')
    cmd = slab_command(render_node, health, receipts)
    # Keep the same single-device, image, offline and allocator restrictions.
    cmd.insert(cmd.index('--restart=no') + 1, '--stop-timeout=-1')
    index = cmd.index('/probe/single_rank_slab_probe.py')
    cmd[index] = '/probe/single_rank_first_forward_probe.py'
    cmd += ['--overlay-sha256', overlay_sha256]
    entry = cmd.index('--entrypoint=/opt/venv/bin/python')
    cmd[entry:entry] = ['-e', 'PYTHONUNBUFFERED=1', '-e', 'B70_SCREEN1B=1',
                       '-e', 'B70_SCREEN1B_STATE_DIR=/receipts/teardown']
    return cmd


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--render-node', required=True)
    parser.add_argument('--health-receipt', required=True)
    parser.add_argument('--receipt-dir', required=True)
    parser.add_argument('--overlay-sha256', required=True)
    args = parser.parse_args()
    print(shlex.join(command(args.render_node, args.health_receipt,
                             args.receipt_dir, args.overlay_sha256)))


if __name__ == '__main__':
    main()
