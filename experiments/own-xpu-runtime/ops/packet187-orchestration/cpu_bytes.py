"""Fresh CPU runs of the hash-bound packet186 V3 fixtures (state correctness + production shape), packet187 inputs.

* state (composition-bytes.json): packet186's miniature rank-0 V3 engines (GNU and Intel; snapshot_host
  production and static): 64-step direct vs speculative sequence on every rank-0 byte, guard refusals and
  the negative control; canonical transcripts must equal packet186's.
* real shape (real-shape.json): packet186's production-shape fixture (real entry code, numerical addresses,
  no payload) loading packet187's ACTIVE selection (the V3 record composition) on both ranks with five
  re-selecting bracket resets, then the real-parser startup of both ranks with packet187's own chain
  inputs (plan, dispatch, draft manifest, selection). The census must equal packet186's measured V3
  dual-layout census; the speculative image must stay 19,025,640 B / 984 extents.
"""
import concurrent.futures,hashlib,json,os,resource,shutil,subprocess,sys
from pathlib import Path
O=Path(__file__).resolve().parent;ROOT=O.parents[3];P=ROOT/'experiments/own-xpu-runtime/stage2/packet187-record-bundle-v3'
SRC=ROOT/'experiments/own-xpu-runtime/stage2/packet186-twocard-v3/v5'
CENSUS={0:30245049064,1:31581735626}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def place():
 state=json.loads((SRC/'evidence/v3-state.json').read_text());shape=json.loads((SRC/'evidence/full-shape.json').read_text())
 pins={}
 for compiler in ('GNU','Intel'):
  src=SRC/'build/v3-state'/('engine-'+compiler);want={r['binary_sha256'] for r in state['engine_runs'] if r['compiler']==compiler}
  assert len(want)==1 and sha(src) in want,'packet186 state engine differs from its receipt: '+compiler
  pins['build/cpu/state/engine-'+compiler]=(src,sha(src))
 for mode in ('v3','v3p'):
  src=SRC/'build/v3-state/selections'/(mode+'.json');assert sha(src)==state['selections'][mode]['sha256']
  pins['build/cpu/state/'+mode+'.json']=(src,sha(src))
 src=SRC/'build/full-shape/fixture';assert sha(src)==shape['binary_sha256'],'packet186 full-shape fixture differs from its receipt'
 pins['build/cpu/real-shape/fixture']=(src,sha(src))
 for rel,(src,digest) in pins.items():
  dst=P/rel;dst.parent.mkdir(parents=True,exist_ok=True)
  if not dst.exists():shutil.copy2(src,dst)
  assert sha(dst)==digest
 return {k:dict(sha256=v[1],origin=str(v[0].relative_to(ROOT))) for k,v in pins.items()},state,shape
def real_shape(shape):
 out=P/'build/cpu/real-shape/results';shutil.rmtree(out,ignore_errors=True);out.mkdir(parents=True)
 sel=P/'selection.json';rows=[]
 for rank in (0,1):
  dest=out/f'v3-rank{rank}';dest.mkdir()
  cmd=[str(P/'build/cpu/real-shape/fixture'),str(sel),sha(sel),str(rank),str(dest),str(sel),sha(sel)]
  cp=subprocess.run(cmd,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=900,env=dict(PATH='/usr/bin:/bin',OMP_NUM_THREADS='2'))
  assert cp.returncode==0,cp.stdout[-2000:]+cp.stderr[-2000:]
  result=json.loads((dest/'result.json').read_text());census=json.loads((dest/'census.json').read_text())['totals']['device'];load=json.loads((dest/'v3-load.json').read_text())
  assert result['passed'] and result['views']==5 and result['rank0_extended'] is True and result['native_refusals']==19 and all(v==result['initial_capture'] for v in result['view_captures'])
  assert census==CENSUS[rank],('census differs from packet186 V3 dual layout',rank,census)
  row=dict(rank=rank,command=cmd,device_census_bytes=census,half_skips_per_view=result['half_skips_per_view'],initial_capture=result['initial_capture'],native_refusals=result['native_refusals'],
           moved_sites=load['moved_sites'],private_buffers=len(load['private_buffers']),banked_state=len(load['banked_state']))
  if rank==0:
   image=json.loads((dest/'image-census.json').read_text())
   assert image['capture_bytes']==19025640 and image['extents']==984 and not any(s['name'].startswith(('blk.24.','blk.25.')) for s in image['sources'])
   assert load['moved_sites']==60 and len(load['private_buffers'])==80 and result['half_skips_per_view']==[60]*5
   row.update(image_capture_bytes=image['capture_bytes'],image_extents=image['extents'])
  else:assert result['half_skips_per_view']==[60]*5,'rank 1 must skip layers 24-25 in every V3 view'
  parent={(r['load'],r['rank']):r['result']['initial_capture'] for r in shape['runs']}
  row['capture_equals_packet186_v3_first']=result['initial_capture']==parent[('v3-first',rank)];assert row['capture_equals_packet186_v3_first']
  rows.append(row)
 startup=[]
 for rank in (0,1):
  dest=out/f'startup-rank{rank}'
  cmd=[str(P/'build/cpu/real-shape/fixture'),'--startup109','--rank',str(rank),'--draft-rank','1','--target-split','0','--context','4096','--tokens','128','--memory','resident','--cards','1','--card','0',
       '--gemv','r5','--nongemv','parallel','--timing','token','--retain-steps','none','--selection',str(sel),'--selection-sha256',sha(sel),'--dispatch',str(P/'dispatch-speed6.json'),
       '--plan',str(P/'build/input/plan.tsv'),'--draft-manifest',str(P/'mtp-manifest.tsv'),'--native-nice','19','--output',str(dest)]
  if rank==1:cmd+=['--draft-mtp']
  cp=subprocess.run(cmd,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=900,env=dict(PATH='/usr/bin:/bin',OMP_NUM_THREADS='2'))
  assert cp.returncode==0,cp.stderr[-2000:]
  result=json.loads((dest/'result.json').read_text());census=json.loads((dest/'census.json').read_text())['totals']['device']
  assert result['passed'] and result['prepared'] and census==CENSUS[rank]
  startup.append(dict(rank=rank,command=cmd,device_census_bytes=census,inputs='packet187 chain inputs (build/input/plan.tsv, dispatch-speed6.json, mtp-manifest.tsv, selection.json)'))
 shutil.rmtree(out)
 return rows,startup
def main():
 assert shutil.disk_usage('/').free>=25_000_000_000
 pins,state,shape=place()
 rows,startup=real_shape(shape)
 (O/'evidence/real-shape.json').write_text(json.dumps(dict(passed=True,device_executed=False,model_payload_read=False,schema='packet187.v3-real-shape.v1',selection_sha256=sha(P/'selection.json'),
   runs=rows,startup_runs=startup,fixture=pins['build/cpu/real-shape/fixture'],
   placement='lane A cards 0+1: each rank process owns one card (card index 0 inside its masked process), identical B70 capacity 34,242,297,856 B, so the per-rank census/admission is the lane-B-measured one'),indent=2)+'\n')
 out=P/'build/cpu/state/results';shutil.rmtree(out,ignore_errors=True);out.mkdir(parents=True)
 def run(job):
  compiler,mode=job
  dest=out/f'{compiler}-{mode}';dest.mkdir()
  binary=P/'build/cpu/state'/('engine-'+compiler);selection=P/'build/cpu/state'/(mode+'.json')
  log=O/'evidence'/f'state-{compiler}-{mode}.log'
  with log.open('w') as f:
   cp=subprocess.run([sys.executable,'-B',str(O/'cpu_bytes.py'),'--worker',str(binary),str(selection),sha(selection),str(dest)],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,env=dict(PATH='/usr/bin:/bin',OMP_NUM_THREADS='2',LD_LIBRARY_PATH='/opt/intel/oneapi/compiler/2026.0/lib'),timeout=1800)
  assert cp.returncode==0,log.read_text()[-1500:]
  result=json.loads((dest/'result.json').read_text());result.update(compiler=compiler,selection=mode)
  print(compiler,mode,'PASS',flush=True);return result
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:runs=list(pool.map(run,[(c,m) for c in ('GNU','Intel') for m in ('v3','v3p')]))
 parent={(r['compiler'],r['selection']):r['canonical_sha256'] for r in state['engine_runs']}
 for r in runs:
  assert r['passed'] and r['cases']>=65 and r['negatives']==2 and r['refusals']>=8
  assert r['canonical_sha256']==parent[(r['compiler'],r['selection'])],'state transcript differs from packet186'
 shutil.rmtree(out)
 (O/'evidence/composition-bytes.json').write_text(json.dumps(dict(passed=True,device_executed=False,schema='packet187.v3-state.v1',runs=runs,fixtures={k:v for k,v in pins.items() if '/state/' in k},
   transcripts_equal_packet186=True,peak_child_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss),indent=2)+'\n')
 print('V3 real-shape and state fixtures PASS')
if __name__=='__main__':
 if '--worker' in sys.argv:
  resource.setrlimit(resource.RLIMIT_AS,(1280*1024**2,1280*1024**2));os.execv(sys.argv[2],sys.argv[2:])
 else:resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
