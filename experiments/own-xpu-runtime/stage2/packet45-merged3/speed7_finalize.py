"""Bind only the reviewed allocation delta and fresh CPU proof to seal 6."""
import json,os
from pathlib import Path
P=Path(__file__).resolve().parent;E=P/'evidence/speed7'
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
 import speed7_qualification as s7,seal6_amendment as amendment
 row=json.loads((P/'seal6-amendment.json').read_text());row['speed7_extension']=s7.verify()
 row['speed7_files']=[*s7.PINS,*[p.name for p in sorted(P.glob('speed7_*.py'))],'speed7-plan-gates.json','speed7-snapshot-gates.json','speed7-memory-gates.json','speed7-copy-gates.json','SPEED7-CLOSEOUT.md','evidence/speed7/']
 clause=' SPEED7, owner directive 2026-10-15: exact source-pinned 8:1 snapshot batch ratio only; unchanged bytes, allocation, guards and admission. Production-size sparse owner checks and mini full-state comparisons are fresh; the immutable device suite oracle remains real-model exactness authority. No new arithmetic, dispatch or real-model CPU run.'
 if clause not in row['justification']:row['justification']+=clause
 row['qualification_sources_sha256']={n:s7.sha(P/n) for n in amendment.QUALIFICATION_SOURCES}
 (P/'seal6-amendment.json').write_text(json.dumps(row,indent=2)+'\n')
 amendment.verify()
 import speed4_finalize as prior
 prior.E=E;prior.tests()
 print('SPEED7 amendment and source-binding tests passed; seal and detached admission required')
if __name__=='__main__':main()
