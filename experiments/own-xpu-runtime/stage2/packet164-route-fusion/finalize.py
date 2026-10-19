"""Write documentary queue rows and source pins only; never import lanequeue."""
import hashlib
import json
from capture import P, ROOT, S, guard


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    guard()
    sources=[
        'packet73-hc-experts2/DO-NOT-REPEAT.md','packet78-small-kernels/DO-NOT-REPEAT.md',
        'packet109-other-fusion/DO-NOT-REPEAT.md','packet112-route-select/DO-NOT-REPEAT.md',
        'packet33-codegen/DO-NOT-REPEAT.md','packet140-body-lever/DO-NOT-REPEAT.md',
        'packet141-transfer-gap/DO-NOT-REPEAT.md','packet147-lever-synthesis/PLAN.md',
        'packet141-transfer-gap/p109_route.hpp','packet141-transfer-gap/engine_fusion.hpp',
        'packet141-transfer-gap/route42.hpp','packet141-transfer-gap/p39_plan.hpp',
        'packet141-transfer-gap/p49d_small.hpp','packet58aj-onecard-resident/README.md',
        'packet58aj-onecard-resident/WINDOW.md',
    ]
    notes=['2026-10-17-own-runtime-packet73.md','2026-10-17-own-runtime-packet78.md',
           '2026-10-18-own-runtime-packet109.md','2026-10-18-own-runtime-packet112-micro-result.md',
           '2026-10-18-own-runtime-packet141-result.md','2026-10-19-own-runtime-packet58aj-result.md']
    pins={str(p.relative_to(ROOT)):sha(p) for p in [*[S/s for s in sources],*[ROOT/'notes'/s for s in notes]]}
    rows=[];provenance=[]
    for arm,tag in [('smoke','smoke'),('resident','v5')]:
        path=ROOT/f'experiments/own-xpu-runtime/ops/lane-queue/proposed-p58aj-{tag}-A.txt'
        original=[json.loads(line) for line in path.read_text().splitlines() if line.startswith('{')]
        assert len(original)==1
        row=json.loads(json.dumps(original[0]))
        row['name']=f'packet164-onecard-{tag}-A'
        argv=row['argv']
        old='experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident'
        new='experiments/own-xpu-runtime/stage2/packet164-route-fusion/onecard'
        row['argv']=[s.replace(old,new) for s in argv]
        row['argv'][row['argv'].index('--output')+1]=str(P/f'onecard/screen/evidence/card0-p164-screen-a/{arm}')
        row['review']=row['review'].replace(old,new)
        # Keep the real historical evidence path, never copy stale binary pins
        # or claim a successful rehearsal of the nonexistent future binary.
        row['plan']={'entry_rehearsal':{'timing_evidence':original[0]['plan']['entry_rehearsal']['timing_evidence']}}
        rows.append(row)
        provenance.append(dict(source=str(path.relative_to(ROOT)),sha256=sha(path),source_row=original[0],
                               status='documentary future build contract; private entry absent; pins and rehearsal required'))
        pins[str(path.relative_to(ROOT))]=sha(path)
    (P/'briefs/lanequeue-rows.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
    (P/'briefs/queue-row-provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
    (P/'evidence/source-pins.json').write_text(json.dumps(pins,indent=2)+'\n')
    print('Pinned decision sources and retained two documentary lanequeue rows; no queue access.')


if __name__=='__main__':main()
