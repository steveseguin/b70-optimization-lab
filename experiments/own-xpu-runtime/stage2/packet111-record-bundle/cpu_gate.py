"""Four compositions, only the two new dimensions; no broad ancestor sweeps."""
import gzip,hashlib,json,subprocess,sys
from build_engine import P,ROOT,sha,save,limits
from bundle_selection import views,choices

def main():
 limits()
 for script in ('head_cpu_gate.py','fusion_cpu_gate.py','reset_regression.py'):
  subprocess.run([sys.executable,'-B',str(P/script)],stdin=subprocess.DEVNULL,check=True)
 head=json.loads((P/'evidence/head-byte-identity.json').read_text());fusion=json.loads((P/'evidence/fusion-byte-identity.json').read_text());reset=json.loads((P/'evidence/reset-regression.json').read_text())
 sources={**head['sources'],**fusion['sources'],**reset['sources']};rows={}
 for label,v in views().items():
  runs=[]
  for compiler in ('GNU','Intel'):
   for repeat in (1,2):
    h=next(r for r in head['runs'] if r['compiler']==compiler and r['repeat']==repeat)
    f=next(r for r in fusion['runs'] if r['compiler']==compiler and r['repeat']==repeat-1)
    raw=gzip.decompress((ROOT/h['fixture']).read_bytes())+gzip.decompress((ROOT/f['artifact']).read_bytes())
    path=P/'evidence'/('joint-'+compiler+'-'+str(repeat)+'.bin.gz');path.write_bytes(gzip.compress(raw,mtime=0));digest=hashlib.sha256(raw).hexdigest()
    runs.append(dict(compiler=compiler,repeat=repeat,fixture=str(path.relative_to(ROOT)),fixture_sha256=sha(path),expected_sha256=digest,candidate_sha256=digest,head=h,fusion=f))
  rows[label]=dict(choices=choices(*v),runs=runs)
 for n in ('cpu_gate.py','head_cpu_gate.py','fusion_cpu_gate.py','reset_regression.py'):
  sources[str((P/n).relative_to(ROOT))]=sha(P/n)
 save(P/'evidence/cpu-byte-identity.json',dict(passed=True,device_executed=False,views=rows,sources=sources,scope='Each new dimension uses the actual compiled local kernel bodies; all four real-shape integration paths are checked separately.'))
if __name__=='__main__':main()
