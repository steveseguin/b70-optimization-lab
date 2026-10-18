"""Remove only this packet's generated fixture payload scratch after receipts."""
import gzip,json,shutil
from build_engine import P,ROOT,B,sha,save,limits

def main():
 limits();shape=json.loads((P/'evidence/full-shape.json').read_text());admission=json.loads((P/'evidence/full-shape-admission.json').read_text());assert shape['passed'] and admission['passed']
 scratch=B/'full-shape';removed=[];retained=[]
 for row in shape['runs']:
  out=scratch/row['view']/str(row['rank'])
  for key,leaf in (('census','census.json'),('native_plan','native-plan.json')):
   archive=ROOT/row[key];assert sha(archive)==row[key+'_sha256'];assert gzip.decompress(archive.read_bytes())==(out/leaf).read_bytes()
  for leaf in ('run.log','result.json','selected-operations.txt'):
   archive=P/'evidence'/(row['view']+'-'+str(row['rank'])+'-'+leaf+'.gz');archive.write_bytes(gzip.compress((out/leaf).read_bytes(),mtime=0));retained.append(dict(path=str(archive.relative_to(ROOT)),sha256=sha(archive)))
 for d in scratch.iterdir():
  if d.is_dir():
   assert not d.is_symlink();removed.append(str(d.relative_to(ROOT)));shutil.rmtree(d)
 save(P/'evidence/fixture-cleanup.json',dict(passed=True,device_executed=False,removed_directories=removed,retained=retained,scope='only packet95 fixture payload scratch; generated sources and fixture binary retained for seals'))
 print('retained and removed fixture scratch:',len(removed),'directories')
if __name__=='__main__':main()
