#!/usr/bin/env python3
"""Explicit small-metadata authority seal; never creates an operational plan."""
import argparse,hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent;L=P.parents[1];ACTUAL=L/'dense-q6-p33/operating/evidence/device-a/review.json';BINARY='a0f9ffc58de704a276b237cbeec2b338ee873c0872bcae2da2214286aa5cce50'
def main():
 p=argparse.ArgumentParser();p.add_argument('--seal',action='store_true',required=True);p.parse_args()
 raw=ACTUAL.read_bytes();r=json.loads(raw)
 assert r['passed'] is True and r['native_binary_sha256']==BINARY and r['all12_exact'] and r['requests']==26 and r['measured_arms']==24 and r['bundles']==54 and r['physical_drain'] and r['explicit_final_repeat_and_closed_stamps_verified']
 out=dict(passed=True,path=str(ACTUAL),sha256=hashlib.sha256(raw).hexdigest(),binary_sha256=BINARY,scope='Immutable actual Q6 fullsuite prerequisite; no plan or device invocation')
 with (P/'actual-authority.json').open('x') as f:json.dump(out,f,indent=2);f.write('\n')
 print(hashlib.sha256((P/'actual-authority.json').read_bytes()).hexdigest())
if __name__=='__main__':main()
