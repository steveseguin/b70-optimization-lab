#!/usr/bin/env python3
"""Plan the eight placement jobs on CPU; never launch a device window."""
import json
import subprocess
import sys
from pathlib import Path

from common import HERE, ROOT, read, require, save, sha
from conditions import cpu_gate
from cpu_seal import ARTIFACTS, verify


def main():
    cpu_gate()
    verify()
    jobs = HERE / 'placement-jobs.txt'
    destination = ARTIFACTS / 'plans'
    require(not destination.exists(), 'never replace saved placement plans')
    lines = [line for line in jobs.read_text().splitlines() if line and not line.startswith('#')]
    require(len(lines) == 8, 'exactly eight jobs required')
    seen = set()
    commands = []
    for line in lines:
        out, lineage, seal, binary, dispatch, placement = line.split('|')
        lane = Path(out).name.rsplit('-', 1)[-1]
        require(lane in ('A','B') and placement in ('1-split23','0-split23','0','1'), 'invalid placement job')
        require((placement, lane) not in seen, 'duplicate placement/lane')
        seen.add((placement,lane))
        commands.append((lane, placement, [sys.executable, '-B', str(HERE/'screen.py'),
            '--output', out, '--lineage', lineage, '--seal', seal, '--binary', binary,
            '--dispatch', dispatch, '--placement', placement, '--lane', lane, '--plan']))
    destination.mkdir()
    results=[]
    for lane, placement, command in commands:
        result=subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=60)
        expected=2 if placement.startswith('0') else 0
        require(result.returncode == expected, 'unexpected plan outcome: '+result.stderr)
        row=json.loads(result.stdout)
        require(row['device_executed'] is False and row['supported'] == (expected == 0), 'incorrect plan status')
        name='packet61x-placement-'+placement+'-'+lane+'.json'
        save(destination/name, row)
        results.append(dict(lane=lane,placement=placement,command=command,returncode=result.returncode,
            memory_admitted=row['identity']['placement']['memory_admitted'], supported=row['supported'],
            plan=name, sha256=sha(destination/name)))
        print(lane,placement,'admitted' if row['supported'] else 'unsupported (resident prefix head)',flush=True)
    save(destination/'commands.json',dict(passed=True,device_executed=False,
        scope='CPU plan outcomes, not model exactness or speed',jobs_sha256=sha(jobs),
        wrapper_seal_sha256=sha(ARTIFACTS/'wrapper-seal.json'),results=results))


if __name__=='__main__':main()
