"""Exact E2 growth from frozen packet90 real arena censuses; no allocations."""
import gzip,json
from build_engine import P,ROOT,sha,save,limits
BASE=P.parent/'packet90-expert-hc'
def main():
 limits();rows=[];sources={str((P/'e2_memory.py').relative_to(ROOT)):sha(P/'e2_memory.py')}
 for rank in (0,1):
  path=BASE/'evidence'/f'exp-halfcache-{rank}-census.json.gz';sources[str(path.relative_to(ROOT))]=sha(path)
  c=json.loads(gzip.decompress(path.read_bytes()))
  tensors=[r for r in c['allocations'] if r['live'] and r['memory']=='device' and r['label'].startswith('card0:weight:blk.') and r['label'].endswith(('.ffn_gate_exps.weight','.ffn_up_exps.weight')) and r['bytes']==512*640*840]
  assert len(tensors)==(46 if rank==0 else 48)
  blocks=len(tensors)*512*640*10;per_layer=2*512*640*10
  headroom=30*1024**3-c['totals']['device'];growth=blocks*(16*4-4)
  assert growth>headroom
  prod_headroom=headroom+blocks*2
  rows.append(dict(rank=rank,tensor_labels=[r['label'] for r in tensors],iq2_tensors=len(tensors),blocks=blocks,blocks_per_layer=per_layer,e1_arena_bytes=c['totals']['device'],e1_headroom_bytes=headroom,e2_growth_over_e1_bytes=growth,e2_arena_bytes=c['totals']['device']+growth,e2_excess_bytes=growth-headroom,e2_growth_over_production_bytes=blocks*62,production_headroom_bytes=prod_headroom,max_layers_e1_elsewhere=headroom//(per_layer*60),max_layers_production_elsewhere=prod_headroom//(per_layer*62),e2_growth_over_e1_without_redundant_nibbles_bytes=blocks*52))
 assert rows[1]['e1_headroom_bytes']==630519094
 save(P/'evidence/e2-memory.json',dict(passed=True,device_executed=False,decision='closed: full E2 fails both arenas; bounded hottest-layer ranking absent',arena_limit_bytes=30*1024**3,rows=rows,sources=sources))
 print('E2 no-fit proof PASS:',[(r['rank'],r['e2_growth_over_e1_bytes'],r['e1_headroom_bytes']) for r in rows])
if __name__=='__main__':main()
