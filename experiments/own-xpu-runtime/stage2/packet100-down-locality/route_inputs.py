"""Recover only SHA256-matching route bytes from existing receipt inventories.
Missing raw bytes are an explicit blocker, never replaced by synthetic routes.
"""
import argparse,gzip,hashlib,json,struct
from pathlib import Path
from build_engine import P,ROOT,sha,save,limits
S=ROOT/'experiments/own-xpu-runtime/stage2/screen/v4-lanes/evidence'
ORIGINS=('packet77-attribution-B-a/run/attribution','packet86-B-a/production/run/attribution')
def inventory():
 sources={};rows=[]
 for origin in ORIGINS:
  for archive in sorted((S/origin).glob('*/state-evidence.json.gz')):
   sources[str(archive.relative_to(ROOT))]=sha(archive)
   for f in json.loads(gzip.decompress(archive.read_bytes()))['files']:
    if f['path'].endswith('.routes.down.bin'):
     assert f['bytes']==120
     rows.append(dict(origin=origin,prompt=archive.parent.name,receipt=str(archive.relative_to(ROOT)),path=f['path'],sha256=f['sha256'],bytes=f['bytes']))
 assert rows and len(sources)==24,(len(rows),len(sources))
 return rows,sources

def make(raw_paths):
 rows,sources=inventory();wanted={r['sha256'] for r in rows};found={};searched=0
 for f in raw_paths:
  if not f.is_file() or f.stat().st_size!=120:continue
  searched+=1;raw=f.read_bytes();digest=hashlib.sha256(raw).hexdigest()
  if digest in wanted:found[digest]=raw
 offsets={};packed=bytearray()
 for digest in sorted(found):
  offsets[digest]=len(packed);packed+=found[digest]
 for row in rows:
  row['available']=row['sha256'] in found
  if row['available']:
   raw=found[row['sha256']];route=list(struct.iter_unpack('<III',raw))
   if not all(0<=e<512 and begin==0 and count==2560 for e,begin,count in route):raise ValueError('non-full-shape receipt route')
   row.update(offset=offsets[row['sha256']],expert_ids=[r[0] for r in route])
 complete=all(r['available'] for r in rows)
 sources[str((P/'route_inputs.py').relative_to(ROOT))]=sha(P/'route_inputs.py')
 report=dict(schema='packet100.receipt-routes.v1',passed=True,device_executed=False,ready=complete,rows=rows,sources=sources,raw_files_examined=searched,unique_hashes=len(wanted),recovered_hashes=len(found),missing_rows=sum(not r['available'] for r in rows),reason=None if complete else 'Receipt archives retained route hashes only; matching raw vectors not found. Real-route microbenchmark blocked.',distribution_scope='final retained per-layer state, all 12 fixed prompts, both ranks, packet77 and packet86 production; not a complete per-token route trace')
 if complete:
  (P/'evidence/routes.bin').write_bytes(packed);report['route_bytes_sha256']=sha(P/'evidence/routes.bin')
 save(P/'evidence/route-inputs.json',report);return report

def require_ready():
 row=json.loads((P/'evidence/route-inputs.json').read_text())
 for name,h in row['sources'].items():
  if sha(ROOT/name)!=h:raise ValueError('route source changed')
 if not row['ready']:raise ValueError(row['reason'])
 expected,sources=inventory()
 keys=('origin','prompt','receipt','path','sha256','bytes')
 if [{k:r[k] for k in keys} for r in row['rows']]!=expected:raise ValueError('route inventory incomplete or altered')
 if any(row['sources'].get(k)!=h for k,h in sources.items()):raise ValueError('route receipt source differs')
 raw=(P/'evidence/routes.bin').read_bytes()
 if len(raw)!=120*len({r['sha256'] for r in expected}):raise ValueError('deduplicated complete routes required')
 if hashlib.sha256(raw).hexdigest()!=row['route_bytes_sha256']:raise ValueError('route payload changed')
 for r in row['rows']:
  if hashlib.sha256(raw[r['offset']:r['offset']+120]).hexdigest()!=r['sha256']:raise ValueError('route payload not receipt-bound')
 return row

def main():
 limits();ap=argparse.ArgumentParser();ap.add_argument('--raw-root',type=Path);ap.add_argument('--path-list',type=Path);args=ap.parse_args()
 paths=list(args.raw_root.rglob('*.routes.down.bin')) if args.raw_root else []
 if args.path_list:paths.extend(Path(s) for s in args.path_list.read_text().splitlines())
 row=make(paths);print(json.dumps({k:row[k] for k in ('ready','raw_files_examined','unique_hashes','recovered_hashes','missing_rows','reason')},indent=2))
if __name__=='__main__':main()
