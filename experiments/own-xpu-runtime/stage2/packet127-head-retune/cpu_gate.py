"""Actual head/argmax/merge bytes and reset repair, both compilers, all views."""
import gzip,hashlib,json,subprocess,sys
from build_engine import P,ROOT,sha,save,limits
from bundle_selection import views,choices,suffix_rows

def main():
 limits()
 for script in ('head_cpu_gate.py','reset_regression.py'):
  subprocess.run([sys.executable,'-B',str(P/script)],stdin=subprocess.DEVNULL,check=True)
 head=json.loads((P/'evidence/head-byte-identity.json').read_text())
 reset=json.loads((P/'evidence/reset-regression.json').read_text())
 assert head['passed'] and reset['passed']
 sources={**head['sources'],**reset['sources']};rows={}
 for label,v in views().items():
  runs=[];suffix=suffix_rows(v)
  for compiler in ('GNU','Intel'):
   for repeat in (1,2):
    h=next(r for r in head['runs'] if (r['compiler'],r['repeat'],r['suffix_rows'])==(compiler,repeat,suffix))
    r=next(r for r in reset['runs'] if (r['compiler'],r['repeat'],r['suffix_rows'])==(compiler,repeat,suffix))
    assert r['result']['passed'] and r['result']['fixed_exact_cases']==21 and r['result']['negative_control_mismatches']==6
    runs.append(dict(h,reset=r))
  rows[label]=dict(choices=choices(*v),suffix_rows=suffix,runs=runs)
 for n in ('cpu_gate.py','head_cpu_gate.py','reset_regression.py','bundle_selection.py'):
  sources[str((P/n).relative_to(ROOT))]=sha(P/n)
 save(P/'evidence/cpu-byte-identity.json',dict(passed=True,device_executed=False,views=rows,sources=sources,scope='Full vocabulary production head vs selected partitions, full logit bytes, finite argmax payloads, forced ties/nonfinite refusal and real reset repair. Unchanged bundle operations covered by all-window startup; device model exactness pending.'))
if __name__=='__main__':main()
