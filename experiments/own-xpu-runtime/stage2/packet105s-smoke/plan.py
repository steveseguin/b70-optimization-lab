#!/usr/bin/env python3
"""CPU-only queue rehearsal; writes only this packet's evidence and a temp copy."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from smoke import HERE, P105, digest, verify_adapter


def main():
    verify_adapter()
    root = P105.parents[3]
    queue = P105.parents[1] / 'ops/lane-queue'
    proposal = queue / 'proposed-p105-smoke-B.txt'
    evidence = HERE / 'evidence'
    evidence.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='p105s-queue-') as tmp:
        dest = Path(tmp)
        for path in queue.glob('*.py'):
            shutil.copyfile(path, dest / path.name)
        shutil.copyfile(proposal, dest / 'queue-B.txt')
        cmd = ['/usr/bin/python3', '-B', str(queue / 'lanequeue.py'),
               'plan', '--lane', 'B', '--directory', str(dest)]
        result = subprocess.run(cmd, cwd=root, stdin=subprocess.DEVNULL,
                                capture_output=True, text=True, timeout=180)
    (evidence / 'queue-plan-B.log').write_text(result.stdout + result.stderr)
    if result.returncode:
        raise SystemExit('CPU queue plan failed; inspect evidence/queue-plan-B.log')
    receipt = dict(passed=True, device_executed=False, live_queue_modified=False,
                   proposal=str(proposal.relative_to(root)), proposal_sha256=digest(proposal),
                   queue_driver_sha256=digest(queue / 'lanequeue.py'),
                   source_pins_sha256=digest(HERE / 'source-pins.json'),
                   command=cmd, log_sha256=digest(evidence / 'queue-plan-B.log'))
    (evidence / 'queue-plan.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print('PASS: one candidate smoke planned on a temporary lane-B queue copy; no device work.')


if __name__ == '__main__':
    main()
