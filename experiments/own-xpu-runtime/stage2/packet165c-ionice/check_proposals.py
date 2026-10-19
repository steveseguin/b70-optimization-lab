"""Plan temporary proposal copies and rehearse real reports; never queue."""
import resource
import subprocess
import tempfile
from pathlib import Path

from check_launch import HERE, ROOT, OPS, read, save, sha
from build_engine import limits

limits()
resource.setrlimit(resource.RLIMIT_AS, (4_000_000_000,) * 2)
checks = []
for number in (163, 165):
    proposal = OPS / 'lane-queue' / f'proposed-p{number}-one-card-A.txt'
    with tempfile.TemporaryDirectory(prefix=f'packet165c-plan-{number}-') as directory:
        scratch = Path(directory)
        copied = scratch / 'queue-A.txt'
        copied.write_bytes(proposal.read_bytes())
        assert sha(copied) == sha(proposal)
        for kind, command in (
            ('plan', ['/usr/bin/python3', '-B', str(OPS / 'lane-queue/lanequeue.py'),
                      'plan', '--lane', 'A', '--directory', str(scratch)]),
            ('rehearse', ['/usr/bin/python3', '-B', str(OPS / 'rehearse_entry.py'),
                          str(copied), '--report', '--json'])):
            target = HERE / 'evidence' / f'{kind}-p{number}.{ "json" if kind == "rehearse" else "log"}'
            with target.open('w') as stdout, target.with_suffix('.stderr.log').open('w') as stderr:
                child = subprocess.run(command, cwd=ROOT, stdin=subprocess.DEVNULL,
                    stdout=stdout, stderr=stderr)
            assert child.returncode == 0, (kind, number, target)
            if kind == 'rehearse':
                result = read(target)
                assert result['passed'] and len(result['jobs']) == 2
                assert all(r['passed'] and r['report']['passed'] and not r['service_started'] for r in result['jobs'])
            else:
                import json
                rows = [json.loads(s) for s in target.read_text().splitlines() if s.startswith('{')]
                assert len(rows) == 2 and all(r['plan'] == 'passed' for r in rows)
            checks.append(dict(proposal=str(proposal.relative_to(ROOT)), proposal_sha256=sha(proposal),
                kind=kind, path=str(target.relative_to(ROOT)), sha256=sha(target), passed=True))
            print(number, kind, 'PASS', flush=True)
save(HERE / 'evidence/proposal-checks.json', dict(passed=True, device_executed=False, queued=False, checks=checks))
