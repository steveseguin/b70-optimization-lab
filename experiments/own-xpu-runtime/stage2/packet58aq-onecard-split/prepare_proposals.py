import json,hashlib
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3];Q=P/'screen';OPS=P.parents[1]/'ops'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 parent=json.loads(next(x for x in (OPS/'lane-queue/proposed-p58aj-v5-A.txt').read_text().splitlines() if x.startswith('{')))
 for tag,arm in [('split','resident'),('smoke','smoke')]:
  row=json.loads(json.dumps(parent));row['name']='packet58aq-'+tag+'-A'
  row['argv']=[a.replace('packet58aj-onecard-resident','packet58aq-onecard-split').replace('card0-58ajb-screen-a','card0-58aq-split-a') for a in row['argv']]
  row['argv'][row['argv'].index('--arm')+1]=arm
  row['argv'][row['argv'].index('--output')+1]=str(Q/'evidence/card0-58aq-split-a'/arm)
  row['review']=str((Q/'fault_review.py').relative_to(ROOT))
  row['planned_write_bytes']=100_000_000 if tag=='split' else 50_000_000
  row['plan']['entry_rehearsal']['binaries']=[dict(path=str((P/'build/device/own-rt-iq3').relative_to(ROOT)),sha256=sha(P/'build/device/own-rt-iq3'),args=['--help'],returncode=0,contains='--publication-diagnostic'),dict(path=str((P/'build/device/p58-cache-fixtures').relative_to(ROOT)),sha256=sha(P/'build/device/p58-cache-fixtures'),args=['--help'],returncode=0,contains='--iterations')]
  row['plan']['entry_rehearsal']['timing_evidence']=[str((P/'lineage/parent-device/run/cold-start.json').relative_to(ROOT))]
  row['plan']['entry_rehearsal']['preparation_probe_note']='Private CPU device-define probe runs the actual six arms and 72 resets with real host sensors; see packet58aq-onecard-split/evidence/preparation.json.'
  proposal=OPS/'lane-queue'/('proposed-p58aq-'+tag+'-A.txt')
  proposal.write_text('# PROPOSAL ONLY; whole-host one-card lane A; coordinator holds PAUSE-B. No automatic queue insertion.\n# Split is ONE load and includes its opening exact control; optional smoke is not a split prerequisite.\n'+json.dumps(row)+'\n')
  (Q/'proposals'/proposal.name).write_bytes(proposal.read_bytes())
if __name__=='__main__':main()
