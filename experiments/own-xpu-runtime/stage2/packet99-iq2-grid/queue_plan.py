"""CPU-only plans in a temporary queue; measured micro admission stays pending."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from build_engine import P, ROOT, save, limits


def main():
    limits()
    queue = P.parents[1] / 'ops/lane-queue'
    rows = []
    with tempfile.TemporaryDirectory(prefix='p99-queue-plan-') as tmp:
        destination = Path(tmp)
        for source in sorted(queue.glob('proposed-p99-*.txt')):
            proposal=json.loads(source.read_text());label=source.stem;lane=proposal['lane']
            (destination / f'queue-{lane}.txt').write_bytes(source.read_bytes())
            command = [sys.executable, '-B', str(queue / 'lanequeue.py'), 'plan',
                       '--lane', lane, '--directory', str(destination)]
            with (P / 'evidence' / f'queue-plan-{label}.log').open('w') as log:
                subprocess.run(command, stdin=subprocess.DEVNULL, stdout=log,
                               stderr=subprocess.STDOUT, check=True, timeout=180)
            rows.append(dict(lane=lane, proposal=str(source.relative_to(ROOT)), command=command,
                             passed=True, runnable=False, micro_gate='pending at planning'))
    save(P / 'evidence/queue-plans.json', dict(passed=True, device_executed=False,
         live_queue_modified=False, runnable=False, plans=rows))
    print(len(rows),'temporary queue plans PASS; measured micro-B gate and exact source winner remain mandatory')


if __name__ == '__main__':
    main()
