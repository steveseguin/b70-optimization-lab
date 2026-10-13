#!/usr/bin/env python3
"""Actual merged maximum-capacity arithmetic fixture under ASAN/UBSAN; CPU only."""
import json,os
from pathlib import Path
import capacity_fixture_gate as gate

def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get('OMP_NUM_THREADS')=='2'
 gate.REPORT=gate.P/'asan-fixture-gates.json'
 report=dict(schema='packet45.asan-fixture.v1',passed=False,device_executed=False,rows=[])
 row=gate.run_arm('asan','nongemv',32768,report,1800)
 report.update(passed=row['passed'],checks=row['checks'],binary_sha256=row['binary_sha256'])
 gate.save(gate.REPORT,report);print(json.dumps(dict(passed=report['passed'],checks=report['checks'])))
if __name__=='__main__':main()
