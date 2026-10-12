#!/usr/bin/env python3
"""Arithmetic-preserving offline backend option probes, no device operations."""
import json,os,subprocess
from pathlib import Path
import analyze
P=Path(__file__).resolve().parent;B=P/'build'
def main():
 spv=next(B.glob('*526529.spv'));rows=[]
 for name,options in [('grf256','-ze-opt-level=O2 -cl-fp32-correctly-rounded-divide-sqrt -cl-intel-256-GRF-per-thread'),('opt_disabled','-cl-opt-disable -cl-fp32-correctly-rounded-divide-sqrt')]:
  dump=B/('options-'+name);argv=['/usr/bin/ocloc','compile','-spirv_input','-file',str(spv),'-device','0xe223','-revision_id','0','-options',options,'-out_dir',str(B/('option-bin-'+name))]
  env={k:v for k,v in os.environ.items() if not k.startswith(('IGC_','NEO_','SYCL_','UR_','ZE_'))};env.update(IGC_ShaderDumpEnable='1',IGC_DumpToCustomDir=str(dump),IGC_ShowFullVectorsInShaderDumps='1')
  r=subprocess.run(argv,env=env,capture_output=True,text=True);(B/('option-'+name+'.log')).write_text(r.stdout+r.stderr)
  kernels=[analyze.parse(f) for f in dump.glob('*entry*.asm') if 'Intel_Symbol_Table' not in f.read_text().splitlines()[0]]
  rows.append(dict(name=name,argv=argv,returncode=r.returncode,log=r.stdout+r.stderr,kernels=kernels))
 (P/'option-study.json').write_text(json.dumps(rows,separators=(',',':'))+'\n')
 print([(r['name'],r['returncode'],[(k['instructions'],k['memory_messages'],k['grf']) for k in r['kernels']]) for r in rows])
if __name__=='__main__':main()
