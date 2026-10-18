"""Verify already archived full-shape evidence; refuse leftover payload scratch."""
import json,gzip
from build_engine import P,ROOT,B,sha,save,limits
def main():
 limits();shape=json.loads((P/'evidence/full-shape.json').read_text());assert shape['passed']
 retained=[]
 for row in shape['runs']:
  for artifact in row['artifacts'].values():
   p=ROOT/artifact['path'];assert sha(p)==artifact['sha256'];gzip.decompress(p.read_bytes());retained.append(artifact)
 assert not (B/'full-shape/scratch').exists()
 save(P/'evidence/fixture-cleanup.json',dict(passed=True,device_executed=False,retained=retained,scope='Full-shape payload scratch archived then deleted after each run; fixture binary and generated source retained.'))
if __name__=='__main__':main()
