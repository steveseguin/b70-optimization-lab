"""The exact W0p rank path under both host-only compilers, 1000 exchanges."""
import json,shutil,time
from pipeline import P,parser,Transport,CANARY,SLOT,struct,save,sha
from cpu_gates import host
rows=[]
for compiler in ('gnu-host','icpx-host'):
 binary=P/'build'/compiler/'own-rt-iq3';host(binary)
 out=P/'build'/f'canary-host-{compiler}-{time.time_ns()}';out.mkdir()
 a=parser().parse_args(['--binary',str(binary),'--output',str(out),'--mini','--seconds','300']);a.canary=True
 t=Transport(a,out)
 try:
  for i in range(1000):
   for rank in (0,1):
    t.mapping[rank*SLOT:rank*SLOT+256]=struct.pack('<64I',*([i]*64));t.start(rank,CANARY,position=i)
   assert all(p.poll() is None for p in t.children)
   t.wait(0);t.wait(1)
   for rank in (0,1):assert t.mapping[rank*SLOT:rank*SLOT+256]==struct.pack('<64I',*([i+1]*64))
  t.close(True)
 except Exception as error:
  t.stop(error);t.close(False);raise
 rows.append(dict(compiler=compiler,binary_sha256=sha(binary),handovers=1000,kernels_per_rank=1000,
  native_receipts=[json.loads((out/f'rank{i}/receipt.json').read_text()) for i in (0,1)],ownership=json.loads((out/'ownership.json').read_text())))
 shutil.rmtree(out)
save(P/'canary-host-gates.json',dict(passed=True,device_executed=False,rows=rows))
print('two compilers, two ranks each, 1000 exchanges each PASS')
