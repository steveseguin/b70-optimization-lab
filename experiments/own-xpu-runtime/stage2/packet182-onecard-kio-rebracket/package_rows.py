#!/usr/bin/env python3
"""Packet182 package step: every CPU gate passed -> proposal bytes verified -> seal written and verified.

Order (plan after seal): gates.py --check -> package_rows.py -> check_queue_rows.py ->
final_checks.py -> final_checks.py --ready. Refuses if READY-FOR-DEVICE.json exists
(never edit a packet that may be queued). CPU only; writes evidence/package-rows.json.
"""
import json, os, subprocess, sys
from pathlib import Path
from build_engine import P, ROOT, sha, save, limits

LQ = P.parents[1] / 'ops/lane-queue'
NAME = 'proposed-p182-one-card-A.txt'


def run(argv):
    cp = subprocess.run([sys.executable, '-B', *map(str, argv)], cwd=P, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=1800)
    assert cp.returncode == 0, (argv, cp.stdout[-2000:], cp.stderr[-2000:])
    return cp.stdout


def main():
    limits()
    assert not (P / 'READY-FOR-DEVICE.json').exists(), 'READY exists: no repackaging of a ready packet'
    gates = json.loads(run([P / 'gates.py', '--check']))
    assert gates['passed'] is True
    import plan_queue
    job, raw = plan_queue.document()
    for path in (P / 'screen/proposals' / NAME, LQ / NAME):
        assert path.read_text() == raw, 'proposal differs from the generated document: ' + str(path)
    seal_out = run([P / 'seal.py'])
    verify = run([P / 'seal.py', '--verify'])
    receipt = P / 'screen/build-receipt.json'
    row = dict(schema='packet182.package-rows.v1', passed=True, device_executed=False, gates=gates['gates'],
               seal=dict(receipt='screen/build-receipt.json', sha256=sha(receipt), write=seal_out.strip(), verify=verify.strip(),
                         sources=len(json.loads(receipt.read_text())['sources'])),
               proposal=dict(path=str((LQ / NAME).relative_to(ROOT)), sha256=sha(LQ / NAME), job=job['name'], lane=job['lane'],
                             local_copy='screen/proposals/' + NAME, queued=False))
    save(P / 'evidence/package-rows.json', row)
    print(json.dumps(dict(passed=True, seal_sha256=row['seal']['sha256'], sources=row['seal']['sources'], proposal_sha256=row['proposal']['sha256'])))


if __name__ == '__main__':
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    main()
