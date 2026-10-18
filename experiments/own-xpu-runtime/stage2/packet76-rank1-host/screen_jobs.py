"""Packet76 job definitions; every screen executes the shared, sealed v4 path."""
import json
from pathlib import Path
import sys
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
WRAPPER=P.parent/'screen/v4-lanes'
sys.path.insert(0,str(WRAPPER))
from common import read,require,sha,verify_map
from cpu_seal import verify as verify_wrapper

def verify():
    verify_wrapper()
    row=read(P/'screen-jobs-seal.json')
    verify_map(ROOT,row['sources'])
    require(row['wrapper_seal_sha256']==sha(WRAPPER/'wrapper-seal.json'),'shared wrapper pin changed')
    return row

def jobs(lane):
    require(lane in ('A','B'),'lane')
    result=[]
    for index,choice in enumerate(('production','ordered','production')):
        v=P/'selections'/choice
        result.append(dict(out=f'p76-{lane}-{index}-{choice}',choice=choice,
            lineage=str(v),seal=str(v/'screen-seal.json'),binary=str(v/'build/device/own-rt-iq3'),
            dispatch=str(v/'dispatch-speed6.json'),placement='1-split23'))
    return result

def command(row,lane,review=None,plan=False):
    cmd=['/usr/bin/python3','-B',str(WRAPPER/'screen.py'),'--profile','tp2',
         '--lane',lane,'--placement','1-split23','--timing','token']
    for key in ('lineage','seal','binary','dispatch'):cmd+=['--'+key,row[key]]
    cmd+=['--output',str(WRAPPER/'evidence'/row['out'])]
    return cmd+(['--plan'] if plan else ['--fault-review',str(review),'--authorized-device-window'])

def choose(rows):
    require([r['choice'] for r in rows]==['production','ordered','production'],'full lane A grid required')
    require(all(r['exact'] for r in rows),'all 13 requests in every A screen must match packet49')
    require(rows[1]['rate']>max(rows[0]['rate'],rows[2]['rate']),'candidate does not beat both fresh controls; lane B withheld')
    return rows[1]

def winner():
    from compare import load
    return choose([load(row,'A') for row in jobs('A')])
