#!/usr/bin/env python3
"""Run every complete window wrapper against host binaries; no device binary runs.

The keyword-only CPU seam changes the backend and receipt device flag. Admission
uses a separate coherent miniature seal and read-only hardware mocks. K0 is a
structural shim; K2 must reject its zero CPU device timestamps. No fake speed or
GPU exactness claim is produced. Ordinary failures traverse the final writer.
"""
import argparse,contextlib,copy,hashlib,json,os,shutil,subprocess,sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import pipeline as pp,suite,window,draft_window,storage
P=Path(__file__).resolve().parent;B=P/'build'
SOURCES=('full_wrapper_gate.py','window.py','draft_window.py','capture40.py','pipeline.py','suite.py','suite_metrics.py','fixture_support.py','storage.py','k2_summary.py','compare_controllers.py','window_safety.py','merge_dispatch.py')

def child(binary,args,log):
 pp.require(binary.parent.name=='gnu-host','host-only executable contract')
 with log.open('w') as stream:
  r=subprocess.run(['nice','-n','19','ionice','-c','3',str(binary),*map(str,args)],env={'PATH':'/usr/bin:/bin','OMP_NUM_THREADS':'2'},stdout=stream,stderr=subprocess.STDOUT,timeout=600)
 pp.require(r.returncode==0,'host fixture failed '+str(log)+': '+log.read_text()[-2000:])

def inspect(root):
 return {str(f.relative_to(root)):pp.sha(f) for pattern in ('row-*/*.bf16','row-*/*.bin','draft-final-state/*.bin') for f in root.glob(pattern)}

class CpuWatch(window.Watch):
 fail=False
 def __init__(self,out,boot,seconds):
  super().__init__(out,boot,seconds)
 def check(self):
  if self.fail:raise ValueError('injected wrapper receipt-format failure')
  return super().check()
 def postflight(self):self.check()

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,default=B/'full-wrapper-cpu');a=ap.parse_args()
 pp.require(not a.output.exists(),'fresh wrapper scratch required');storage.admit(64_000_000);a.output.mkdir(parents=True)
 source_sha256={name:pp.sha(P/name) for name in SOURCES}
 root=a.output;seal=root/'seal';seal.mkdir();(seal/'dispatch-p38.json').write_bytes((P/'dispatch-p38.json').read_bytes());binary=B/'gnu-host/own-rt-iq3';rows=[]
 env={'PATH':'/usr/bin:/bin','OMP_NUM_THREADS':'2'}
 if 'LD_LIBRARY_PATH' in os.environ:env['LD_LIBRARY_PATH']=os.environ['LD_LIBRARY_PATH']
 expected={};fixtures={}
 # Independent sequential host baseline for each requested token cap. Its
 # output bytes and final hashes are retained in the gate receipt, then removed.
 for cap in (64,128):
  args=pp.parser().parse_args(['--binary',str(binary),'--mini','--output',str(root/f'baseline{cap}'),'--max-new',str(cap),'--retain-steps','1-8,97-104','--controller','native'])
  result=pp.run(args);expected[cap]=result['tokens']
  fixtures[cap]={str(f.relative_to(args.output/f'rank{rank}')):pp.sha(f) for rank in (0,1) for f in (args.output/f'rank{rank}').glob('step*/layer-*.bf16')}
  pp.save(root/f'baseline{cap}.json',dict(tokens=result['tokens'],fixtures=fixtures[cap],device_executed=False,binary_sha256=pp.sha(binary)))
  shutil.rmtree(args.output)
 # Coherent host fixture output hashes, as the real seal requires.
 fixture=root/'fixture-reference';fixture.mkdir()
 child(B/'gnu-host/nongemv-fixtures',['--validate-only','--fixtures',B/'fusion-fixtures','--dispatch',P/'dispatch-p38.json','--output',fixture/'nongemv'],fixture/'nongemv.log')
 child(B/'gnu-host/p33-linked-fixtures',['--output',fixture/'linked','--seconds','300'],fixture/'linked.log')
 nongemv=json.loads((fixture/'nongemv/receipt.json').read_text());linked=json.loads((fixture/'linked/receipt.json').read_text())
 fixture_digests={'nongemv_fixture_host_sha256':nongemv['output_sha256'],'p33_linked_fixture_host_sha256':linked['output_sha256']}
 shutil.rmtree(fixture)
 inp=seal/'input';inp.mkdir();pp.save(inp/'input.json',dict(tokens=[2,5,3,7,1],files={},model_dir='mini-unused'))
 (seal/'mtp-manifest.tsv').write_bytes((P/'mtp-manifest.tsv').read_bytes());(seal/'memory-plan.json').write_bytes((P/'memory-plan.json').read_bytes())
 # The KD path receives a miniature capture with exactly the same byte binding
 # and selected-dispatch host-reference logic as a real capture.
 captured=B/'captured-incident-retrospective';table=B/'capture-incident-retrospective.tsv'
 # Do not overwrite the real packet's prepared capture. Override KD B with a
 # private tree that links only host binaries, and keeps capture inputs private.
 kd_build=root/'kd-build';kd_build.mkdir();(kd_build/'gnu-host').symlink_to(B/'gnu-host',target_is_directory=True)
 captured=kd_build/'captured-incident-retrospective';captured.mkdir();stream=captured/'streams.bf16';stream.write_bytes(bytes(128))
 table=kd_build/'capture-incident-retrospective.tsv';table.write_text(''.join(f'{pos} {token} 1 {stream.resolve()}\n' for pos,token in enumerate([2,5,3])))
 reference=root/'capture-reference';child(binary,['--mini','--pipeline-mini','--draft-capture',table,'--rank','1','--context','256','--dispatch',P/'dispatch-p38.json','--output',reference,'--seconds','300'],root/'capture-reference.log')
 capture=dict(table_sha256=pp.sha(table),streams={'streams.bf16':pp.sha(stream)})
 pp.save(seal/'capture-input-incident-retrospective.json',capture)
 pp.save(seal/'capture-run-incident-retrospective.json',dict(output=str(reference.resolve()),binary_sha256=pp.sha(binary),table_sha256=pp.sha(table)))
 artifacts={f'gnu-host/{name}':pp.sha(B/'gnu-host'/name) for name in ('own-rt-iq3','nongemv-fixtures','p33-linked-fixtures','k2-fixtures')}
 build=dict(passed=True,sources={},artifacts_sha256=artifacts,official_manifest_sha256=pp.sha(seal/'mtp-manifest.tsv'),memory_plan=json.loads((seal/'memory-plan.json').read_text()),
  input_sha256=pp.sha(inp/'input.json'),cpu_tests_sha256=pp.sha(P/'cpu-tests.json'),**fixture_digests,
  draft_capture_fixture_sha256={'incident-retrospective':inspect(reference)},draft_capture_input_sha256={'incident-retrospective':pp.sha(seal/'capture-input-incident-retrospective.json')})
 pp.save(seal/'build-receipt.json',build)
 manifests={}
 for cap in (64,128):
  manifests[cap]=root/f'manifest{cap}.json';pp.save(manifests[cap],dict(arithmetic='iq3-p17-detmath-v2',token_cap=cap,context=256,complete=False,prompts=[dict(prompt_id=name,input_bundle='mini-unused',mini_tokens=tokens,mini_count=cap) for name,tokens in [('code-review',[2,5,3,7,1]),('customer-email',[1,2,1])]]))
 def oracle(a,inp,steps):
  return {key:value for key,value in fixtures[a.max_new].items() if int(key.split('/')[0][4:]) in steps},expected[a.max_new]
 success={};dispatch=seal/'dispatch-p38.json'
 sequence=['K0','K1a','K1b','K2','W0p','KD','W2m-exact','WS64x','WS128x','WSs-exact']+[n for n in window.CONFIG if n not in {'K0','K1a','K1b','K2','W0p','KD','W2m-exact','WS64x','WS128x'}]
 with contextlib.ExitStack() as stack:
  for module,name,value in ((window,'P',seal),(window,'B',B),(draft_window,'P',seal),(draft_window,'B',kd_build),
   (window,'environment_gate',lambda:dict(native=env)),(window,'memory_snapshot',lambda:dict(MemAvailable=128*1024**3)),
   (window,'foreign_engines',lambda:dict(scope='CPU admission mock; no DRM access')),(window,'journal',lambda *args:('','cpu-cursor')),
   (window,'Watch',CpuWatch),(window,'selected_oracle',oracle)):
   stack.enter_context(patch.object(module,name,value))
  for label in sequence:
   name='WSs' if label=='WSs-exact' else label;cap=128 if name.startswith('WS128') else 64
   output=seal/label
   argv=['window.py','--authorized-device-window','--window',name,'--card','0','--output',str(output),'--input',str(inp),'--oracle',str(root/'unused-oracle'),'--max-new',str(cap)]
   if name!='K0':argv+=['--k0',str(success['K0'])]
   if name not in ('K0','W0p'):
    argv+=['--dispatch',str(dispatch)]
    for prior in ('K1a','K1b','K2','W0p','KD'):
     if prior in success:argv+=['--'+prior.lower(),str(success[prior])]
   if name in window.SUITE_WINDOWS:argv+=['--suite-manifest',str(manifests[cap])]
   if label=='WSs-exact':argv+=['--retain-steps','1-8']
   elif name in window.SPEED_WINDOWS:
    companion='WSs-exact' if name=='WSs' else window.SPEED_WINDOWS[name]
    argv+=['--exactness-window',str(success[companion])]
   with patch.object(sys,'argv',argv),contextlib.redirect_stdout((output.parent/(label+'-summary.log')).open('w')):
    code=window.main(cpu_rehearsal=True)
   result=json.loads((output/'window.json').read_text());pp.require(code==0 and result['passed'],label+' wrapper failed: '+str(result.get('error')))
   pp.require(result['device_executed'] is False and result['cpu_rehearsal'] is True,'CPU wrapper mislabeled')
   if name=='K2':pp.require(result['device_timing_qualified'] is False,'CPU timestamps promoted');dispatch=output/'run0/dispatch-measured.json'
   success[label]=output/'window.json'
   try:window.prerequisites(success[label],name,result)
   except ValueError as error:pp.require('CPU rehearsal cannot authorize device work' in str(error),'CPU seal refusal reason')
   else:raise AssertionError('CPU rehearsal authorized device prerequisite')
   # Every wrapper also completes its ordinary failure writer. No GPU fault
   # line, no device contact: no boot latch may be written.
   failed=seal/(label+'-failure');bad_argv=argv.copy();bad_argv[bad_argv.index('--output')+1]=str(failed);CpuWatch.fail=True
   try:
    with patch.object(sys,'argv',bad_argv),contextlib.redirect_stdout((root/(label+'-failure.log')).open('w')):rc=window.main(cpu_rehearsal=True)
   finally:CpuWatch.fail=False
   failure=json.loads((failed/'window.json').read_text());pp.require(rc==1 and not failure['passed'] and 'injected wrapper' in failure['error'],'ordinary wrapper failure summary missing')
   pp.require(not (B/'FAULT.json').exists(),'ordinary CPU failure wrote boot latch')
   rows.append(dict(window=name,label=label,passed=True,device_executed=False,success_window_sha256=pp.sha(output/'window.json'),failure_window_sha256=pp.sha(failed/'window.json'),failure_did_not_latch=True,
    limitations=['K0 structural shim only'] if name=='K0' else ['K1 registered-entry validation-only; arithmetic gates separate'] if name in ('K1a','K1b') else ['CPU zero event timestamps rejected by real K2 summary'] if name=='K2' else []))
   pp.save(P/'full-wrapper-gates.json',dict(passed=False,in_progress=True,rows=rows,device_executed=False))
 # Evidence contains hashes, exact summaries and compressed event logs before
 # scratch is deleted; never retain raw CPU outputs as a second build tree.
 import gzip
 packet={str(f.relative_to(root)):json.loads(f.read_text()) for f in root.rglob('window.json')}
 data=json.dumps(packet,sort_keys=True,separators=(',',':')).encode();storage.admit(len(data)+1_000_000);archive=P/'evidence/full-wrapper-windows.json.gz';archive.parent.mkdir(exist_ok=True);archive.write_bytes(gzip.compress(data,mtime=0))
 pp.require(source_sha256=={name:pp.sha(P/name) for name in SOURCES},'wrapper sources changed during rehearsal')
 report=dict(source_sha256=source_sha256,archive_path=str(archive.relative_to(P)),passed=True,in_progress=False,device_executed=False,no_speed_claim=True,windows=len(rows),failure_windows=len(rows),rows=rows,
  host_binary_sha256=pp.sha(binary),archive_sha256=pp.sha(archive),scope='every window.main success and ordinary failure path, real host runtime/fixture/KD/suite summary; explicit CPU-only seam and admission mocks',
  limitations=['K0 JIT body remains device-only; structural shim does not execute JIT','CPU K2 must fail device timing admission','Hardware faults/event timing and real-model windows require coordinator'])
 pp.save(P/'full-wrapper-gates.json',report);shutil.rmtree(root);print(json.dumps(dict(passed=True,windows=len(rows),failure_windows=len(rows),scratch_removed=True)))
if __name__=='__main__':main()
