"""All eleven inherited window parsers/startups, both selections; CPU only."""
import gzip,json,os,shutil,time
from types import SimpleNamespace
from unittest.mock import patch
from build131 import P,ROOT,B,BASE,sha,save,cpu_main,limits
def main():
 try:
  prior=json.loads((P/'evidence/startup131.json').read_text());assert prior['passed'] and prior['total_windows']==22
  for path,h in prior['sources'].items():assert sha(ROOT/path)==h
  assert sha(ROOT/prior['archive'])==prior['archive_sha256']
 except (OSError,KeyError,AssertionError):pass
 else:print('Unchanged 22-window startup receipt and fixture verified');return
 import startup103 as g
 import window as w
 from kd_reference import prepare,command
 if not (B/'input').exists():(B/'input').symlink_to(os.readlink(BASE/'build/input'))
 generated,commands=g.build()
 # K0/K1/K2 contain no selected snapshot engine. Run their unchanged frozen
 # CPU fixtures, redirecting every output to this packet's scratch.
 with patch.object(w,'B',BASE/'build'):shared=g.shared_fixtures()
 rows=[]
 for view in ('control','candidate'):
  target=P/'selections'/view/'selection.json'
  dest=g.S/('canary-'+view);dest.mkdir()
  args=g.model_args('W0p',target,dest);args.device=False;args.binary=B/'gnu-host/own-rt-iq3'
  watch=SimpleNamespace(check=lambda:None,mark_launched=lambda pid:None,latch=lambda error:None)
  w.concurrency_canary(args,dest,{'PATH':'/usr/bin:/bin','OMP_NUM_THREADS':'2'},watch)
  shared['W0p-'+view]=dict(passed=True,files={str(f.relative_to(dest)):sha(f) for f in dest.rglob('*') if f.is_file()});shutil.rmtree(dest)
  ref,binding=prepare(target,sha(target),g.S)
  inp=json.loads((B/'input/input.json').read_text());a=SimpleNamespace(card=0,draft_rank=1,context=4096,input=B/'input',dispatch=P/'dispatch-speed6.json')
  for name in g.WINDOWS:
   g.window_options(name);row=dict(view=view,window=name)
   if name in shared:row['shared_fixture']=name
   elif name=='KD':
    row['host']=g.native(command(B/'unused',a,P/'oracle/results/capture-incident-retrospective.tsv',inp,g.S/'scratch',ref,binding['reference_selection_sha256'],-1))
    row['device_arguments_on_cpu']=g.native(command(B/'unused',a,P/'oracle/results/capture-incident-retrospective.tsv',inp,g.S/'scratch',ref,binding['reference_selection_sha256'],-1,device=True))
   else:row['ranks']=[g.native(cmd) for cmd in g.rank_commands(name,target)]
   rows.append(row)
  print(view,'all eleven inherited window startups PASS',flush=True)
 sources={str(f.relative_to(ROOT)):sha(f) for f in [P/'startup131.py',P/'startup103.py',P/'kd_reference.py',P/'window.py',P/'queue_runner.py',P/'chain_pipeline.py',*(P/'selections'/v/'selection.json' for v in ('control','candidate')),*generated,g.S/'fixture']}
 row=dict(passed=True,device_executed=False,windows_per_view=11,total_windows=22,runs=rows,shared=shared,sources=sources,commands=commands)
 archive=P/'evidence/startup131.json.gz';archive.write_bytes(gzip.compress(json.dumps(row,sort_keys=True).encode(),mtime=0))
 save(P/'evidence/startup131.json',dict(passed=True,device_executed=False,total_windows=22,sources=sources,archive=str(archive.relative_to(ROOT)),archive_sha256=sha(archive)))
 limits()
if __name__=='__main__':cpu_main();main()
