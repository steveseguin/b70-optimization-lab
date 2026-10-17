"""Bind only the reviewed allocation delta and fresh CPU proof to seal 6."""
import json,os
from pathlib import Path
P=Path(__file__).resolve().parent;E=P/'evidence/speed6'
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
 import speed6_qualification as s6,seal6_amendment as amendment
 row=json.loads((P/'seal6-amendment.json').read_text());row['speed6_extension']=s6.verify()
 row['speed6_files']=[*s6.PINS,*[p.name for p in sorted(P.glob('speed6_*.py'))],'test_speed6.py','speed6-plan-gates.json','speed6-snapshot-gates.json','speed6-memory-gates.json','SPEED6-CLOSEOUT.md','evidence/speed6/']
 clause=' SPEED6, owner directive 2026-10-15: exact source-pinned arena admission and parallel split23/dr1/4K scratch allocation repair only. Production-size sparse owner checks and mini full-state comparisons are fresh; the immutable device suite oracle remains real-model exactness authority. No new arithmetic, dispatch or real-model CPU run.'
 if clause not in row['justification']:row['justification']+=clause
 row['qualification_sources_sha256']={n:s6.sha(P/n) for n in amendment.QUALIFICATION_SOURCES}
 (P/'seal6-amendment.json').write_text(json.dumps(row,indent=2)+'\n')
 amendment.verify()
 import speed4_finalize as prior
 prior.E=E;prior.tests()
 print('SPEED6 amendment and source-binding tests passed; seal and detached admission required')
if __name__=='__main__':main()
