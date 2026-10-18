"""Factor unchanged DOWN byte proof from packet100; snapshot its receipt locally."""
import gzip,hashlib,json
from build_engine import P,ROOT,sha,save
from chain_seal import check_map
BASE=P.parent/'packet100-down-locality'

def verify():
 snapshot=P/'evidence/down-parent-byte-identity.json'
 row=json.loads(snapshot.read_text());assert row['passed'] and not row['device_executed']
 # Receipt snapshot preserves original provenance; sources and bytes are immutable.
 check_map(ROOT,row['sources'])
 bound={str(snapshot.relative_to(ROOT)):sha(snapshot),str((P/'down_proof104b.py').relative_to(ROOT)):sha(P/'down_proof104b.py')}
 matched={}
 for n,h in row['sources'].items():
  f=ROOT/n
  if f.is_relative_to(BASE) and f.suffix in ('.hpp','.cpp'):
   local=P/f.relative_to(BASE);assert local.is_file() and sha(local)==h,local
   matched[str(local.relative_to(ROOT))]=h
 assert str((P/'p100_down.hpp').relative_to(ROOT)) in matched
 # Do not seal a parent Python gate/receipt, whose packaging can change later.
 bound.update({n:h for n,h in row['sources'].items() if n.endswith(('.hpp','.cpp'))});bound.update(matched)
 selected=row['views']['down-tile16'];assert selected['passed']
 assert {(r['compiler'],r['repeat']) for r in selected['runs']}=={(c,r) for c in ('GNU','Intel') for r in (1,2)}
 for r in selected['runs']:
  assert r['cases']==36 and r['half_patterns']==65536 and r['layout_bytes_checked']==167961600
  f=ROOT/r['raw_evidence'];assert sha(f)==r['raw_evidence_sha256']
  assert hashlib.sha256(gzip.decompress(f.read_bytes())).hexdigest()==r['expected_sha256']==r['candidate_sha256']
  bound[r['raw_evidence']]=sha(f)
  f=ROOT/r['cases_path'];assert sha(f)==r['cases_sha256'];bound[r['cases_path']]=sha(f)
 return dict(passed=True,device_executed=False,sources=bound,scope='unchanged DOWN kernel source and GNU/Intel repeated byte proof; new gate/up tested separately; composition dispatch/allocation tested in packet104b')
if __name__=='__main__':
 source=BASE/'evidence/cpu-byte-identity.json';dest=P/'evidence/down-parent-byte-identity.json'
 if not dest.exists():dest.write_bytes(source.read_bytes())
 save(P/'evidence/down-proof104b.json',verify());print('immutable DOWN byte proof bound')
