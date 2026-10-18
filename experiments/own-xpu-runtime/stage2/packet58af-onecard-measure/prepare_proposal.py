"""Write the single unqueued proposal from this build's actual native hashes."""
import json,resource
from build_engine import P,ROOT,sha,save,limits

def main():
    limits()
    proposal=P.parents[1]/'ops/lane-queue/proposed-p58af-measure-A.txt'
    library=json.loads((P/'library-path.json').read_text())['LD_LIBRARY_PATH']
    artifacts=json.loads((P/'evidence/build-measure.json').read_text())['artifacts']
    binaries=[]
    for name in ('own-rt-iq3','p58-cache-fixtures'):
        rel='build/device/'+name;assert sha(P/rel)==artifacts[rel]
        row=dict(path=str((P/rel).relative_to(ROOT)),sha256=artifacts[rel])
        if name=='p58-cache-fixtures':row.update(args=['--help'],returncode=1,contains='K1 unknown option')
        binaries.append(row)
    job=dict(name='packet58af-measure-A',lane='A',
        argv=['/usr/bin/python3','-B',str((P/'entry.py').relative_to(ROOT)),'--kind','bracket','--lane','A',
            '--output',str(P/'evidence/card0-measure-a/combined'),'--fault-review','{REVIEW}',
            '--library-path',library,'--authorized-device-window'],env_extra={},
        review=str((P/'fault_review.py').relative_to(ROOT)),plan=dict(entry_rehearsal=dict(binaries=binaries)))
    comments='''# PROPOSAL ONLY, unqueued. Require READY-FOR-DEVICE.json and its sealed CPU gates.
# One card 0, lane A, whole host, existing packet58ab hold only.
# One model load: A0 off, B0 publication, A1 off, B1 resident/miss, A2 off.
# Each view: 12 x 64, every token checked against packet49 iq3-p49-split32-v1.
# Total active budget <=900 s including two K1 fixtures and 90 s drain gaps.
# Deadline requests graceful termination; no hard kill or retry.
# Full BF16 KV, tile16, max cache, overlap. Diagnostic only; overhead must be <2%.
'''
    raw=comments+json.dumps(job)+'\n'
    (P/'proposals'/proposal.name).write_text(raw)
    proposal.write_text(raw)

if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
