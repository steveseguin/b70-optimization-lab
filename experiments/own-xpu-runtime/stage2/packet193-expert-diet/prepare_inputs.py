"""Bind the parent inputs read in place (never pins): packet100b's 384 real routes, packet162b's real rows,
packet192's device analysis (the production control datums), packet110 floors. Writes lineage-inputs/.

routes-p100b.json is derived from packet100b/evidence/routes.bin exactly as packet192 derived it (384 x 10
expert ids; gate/up uses row_count 640, down 2560) and must hash identically to packet192's copy.
"""
import json,struct
from build_engine import P,ROOT,P100B,P162,P110,P192,LINEAGE,EV,limits,sha,parent,save
EXPECTED={'routes.bin':'01c8c616990f4dc406f497c9c14da5920aa1b49326ff312a5c2c82a32856c605','route-inputs.json':'f91ad7fd56d87eeecfb5f3abf1b01eb6260f72d5513f99e4e6237714fccd2973',
          'layer0.bin':'eeed9d3bab0c8652c344d363174032c1f197944e7314cdf73fe974493ebc6628','layer24.bin':'77bdd24006f6f5425b32e78ddfc50e34faa670b5b655070c4c59ed25aa35f52b'}
def main():
 limits();LINEAGE.mkdir(exist_ok=True);EV.mkdir(exist_ok=True)
 routes_bin=P100B/'evidence/routes.bin';manifest=P100B/'evidence/route-inputs.json'
 assert sha(routes_bin)==EXPECTED['routes.bin'] and sha(manifest)==EXPECTED['route-inputs.json'],'packet100b route identity changed'
 raw=routes_bin.read_bytes();assert len(raw)==384*120
 rows=[]
 for r in range(384):
  trip=[struct.unpack_from('<III',raw,r*120+i*12) for i in range(10)]
  assert all(b==0 and c==2560 and e<512 for e,b,c in trip),'full real route shape required'
  rows.append([e for e,_,_ in trip])
 man=json.loads(manifest.read_text());assert man['micro_route_vectors']==384 and man['route_bytes_sha256']==EXPECTED['routes.bin']
 routes=dict(schema='packet192.routes.v1',parent_relpath=str(routes_bin.relative_to(ROOT)),parent_digest=sha(routes_bin),manifest_relpath=str(manifest.relative_to(ROOT)),manifest_digest=sha(manifest),
  route_count=384,experts=512,down_rows=2560,gateup_rows=640,note='expert ids of packet100b fixtures 1/16/32/64, every layer, both ranks, both prompts; gate/up uses the same ids with row_count 640',routes=rows)
 (LINEAGE/'routes-p100b.json').write_text(json.dumps(routes,separators=(',',':'))+'\n')
 p192_routes=P192/'lineage-inputs/routes-p100b.json';assert sha(LINEAGE/'routes-p100b.json')==sha(p192_routes),'routes json differs from packet192 derivation'
 real=P162/'build/micro-inputs';assert sha(real/'layer0.bin')==EXPECTED['layer0.bin'] and sha(real/'layer24.bin')==EXPECTED['layer24.bin'],'packet162b real rows changed'
 analysis=P192/'evidence/issue-floor-B1/analysis.json';a=json.loads(analysis.read_text());assert a['passed'] and a['verdict']=='measured'
 controls={k:dict(cold_us=a['kernels'][k]['strata']['cold']['median_us'],warm_us=a['kernels'][k]['strata']['warm']['median_us']) for k in ('gateup','down')}
 parents=[parent('packet100b real routes (384 x 10, fixtures 1/16/32/64)',routes_bin),parent('packet100b route manifest',manifest),
  parent('packet162b real gate/up rows layer0 (experts 0-9)',real/'layer0.bin'),parent('packet162b real gate/up rows layer24 (experts (37i+19)%512)',real/'layer24.bin'),
  parent('packet162b inputs receipt',P162/'evidence/micro-prep/inputs.json'),
  parent('packet192 device analysis (production cold/warm control datums, follow-on bars)',analysis),
  parent('packet192 device samples (production stream, different schema; analyzer must refuse it)',P192/'evidence/issue-floor-B1/samples.jsonl'),
  parent('packet192 routes json (identical derivation)',p192_routes),
  parent('packet110 class roofline (copy floors 20.08 / 17.28 us; expsact 5.42 us)',P110/'roofline.json')]
 save(LINEAGE/'parent-inputs.json',dict(schema='packet193.parent-inputs.v1',rule='cross-packet files are read in place and verified by digest at plan/run time; they are provenance records, never pin-guard pins',real_rows_dir=str(real.relative_to(ROOT)),routes_json=str((LINEAGE/'routes-p100b.json').relative_to(ROOT)),routes_json_sha256=sha(LINEAGE/'routes-p100b.json'),packet192_controls_us=controls,packet192_follow_on_bars_us={k:a['kernels'][k]['follow_on_bars_us'] for k in ('gateup','down')},parents=parents))
 print('inputs bound: 384 routes;',len(parents),'parent records; controls',controls)
if __name__=='__main__':main()
